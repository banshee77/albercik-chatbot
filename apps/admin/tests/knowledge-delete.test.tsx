import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import * as knowledgeApi from '../src/api/knowledge'
import { renderKnowledgePage } from './testUtils'

vi.mock('../src/api/knowledge')

const mockedListDocuments = vi.mocked(knowledgeApi.listDocuments)
const mockedGetKnowledgeHealth = vi.mocked(knowledgeApi.getKnowledgeHealth)
const mockedDeleteDocument = vi.mocked(knowledgeApi.deleteDocument)

const HEALTH_ONE = {
  documents: { total: 1, ready: 1, processing: 0, failed: 0 },
  chunks: 3,
  ready_for_chat: true,
  last_indexed_at: '2026-08-20T10:00:05Z',
}

const HEALTH_EMPTY = {
  documents: { total: 0, ready: 0, processing: 0, failed: 0 },
  chunks: 0,
  ready_for_chat: false,
  last_indexed_at: null,
}

const DOCUMENT = {
  id: 'doc-1',
  filename: 'treningi.pdf',
  content_type: 'text/plain',
  status: 'ready' as const,
  uploaded_at: '2026-08-20T10:00:00Z',
  updated_at: '2026-08-20T10:00:00Z',
  indexed_at: '2026-08-20T10:00:05Z',
  error_message: null,
}

beforeEach(() => {
  mockedListDocuments.mockReset()
  mockedGetKnowledgeHealth.mockReset()
  mockedDeleteDocument.mockReset()
  mockedListDocuments.mockResolvedValue([DOCUMENT])
  mockedGetKnowledgeHealth.mockResolvedValue(HEALTH_ONE)
})

async function openDetailAndDeleteDialog(user: ReturnType<typeof userEvent.setup>) {
  await waitFor(() => expect(screen.getByText('treningi.pdf')).toBeInTheDocument())
  await user.click(screen.getByRole('button', { name: 'treningi.pdf' }))
  await screen.findByRole('region', { name: /treningi\.pdf/i })
  await user.click(screen.getByRole('button', { name: 'Delete' }))
  return screen.findByRole('dialog', { name: /delete treningi\.pdf/i })
}

describe('Knowledge delete', () => {
  it('requires explicit confirmation that identifies the document by filename', async () => {
    const user = userEvent.setup()
    renderKnowledgePage()

    const dialog = await openDetailAndDeleteDialog(user)
    expect(dialog).toHaveTextContent('Delete "treningi.pdf"?')
    expect(mockedDeleteDocument).not.toHaveBeenCalled()
  })

  it('disables the confirmation control while in flight, preventing duplicate submission', async () => {
    let resolveDelete!: () => void
    mockedDeleteDocument.mockReturnValue(
      new Promise((resolve) => {
        resolveDelete = resolve
      }),
    )
    const user = userEvent.setup()
    renderKnowledgePage()

    const dialog = await openDetailAndDeleteDialog(user)
    await user.click(within(dialog).getByRole('button', { name: 'Delete' }))

    expect(within(dialog).getByRole('button', { name: 'Delete' })).toBeDisabled()
    expect(mockedDeleteDocument).toHaveBeenCalledTimes(1)

    resolveDelete()
    await waitFor(() => expect(screen.getByText('Document deleted.')).toBeInTheDocument())
    expect(mockedDeleteDocument).toHaveBeenCalledTimes(1)
  })

  it('on success, removes the document from the list and refreshes health — no full reload', async () => {
    mockedDeleteDocument.mockResolvedValue(undefined)
    const user = userEvent.setup()
    renderKnowledgePage()

    const dialog = await openDetailAndDeleteDialog(user)
    mockedListDocuments.mockResolvedValue([])
    mockedGetKnowledgeHealth.mockResolvedValue(HEALTH_EMPTY)

    await user.click(within(dialog).getByRole('button', { name: 'Delete' }))

    await waitFor(() => expect(screen.queryByText('treningi.pdf')).not.toBeInTheDocument())
    expect(screen.getByText('No knowledge has been added yet.')).toBeInTheDocument()
    expect(screen.getByText('Document deleted.')).toBeInTheDocument()
  })

  it('shows a safe, generic message on delete failure', async () => {
    mockedDeleteDocument.mockRejectedValue({ message: 'Something went wrong. Please try again.' })
    const user = userEvent.setup()
    renderKnowledgePage()

    const dialog = await openDetailAndDeleteDialog(user)
    await user.click(within(dialog).getByRole('button', { name: 'Delete' }))

    expect(await screen.findByText('Something went wrong. Please try again.')).toBeInTheDocument()
  })

  it('is reachable and operable using the keyboard alone, with correct focus behavior', async () => {
    mockedDeleteDocument.mockResolvedValue(undefined)
    const user = userEvent.setup()
    renderKnowledgePage()

    await waitFor(() => expect(screen.getByText('treningi.pdf')).toBeInTheDocument())
    const rowButton = screen.getByRole('button', { name: 'treningi.pdf' })
    rowButton.focus()
    await user.keyboard('{Enter}')
    await screen.findByRole('region', { name: /treningi\.pdf/i })

    const deleteTrigger = screen.getByRole('button', { name: 'Delete' })
    deleteTrigger.focus()
    await user.keyboard('{Enter}')
    const dialog = await screen.findByRole('dialog', { name: /delete treningi\.pdf/i })
    await waitFor(() => expect(dialog.contains(document.activeElement)).toBe(true))

    const confirm = within(dialog).getByRole('button', { name: 'Delete' })
    confirm.focus()
    await user.keyboard('{Enter}')

    await waitFor(() => expect(mockedDeleteDocument).toHaveBeenCalledWith('doc-1'))
  })
})
