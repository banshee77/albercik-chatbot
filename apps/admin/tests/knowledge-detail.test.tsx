import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import * as knowledgeApi from '../src/api/knowledge'
import { renderKnowledgePage } from './testUtils'

vi.mock('../src/api/knowledge')

const mockedListDocuments = vi.mocked(knowledgeApi.listDocuments)
const mockedGetKnowledgeHealth = vi.mocked(knowledgeApi.getKnowledgeHealth)

const HEALTH = {
  documents: { total: 3, ready: 1, processing: 1, failed: 1 },
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

const PROCESSING_DOCUMENT = {
  id: 'doc-processing',
  filename: 'harmonogram.pdf',
  content_type: 'text/plain',
  status: 'processing' as const,
  uploaded_at: '2026-08-20T11:00:00Z',
  updated_at: '2026-08-20T11:00:00Z',
  indexed_at: null,
  error_message: null,
}

beforeEach(() => {
  mockedListDocuments.mockReset()
  mockedGetKnowledgeHealth.mockReset()
  mockedListDocuments.mockResolvedValue([READY_DOCUMENT, FAILED_DOCUMENT, PROCESSING_DOCUMENT])
  mockedGetKnowledgeHealth.mockResolvedValue(HEALTH)
})

describe('Knowledge document detail', () => {
  it("shows 'Failed' as text plus its sanitized message, with Re-index available", async () => {
    const user = userEvent.setup()
    renderKnowledgePage()

    await waitFor(() => expect(screen.getByText('cennik.pdf')).toBeInTheDocument())
    await user.click(screen.getByRole('button', { name: 'cennik.pdf' }))

    const detail = await screen.findByRole('region', { name: /cennik\.pdf/i })
    expect(detail).toHaveTextContent('Failed')
    expect(detail).toHaveTextContent('Document could not be processed.')
    expect(screen.getByRole('button', { name: 'Rebuild search index' })).toBeInTheDocument()
  })

  it('shows no failure message for a ready document and never presents it as unusable', async () => {
    const user = userEvent.setup()
    renderKnowledgePage()

    await waitFor(() => expect(screen.getByText('treningi.pdf')).toBeInTheDocument())
    await user.click(screen.getByRole('button', { name: 'treningi.pdf' }))

    const detail = await screen.findByRole('region', { name: /treningi\.pdf/i })
    expect(detail).not.toHaveTextContent('could not be processed')
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  it('does not offer Re-index for a document that is still Processing', async () => {
    const user = userEvent.setup()
    renderKnowledgePage()

    await waitFor(() => expect(screen.getByText('harmonogram.pdf')).toBeInTheDocument())
    await user.click(screen.getByRole('button', { name: 'harmonogram.pdf' }))

    await screen.findByRole('region', { name: /harmonogram\.pdf/i })
    expect(screen.queryByRole('button', { name: 'Rebuild search index' })).not.toBeInTheDocument()
  })
})
