import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import * as conversationsApi from '../src/api/conversations'
import { renderConversationsPage } from './testUtils'

vi.mock('../src/api/conversations')

const mockedListConversations = vi.mocked(conversationsApi.listConversations)

const EMPTY_RESPONSE = { items: [], total: 0, limit: 20, offset: 0 }

beforeEach(() => {
  mockedListConversations.mockReset()
})

describe('Conversations empty states', () => {
  it('shows "No conversations yet." when the tenant has no conversations and no filters are active', async () => {
    mockedListConversations.mockResolvedValue(EMPTY_RESPONSE)

    renderConversationsPage()

    await waitFor(() => expect(screen.getByText('No conversations yet.')).toBeInTheDocument())
    expect(screen.queryByRole('table')).not.toBeInTheDocument()
    expect(screen.queryByText('No conversations match the selected filters.')).not.toBeInTheDocument()
  })

  it('shows a distinct filtered-empty state with a working "Clear filters" action', async () => {
    mockedListConversations.mockResolvedValue({
      items: [
        {
          id: 'conv-1',
          request_id: 'req-1',
          question: 'When are beginner classes?',
          outcome: 'grounded' as const,
          created_at: '2026-08-20T10:15:00Z',
          latency_ms: 1180,
        },
      ],
      total: 1,
      limit: 20,
      offset: 0,
    })
    const user = userEvent.setup()
    renderConversationsPage()

    await waitFor(() => expect(screen.getByLabelText('Search questions')).toBeInTheDocument())
    mockedListConversations.mockResolvedValueOnce(EMPTY_RESPONSE)
    await user.type(screen.getByLabelText('Search questions'), 'nonexistent')
    await user.click(screen.getByRole('button', { name: 'Search' }))

    await waitFor(() =>
      expect(screen.getByText('No conversations match the selected filters.')).toBeInTheDocument(),
    )
    expect(screen.queryByText('No conversations yet.')).not.toBeInTheDocument()

    mockedListConversations.mockResolvedValueOnce({
      items: [
        {
          id: 'conv-1',
          request_id: 'req-1',
          question: 'When are beginner classes?',
          outcome: 'grounded' as const,
          created_at: '2026-08-20T10:15:00Z',
          latency_ms: 1180,
        },
      ],
      total: 1,
      limit: 20,
      offset: 0,
    })
    await user.click(screen.getByRole('button', { name: 'Clear filters' }))

    await waitFor(() =>
      expect(screen.getByText('When are beginner classes?')).toBeInTheDocument(),
    )
    expect(mockedListConversations).toHaveBeenLastCalledWith(
      expect.objectContaining({ q: undefined, outcome: undefined, offset: 0 }),
    )
    expect((screen.getByLabelText('Search questions') as HTMLInputElement).value).toBe('')
  })
})
