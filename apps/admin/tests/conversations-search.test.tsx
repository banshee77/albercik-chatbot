import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import * as conversationsApi from '../src/api/conversations'
import { renderConversationsPage } from './testUtils'

vi.mock('../src/api/conversations')

const mockedListConversations = vi.mocked(conversationsApi.listConversations)

const EMPTY_RESPONSE = { items: [], total: 0, limit: 20, offset: 0 }
const ONE_ITEM_RESPONSE = {
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
}

beforeEach(() => {
  mockedListConversations.mockReset()
  mockedListConversations.mockResolvedValue(ONE_ITEM_RESPONSE)
})

describe('Conversations search', () => {
  it('submitting a search term re-queries the server with q set, resetting to the first page', async () => {
    const user = userEvent.setup()
    renderConversationsPage()

    await waitFor(() => expect(screen.getByLabelText('Search questions')).toBeInTheDocument())
    mockedListConversations.mockResolvedValueOnce(EMPTY_RESPONSE)

    await user.type(screen.getByLabelText('Search questions'), 'swallow')
    await user.click(screen.getByRole('button', { name: 'Search' }))

    await waitFor(() => expect(mockedListConversations).toHaveBeenLastCalledWith(
      expect.objectContaining({ q: 'swallow', offset: 0 }),
    ))
  })

  it('clearing the search term and resubmitting re-queries without q', async () => {
    const user = userEvent.setup()
    renderConversationsPage()

    await waitFor(() => expect(screen.getByLabelText('Search questions')).toBeInTheDocument())

    const input = screen.getByLabelText('Search questions')
    await user.type(input, 'swallow')
    await user.click(screen.getByRole('button', { name: 'Search' }))
    await waitFor(() =>
      expect(mockedListConversations).toHaveBeenLastCalledWith(
        expect.objectContaining({ q: 'swallow' }),
      ),
    )

    await user.clear(input)
    await user.click(screen.getByRole('button', { name: 'Search' }))

    await waitFor(() =>
      expect(mockedListConversations).toHaveBeenLastCalledWith(
        expect.objectContaining({ q: undefined }),
      ),
    )
  })
})
