import { screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import * as knowledgeApi from '../src/api/knowledge'
import { renderKnowledgePage } from './testUtils'

vi.mock('../src/api/knowledge')

const mockedListDocuments = vi.mocked(knowledgeApi.listDocuments)
const mockedGetKnowledgeHealth = vi.mocked(knowledgeApi.getKnowledgeHealth)

const HEALTH = {
  documents: { total: 0, ready: 0, processing: 0, failed: 0 },
  chunks: 0,
  ready_for_chat: false,
  last_indexed_at: null,
}

beforeEach(() => {
  mockedListDocuments.mockReset()
  mockedGetKnowledgeHealth.mockReset()
})

describe('Knowledge document list', () => {
  it('renders tenant-returned documents with human-readable status, in received order', async () => {
    mockedListDocuments.mockResolvedValue([
      {
        id: 'doc-1',
        filename: 'treningi.pdf',
        content_type: 'text/plain',
        status: 'ready',
        uploaded_at: '2026-08-20T10:00:00Z',
        updated_at: '2026-08-20T10:00:00Z',
        indexed_at: '2026-08-20T10:00:05Z',
        error_message: null,
      },
      {
        id: 'doc-2',
        filename: 'cennik.pdf',
        content_type: 'text/plain',
        status: 'failed',
        uploaded_at: '2026-08-20T09:00:00Z',
        updated_at: '2026-08-20T09:00:01Z',
        indexed_at: null,
        error_message: 'Document could not be processed.',
      },
    ])
    mockedGetKnowledgeHealth.mockResolvedValue(HEALTH)

    renderKnowledgePage()

    await waitFor(() => expect(screen.getByText('treningi.pdf')).toBeInTheDocument())
    const rows = screen.getAllByRole('row').slice(1) // skip header row
    expect(rows[0]).toHaveTextContent('treningi.pdf')
    expect(rows[0]).toHaveTextContent('Ready')
    expect(rows[1]).toHaveTextContent('cennik.pdf')
    expect(rows[1]).toHaveTextContent('Failed')
  })

  it('renders an intentional empty state with a working upload CTA, not a broken table', async () => {
    mockedListDocuments.mockResolvedValue([])
    mockedGetKnowledgeHealth.mockResolvedValue(HEALTH)

    renderKnowledgePage()

    await waitFor(() =>
      expect(screen.getByText('No knowledge has been added yet.')).toBeInTheDocument(),
    )
    expect(screen.queryByRole('table')).not.toBeInTheDocument()
    expect(screen.getByLabelText('Upload document')).toBeInTheDocument()
  })

  it('shows an explicit loading state before data arrives', () => {
    mockedListDocuments.mockReturnValue(new Promise(() => {}))
    mockedGetKnowledgeHealth.mockReturnValue(new Promise(() => {}))

    renderKnowledgePage()

    expect(screen.getByRole('status')).toBeInTheDocument()
    expect(screen.queryByRole('table')).not.toBeInTheDocument()
  })

  it('shows a distinct, retryable error state when the initial load fails — never as an empty knowledge base', async () => {
    mockedListDocuments.mockRejectedValue({ message: 'Something went wrong.' })
    mockedGetKnowledgeHealth.mockResolvedValue(HEALTH)

    renderKnowledgePage()

    const retry = await screen.findByRole('button', { name: 'Retry' })
    expect(screen.queryByText('No knowledge has been added yet.')).not.toBeInTheDocument()
    expect(retry).toBeInTheDocument()
  })
})
