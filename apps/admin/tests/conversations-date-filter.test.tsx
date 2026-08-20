import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import * as conversationsApi from '../src/api/conversations'
import { renderConversationsPage } from './testUtils'

vi.mock('../src/api/conversations')

const mockedListConversations = vi.mocked(conversationsApi.listConversations)

const RESPONSE = { items: [], total: 0, limit: 20, offset: 0 }

beforeEach(() => {
  mockedListConversations.mockReset()
  mockedListConversations.mockResolvedValue(RESPONSE)
})

describe('Conversations date filter', () => {
  it('setting From/To sends start_date as the bare date and end_date as end-of-day, resetting to the first page', async () => {
    const user = userEvent.setup()
    renderConversationsPage()

    await waitFor(() => expect(screen.getByLabelText('From')).toBeInTheDocument())
    await user.type(screen.getByLabelText('From'), '2026-08-01')

    await waitFor(() =>
      expect(mockedListConversations).toHaveBeenLastCalledWith(
        expect.objectContaining({ start_date: '2026-08-01', offset: 0 }),
      ),
    )

    await user.type(screen.getByLabelText('To'), '2026-08-20')

    await waitFor(() =>
      expect(mockedListConversations).toHaveBeenLastCalledWith(
        expect.objectContaining({
          start_date: '2026-08-01',
          end_date: '2026-08-20T23:59:59.999',
          offset: 0,
        }),
      ),
    )
  })

  it('shows an inline validation message and never submits when From is later than To', async () => {
    const user = userEvent.setup()
    renderConversationsPage()

    await waitFor(() => expect(screen.getByLabelText('From')).toBeInTheDocument())
    await user.type(screen.getByLabelText('To'), '2026-08-01')
    mockedListConversations.mockClear()
    await user.type(screen.getByLabelText('From'), '2026-08-20')

    expect(await screen.findByRole('alert')).toHaveTextContent(/on or before/i)
    expect(mockedListConversations).not.toHaveBeenCalled()
  })
})
