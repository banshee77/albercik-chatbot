import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import * as knowledgeApi from '../src/api/knowledge'
import type { DocumentSummary } from '../src/api/types'
import { renderKnowledgePage } from './testUtils'

vi.mock('../src/api/knowledge')

const mockedListDocuments = vi.mocked(knowledgeApi.listDocuments)
const mockedGetKnowledgeHealth = vi.mocked(knowledgeApi.getKnowledgeHealth)
const mockedReindexDocument = vi.mocked(knowledgeApi.reindexDocument)

const HEALTH = {
  documents: { total: 2, ready: 1, processing: 0, failed: 1 },
  chunks: 4,
  ready_for_chat: true,
  last_indexed_at: '2026-08-20T10:00:05Z',
}

const READY_DOCUMENT = {
  id: 'doc-ready',
  filename: 'treningi.pdf',
  content_type: 'text/plain',
  status: 'ready' as const,
  uploaded_at: '2026-08-20T10:00:00Z',
  updated_at: '2026-08-20T10:00:00Z',
  indexed_at: '2026-08-20T10:00:05Z',
  error_message: null,
}

const FAILED_DOCUMENT = {
  id: 'doc-failed',
  filename: 'cennik.pdf',
  content_type: 'text/plain',
  status: 'failed' as const,
  uploaded_at: '2026-08-20T09:00:00Z',
  updated_at: '2026-08-20T09:00:01Z',
  indexed_at: null,
  error_message: 'Document could not be processed.',
}

beforeEach(() => {
  mockedListDocuments.mockReset()
  mockedGetKnowledgeHealth.mockReset()
  mockedReindexDocument.mockReset()
  mockedListDocuments.mockResolvedValue([READY_DOCUMENT, FAILED_DOCUMENT])
  mockedGetKnowledgeHealth.mockResolvedValue(HEALTH)
})

async function openDetail(user: ReturnType<typeof userEvent.setup>, filename: string) {
  await waitFor(() => expect(screen.getByText(filename)).toBeInTheDocument())
  await user.click(screen.getByRole('button', { name: filename }))
  await screen.findByRole('region', { name: new RegExp(filename.replace('.', '\\.'), 'i') })
}

describe('Knowledge re-index', () => {
  it('disables duplicate submission for that document while leaving other documents usable', async () => {
    let resolveReindex!: (value: DocumentSummary) => void
    mockedReindexDocument.mockReturnValue(
      new Promise((resolve) => {
        resolveReindex = resolve
      }),
    )
    const user = userEvent.setup()
    renderKnowledgePage()

    await openDetail(user, 'cennik.pdf')
    await user.click(screen.getByRole('button', { name: 'Rebuild search index' }))

    expect(screen.getByRole('button', { name: 'Rebuild search index' })).toBeDisabled()
    expect(mockedReindexDocument).toHaveBeenCalledTimes(1)

    // Switching to the other document's detail is unaffected.
    await user.click(screen.getByRole('button', { name: 'treningi.pdf' }))
    await screen.findByRole('region', { name: /treningi\.pdf/i })
    expect(screen.getByRole('button', { name: 'Rebuild search index' })).not.toBeDisabled()

    resolveReindex({ ...FAILED_DOCUMENT, status: 'ready', error_message: null })
  })

  it('refreshes the document state and health on a successful re-index', async () => {
    mockedReindexDocument.mockResolvedValue({ ...FAILED_DOCUMENT, status: 'ready', error_message: null })
    const user = userEvent.setup()
    renderKnowledgePage()

    await openDetail(user, 'cennik.pdf')
    mockedListDocuments.mockResolvedValue([
      READY_DOCUMENT,
      { ...FAILED_DOCUMENT, status: 'ready', error_message: null },
    ])
    mockedGetKnowledgeHealth.mockResolvedValue({
      ...HEALTH,
      documents: { total: 2, ready: 2, processing: 0, failed: 0 },
    })

    await user.click(screen.getByRole('button', { name: 'Rebuild search index' }))

    await waitFor(() => expect(screen.getByText('2 ready')).toBeInTheDocument())
    expect(screen.getByText('Search index rebuilt.')).toBeInTheDocument()
  })

  it('on failure, shows a safe message and never marks an already-ready document as broken', async () => {
    mockedReindexDocument.mockRejectedValue({
      message: 'Something went wrong. Please try again.',
    })
    const user = userEvent.setup()
    renderKnowledgePage()

    await openDetail(user, 'cennik.pdf')
    await user.click(screen.getByRole('button', { name: 'Rebuild search index' }))

    expect(await screen.findByText('Something went wrong. Please try again.')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'treningi.pdf' }))
    const readyDetail = await screen.findByRole('region', { name: /treningi\.pdf/i })
    expect(readyDetail).toHaveTextContent('Ready')
    expect(readyDetail).not.toHaveTextContent('could not be processed')
  })

  it('is operable using the keyboard alone', async () => {
    mockedReindexDocument.mockResolvedValue({ ...FAILED_DOCUMENT, status: 'ready', error_message: null })
    const user = userEvent.setup()
    renderKnowledgePage()

    await openDetail(user, 'cennik.pdf')
    const reindexButton = screen.getByRole('button', { name: 'Rebuild search index' })
    reindexButton.focus()
    expect(reindexButton).toHaveFocus()
    await user.keyboard('{Enter}')

    await waitFor(() => expect(mockedReindexDocument).toHaveBeenCalledWith('doc-failed'))
  })
})
