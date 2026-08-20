import { screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import * as knowledgeApi from '../src/api/knowledge'
import { renderKnowledgePage } from './testUtils'

vi.mock('../src/api/knowledge')

const mockedListDocuments = vi.mocked(knowledgeApi.listDocuments)
const mockedGetKnowledgeHealth = vi.mocked(knowledgeApi.getKnowledgeHealth)

beforeEach(() => {
  mockedListDocuments.mockReset()
  mockedGetKnowledgeHealth.mockReset()
})

describe('Knowledge health summary', () => {
  it('renders total/ready/processing/failed counts, chunks, and ready-for-chat from the API', async () => {
    mockedListDocuments.mockResolvedValue([])
    mockedGetKnowledgeHealth.mockResolvedValue({
      documents: { total: 12, ready: 11, processing: 0, failed: 1 },
      chunks: 184,
      ready_for_chat: true,
      last_indexed_at: '2026-08-20T12:00:00Z',
    })

    renderKnowledgePage()

    await waitFor(() => expect(screen.getByText('12 documents')).toBeInTheDocument())
    expect(screen.getByText('11 ready')).toBeInTheDocument()
    expect(screen.getByText('0 processing')).toBeInTheDocument()
    expect(screen.getByText('1 failed')).toBeInTheDocument()
    expect(screen.getByText('184 chunks')).toBeInTheDocument()
    expect(screen.getByText('Ready for chat: Yes')).toBeInTheDocument()
  })
})
