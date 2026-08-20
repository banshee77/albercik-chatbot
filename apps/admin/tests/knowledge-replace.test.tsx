import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import * as knowledgeApi from '../src/api/knowledge'
import { renderKnowledgePage } from './testUtils'

vi.mock('../src/api/knowledge')

const mockedListDocuments = vi.mocked(knowledgeApi.listDocuments)
const mockedGetKnowledgeHealth = vi.mocked(knowledgeApi.getKnowledgeHealth)
const mockedReplaceDocument = vi.mocked(knowledgeApi.replaceDocument)

const HEALTH = {
  documents: { total: 1, ready: 1, processing: 0, failed: 0 },
  chunks: 3,
  ready_for_chat: true,
  last_indexed_at: '2026-08-20T10:00:05Z',
}

function makeDocument(status: 'ready' | 'processing' | 'failed') {
  return {
    id: 'doc-1',
    filename: 'treningi.pdf',
    content_type: 'text/plain',
    status,
    uploaded_at: '2026-08-20T10:00:00Z',
    updated_at: '2026-08-20T10:00:00Z',
    indexed_at: status === 'ready' ? '2026-08-20T10:00:05Z' : null,
    error_message: status === 'failed' ? 'Document could not be processed.' : null,
  }
}

const NEW_VERSION = {
  id: 'doc-2',
  filename: 'treningi-v2.txt',
  content_type: 'text/plain',
  status: 'ready' as const,
  uploaded_at: '2026-08-20T12:00:00Z',
  updated_at: '2026-08-20T12:00:00Z',
  indexed_at: '2026-08-20T12:00:05Z',
  error_message: null,
}

beforeEach(() => {
  mockedListDocuments.mockReset()
  mockedGetKnowledgeHealth.mockReset()
  mockedReplaceDocument.mockReset()
  mockedGetKnowledgeHealth.mockResolvedValue(HEALTH)
})

async function openDetailAndReplaceDialog(user: ReturnType<typeof userEvent.setup>) {
  await waitFor(() => expect(screen.getByText('treningi.pdf')).toBeInTheDocument())
  await user.click(screen.getByRole('button', { name: 'treningi.pdf' }))
  await screen.findByRole('region', { name: /treningi\.pdf/i })
  await user.click(screen.getByRole('button', { name: 'Replace' }))
  return screen.findByRole('dialog', { name: /replace treningi\.pdf/i })
}

describe.each(['ready', 'processing', 'failed'] as const)('Knowledge replace — %s document', (status) => {
  it('offers Replace regardless of the document status', async () => {
    mockedListDocuments.mockResolvedValue([makeDocument(status)])
    const user = userEvent.setup()
    renderKnowledgePage()

    const dialog = await openDetailAndReplaceDialog(user)
    expect(dialog).toBeInTheDocument()
  })
})

describe('Knowledge replace', () => {
  beforeEach(() => {
    mockedListDocuments.mockResolvedValue([makeDocument('ready')])
  })

  it('requires the one lightweight confirmation step before sending the request', async () => {
    const user = userEvent.setup()
    renderKnowledgePage()

    const dialog = await openDetailAndReplaceDialog(user)
    expect(mockedReplaceDocument).not.toHaveBeenCalled()

    const file = new File(['new content'], 'treningi-v2.txt', { type: 'text/plain' })
    await user.upload(within(dialog).getByLabelText('New file'), file)
    expect(mockedReplaceDocument).not.toHaveBeenCalled()

    mockedReplaceDocument.mockResolvedValue(NEW_VERSION)
    await user.click(within(dialog).getByRole('button', { name: 'Replace' }))
    await waitFor(() => expect(mockedReplaceDocument).toHaveBeenCalledTimes(1))
  })

  it('prevents duplicate submission while a replacement is in flight', async () => {
    let resolveReplace!: (value: typeof NEW_VERSION) => void
    mockedReplaceDocument.mockReturnValue(
      new Promise((resolve) => {
        resolveReplace = resolve
      }),
    )
    const user = userEvent.setup()
    renderKnowledgePage()

    const dialog = await openDetailAndReplaceDialog(user)
    const file = new File(['new content'], 'treningi-v2.txt', { type: 'text/plain' })
    await user.upload(within(dialog).getByLabelText('New file'), file)
    await user.click(within(dialog).getByRole('button', { name: 'Replace' }))

    expect(mockedReplaceDocument).toHaveBeenCalledTimes(1)
    resolveReplace(NEW_VERSION)
    await waitFor(() => expect(screen.getByText('Document replaced.')).toBeInTheDocument())
    expect(mockedReplaceDocument).toHaveBeenCalledTimes(1)
  })

  it('on success, refreshes list/health and shows the new version as active', async () => {
    mockedReplaceDocument.mockResolvedValue(NEW_VERSION)
    const user = userEvent.setup()
    renderKnowledgePage()

    const dialog = await openDetailAndReplaceDialog(user)
    mockedListDocuments.mockResolvedValue([NEW_VERSION])
    mockedGetKnowledgeHealth.mockResolvedValue(HEALTH)

    const file = new File(['new content'], 'treningi-v2.txt', { type: 'text/plain' })
    await user.upload(within(dialog).getByLabelText('New file'), file)
    await user.click(within(dialog).getByRole('button', { name: 'Replace' }))

    await waitFor(() => expect(screen.getByText('treningi-v2.txt')).toBeInTheDocument())
    expect(screen.getByText('Document replaced.')).toBeInTheDocument()
  })

  it('on failure, shows a safe message and keeps the original document active and usable', async () => {
    mockedReplaceDocument.mockRejectedValue({ message: 'Something went wrong. Please try again.' })
    const user = userEvent.setup()
    renderKnowledgePage()

    const dialog = await openDetailAndReplaceDialog(user)
    const file = new File(['new content'], 'treningi-v2.txt', { type: 'text/plain' })
    await user.upload(within(dialog).getByLabelText('New file'), file)
    await user.click(within(dialog).getByRole('button', { name: 'Replace' }))

    expect(await screen.findByText('Something went wrong. Please try again.')).toBeInTheDocument()
    expect(screen.getAllByText('treningi.pdf').length).toBeGreaterThan(0)
  })

  it('manages dialog focus correctly on open and close', async () => {
    const user = userEvent.setup()
    renderKnowledgePage()

    await waitFor(() => expect(screen.getByText('treningi.pdf')).toBeInTheDocument())
    await user.click(screen.getByRole('button', { name: 'treningi.pdf' }))
    await screen.findByRole('region', { name: /treningi\.pdf/i })
    const replaceTrigger = screen.getByRole('button', { name: 'Replace' })
    replaceTrigger.focus()
    await user.click(replaceTrigger)

    const dialog = await screen.findByRole('dialog', { name: /replace treningi\.pdf/i })
    await waitFor(() => expect(dialog.contains(document.activeElement)).toBe(true))

    await user.click(within(dialog).getByRole('button', { name: 'Cancel' }))
    await waitFor(() => expect(replaceTrigger).toHaveFocus())
  })

  it('is operable using the keyboard alone', async () => {
    mockedReplaceDocument.mockResolvedValue(NEW_VERSION)
    const user = userEvent.setup()
    renderKnowledgePage()

    await waitFor(() => expect(screen.getByText('treningi.pdf')).toBeInTheDocument())
    const rowButton = screen.getByRole('button', { name: 'treningi.pdf' })
    rowButton.focus()
    await user.keyboard('{Enter}')
    await screen.findByRole('region', { name: /treningi\.pdf/i })

    const replaceTrigger = screen.getByRole('button', { name: 'Replace' })
    replaceTrigger.focus()
    await user.keyboard('{Enter}')
    const dialog = await screen.findByRole('dialog', { name: /replace treningi\.pdf/i })

    const file = new File(['new content'], 'treningi-v2.txt', { type: 'text/plain' })
    await user.upload(within(dialog).getByLabelText('New file'), file)

    const confirm = within(dialog).getByRole('button', { name: 'Replace' })
    confirm.focus()
    await user.keyboard('{Enter}')

    await waitFor(() => expect(mockedReplaceDocument).toHaveBeenCalledTimes(1))
  })
})
