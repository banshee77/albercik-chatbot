import { screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import * as conversationsApi from '../src/api/conversations'
import { renderConversationsPage } from './testUtils'

vi.mock('../src/api/conversations')

const mockedListConversations = vi.mocked(conversationsApi.listConversations)

beforeEach(() => {
  mockedListConversations.mockReset()
})

describe('Conversations list', () => {
  it('shows an explicit loading state before data arrives', () => {
    mockedListConversations.mockReturnValue(new Promise(() => {}))

    renderConversationsPage()

    expect(screen.getByRole('status')).toBeInTheDocument()
    expect(screen.queryByRole('table')).not.toBeInTheDocument()
  })

  it('renders conversations in received (newest-first) order with human-readable outcome labels', async () => {
    mockedListConversations.mockResolvedValue({
      items: [
        {
          id: 'conv-1',
          request_id: 'req-1',
          question: 'When are beginner classes?',
          outcome: 'grounded',
          created_at: '2026-08-20T10:15:00Z',
          latency_ms: 1180,
        },
        {
          id: 'conv-2',
          request_id: 'req-2',
          question: 'Do you offer online training?',
          outcome: 'insufficient_information',
          created_at: '2026-08-20T09:00:00Z',
          latency_ms: 900,
        },
      ],
      total: 2,
      limit: 20,
      offset: 0,
    })

    renderConversationsPage()

    await waitFor(() =>
      expect(screen.getByText('When are beginner classes?')).toBeInTheDocument(),
    )
    const rows = screen.getAllByRole('row').slice(1) // skip header row
    expect(rows[0]).toHaveTextContent('When are beginner classes?')
    expect(rows[0]).toHaveTextContent('Answered')
    expect(rows[1]).toHaveTextContent('Do you offer online training?')
    expect(rows[1]).toHaveTextContent('Knowledge gap')
    // Never the raw backend enum string:
    expect(screen.queryByText('grounded')).not.toBeInTheDocument()
    expect(screen.queryByText('insufficient_information')).not.toBeInTheDocument()
  })

  it('shows a distinct, retryable error state when the initial load fails — never stale/empty data as success', async () => {
    mockedListConversations.mockRejectedValueOnce({ message: 'Something went wrong.' })

    renderConversationsPage()

    const retry = await screen.findByRole('button', { name: 'Retry' })
    expect(screen.queryByText('No conversations yet.')).not.toBeInTheDocument()
    expect(screen.queryByRole('table')).not.toBeInTheDocument()

    mockedListConversations.mockResolvedValueOnce({
      items: [
        {
          id: 'conv-1',
          request_id: 'req-1',
          question: 'When are beginner classes?',
          outcome: 'grounded',
          created_at: '2026-08-20T10:15:00Z',
          latency_ms: 1180,
        },
      ],
      total: 1,
      limit: 20,
      offset: 0,
    })
    retry.click()

    await waitFor(() =>
      expect(screen.getByText('When are beginner classes?')).toBeInTheDocument(),
    )
  })
})
