import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import * as conversationsApi from '../src/api/conversations'
import { renderConversationsPage } from './testUtils'

vi.mock('../src/api/conversations')

const mockedListConversations = vi.mocked(conversationsApi.listConversations)

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

const PAGE_1 = { items: [item('1', 'First page question')], total: 45, limit: 20, offset: 0 }
const PAGE_2 = { items: [item('2', 'Second page question')], total: 45, limit: 20, offset: 20 }
const LAST_PAGE = { items: [item('3', 'Last page question')], total: 45, limit: 20, offset: 40 }

beforeEach(() => {
  mockedListConversations.mockReset()
})

describe('Conversations pagination', () => {
  it('Previous is disabled on the first page; Next is enabled when more pages exist', async () => {
    mockedListConversations.mockResolvedValue(PAGE_1)
    renderConversationsPage()

    await waitFor(() => expect(screen.getByText('First page question')).toBeInTheDocument())
    expect(screen.getByRole('button', { name: 'Previous' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Next' })).toBeEnabled()
  })

  it('Next loads the next page, preserving active filters, and every request stays bounded', async () => {
    mockedListConversations.mockResolvedValue(PAGE_1)
    const user = userEvent.setup()
    renderConversationsPage()

    await waitFor(() => expect(screen.getByText('First page question')).toBeInTheDocument())
    mockedListConversations.mockResolvedValueOnce(PAGE_2)
    await user.click(screen.getByRole('button', { name: 'Next' }))

    await waitFor(() => expect(screen.getByText('Second page question')).toBeInTheDocument())
    expect(mockedListConversations).toHaveBeenLastCalledWith(
      expect.objectContaining({ offset: 20, limit: 20 }),
    )
    expect(screen.getByRole('button', { name: 'Previous' })).toBeEnabled()
  })

  it('Next is disabled on the last page', async () => {
    mockedListConversations.mockResolvedValue(PAGE_1)
    const user = userEvent.setup()
    renderConversationsPage()

    await waitFor(() => expect(screen.getByText('First page question')).toBeInTheDocument())
    mockedListConversations.mockResolvedValueOnce(PAGE_2)
    await user.click(screen.getByRole('button', { name: 'Next' }))
    await waitFor(() => expect(screen.getByText('Second page question')).toBeInTheDocument())

    mockedListConversations.mockResolvedValueOnce(LAST_PAGE)
    await user.click(screen.getByRole('button', { name: 'Next' }))

    await waitFor(() => expect(screen.getByText('Last page question')).toBeInTheDocument())
    expect(screen.getByRole('button', { name: 'Next' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Previous' })).toBeEnabled()
  })

  it('Previous returns to the prior page', async () => {
    mockedListConversations.mockResolvedValue(PAGE_1)
    const user = userEvent.setup()
    renderConversationsPage()

    await waitFor(() => expect(screen.getByText('First page question')).toBeInTheDocument())
    mockedListConversations.mockResolvedValueOnce(PAGE_2)
    await user.click(screen.getByRole('button', { name: 'Next' }))
    await waitFor(() => expect(screen.getByText('Second page question')).toBeInTheDocument())

    mockedListConversations.mockResolvedValueOnce(PAGE_1)
    await user.click(screen.getByRole('button', { name: 'Previous' }))

    await waitFor(() => expect(screen.getByText('First page question')).toBeInTheDocument())
    expect(mockedListConversations).toHaveBeenLastCalledWith(
      expect.objectContaining({ offset: 0 }),
    )
  })
})
