import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import * as conversationsApi from '../src/api/conversations'
import { renderConversationsPage } from './testUtils'

vi.mock('../src/api/conversations')

const mockedListConversations = vi.mocked(conversationsApi.listConversations)
const mockedGetConversation = vi.mocked(conversationsApi.getConversation)

function item(id: string, question: string) {
  return {
    id,
    request_id: `req-${id}`,
    question,
    outcome: 'grounded' as const,
    created_at: '2026-08-20T10:15:00Z',
    latency_ms: 1180,
  }
}

const LIST_RESPONSE = {
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

const GROUNDED_DETAIL = {
  id: 'conv-1',
  request_id: 'req-1',
  question: 'When are beginner classes?',
  answer: 'Beginner classes run on Tuesdays at 6pm.',
  outcome: 'grounded' as const,
  created_at: '2026-08-20T10:15:00Z',
  latency_ms: 1180,
  sources: [{ document_id: 'doc-1', label: 'treningi.txt' }],
  provider_name: 'ollama',
  provider_model: 'qwen3:8b',
  input_tokens: 512,
  output_tokens: 96,
  safe_failure_category: null,
}

beforeEach(() => {
  mockedListConversations.mockReset()
  mockedGetConversation.mockReset()
  mockedListConversations.mockResolvedValue(LIST_RESPONSE)
  mockedGetConversation.mockResolvedValue(GROUNDED_DETAIL)
})

describe('Conversation detail — focus management', () => {
  it('moves focus to the detail heading on open and restores it to the row button on close', async () => {
    const user = userEvent.setup()
    renderConversationsPage()

    const rowButton = await screen.findByRole('button', { name: 'When are beginner classes?' })
    await user.click(rowButton)

    const heading = await screen.findByRole('heading', { name: 'Conversation detail' })
    await waitFor(() => expect(heading).toHaveFocus())

    await user.click(screen.getByRole('button', { name: 'Close' }))
    await waitFor(() => expect(rowButton).toHaveFocus())
  })
})

describe('Conversations — keyboard navigation (SC-008)', () => {
  it('reaches and activates search, outcome, date, row, and pagination controls via Tab/Enter/Space alone', async () => {
    mockedListConversations.mockResolvedValue({
      items: [item('conv-1', 'When are beginner classes?')],
      total: 45,
      limit: 20,
      offset: 0,
    })
    const user = userEvent.setup()
    renderConversationsPage()

    const searchInput = await screen.findByLabelText('Search questions')
    const searchButton = screen.getByRole('button', { name: 'Search' })
    const outcomeSelect = screen.getByLabelText('Outcome')
    const dateFrom = screen.getByLabelText('From')
    const dateTo = screen.getByLabelText('To')
    const row = screen.getByRole('button', { name: 'When are beginner classes?' })
    const previous = screen.getByRole('button', { name: 'Previous' })
    const next = screen.getByRole('button', { name: 'Next' })

    // Previous starts disabled (offset 0) and is skipped by Tab.
    expect(previous).toBeDisabled()

    // Tab order: search input -> Search button -> outcome -> from -> to -> row -> Next.
    await user.tab()
    expect(searchInput).toHaveFocus()
    await user.tab()
    expect(searchButton).toHaveFocus()
    await user.tab()
    expect(outcomeSelect).toHaveFocus()
    await user.tab()
    expect(dateFrom).toHaveFocus()
    await user.tab()
    expect(dateTo).toHaveFocus()
    await user.tab()
    expect(row).toHaveFocus()
    await user.tab()
    expect(next).toHaveFocus()

    // Enter on the row opens detail.
    mockedGetConversation.mockResolvedValue(GROUNDED_DETAIL)
    row.focus()
    await user.keyboard('{Enter}')
    await screen.findByRole('region', { name: 'Conversation detail' })
    await user.click(screen.getByRole('button', { name: 'Close' }))

    // Enter on Next requests the next page.
    mockedListConversations.mockResolvedValueOnce({
      items: [item('conv-2', 'Second page question')],
      total: 45,
      limit: 20,
      offset: 20,
    })
    next.focus()
    await user.keyboard('{Enter}')
    await waitFor(() => expect(screen.getByText('Second page question')).toBeInTheDocument())

    // Enter on the search form submits it.
    mockedListConversations.mockResolvedValueOnce({ items: [], total: 0, limit: 20, offset: 0 })
    searchInput.focus()
    await user.keyboard('term{Enter}')
    await waitFor(() =>
      expect(mockedListConversations).toHaveBeenLastCalledWith(
        expect.objectContaining({ q: 'term' }),
      ),
    )
  })
})
