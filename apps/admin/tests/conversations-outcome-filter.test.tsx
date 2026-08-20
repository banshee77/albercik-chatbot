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

describe('Conversations outcome filter', () => {
  it.each([
    ['Answered', 'grounded'],
    ['Knowledge gap', 'insufficient_information'],
    ['Out of scope', 'out_of_scope'],
    ['Unavailable', 'unavailable'],
    ['Small talk', 'small_talk'],
  ])('selecting %s calls listConversations() with outcome=%s and resets to the first page', async (label, value) => {
    const user = userEvent.setup()
    renderConversationsPage()

    await waitFor(() => expect(screen.getByLabelText('Outcome')).toBeInTheDocument())
    await user.selectOptions(screen.getByLabelText('Outcome'), label)

    await waitFor(() =>
      expect(mockedListConversations).toHaveBeenLastCalledWith(
        expect.objectContaining({ outcome: value, offset: 0 }),
      ),
    )
  })

  it('selecting All omits the outcome param entirely', async () => {
    const user = userEvent.setup()
    renderConversationsPage()

    await waitFor(() => expect(screen.getByLabelText('Outcome')).toBeInTheDocument())
    await user.selectOptions(screen.getByLabelText('Outcome'), 'Answered')
    await waitFor(() =>
      expect(mockedListConversations).toHaveBeenLastCalledWith(
        expect.objectContaining({ outcome: 'grounded' }),
      ),
    )

    await user.selectOptions(screen.getByLabelText('Outcome'), 'All')
    await waitFor(() =>
      expect(mockedListConversations).toHaveBeenLastCalledWith(
        expect.objectContaining({ outcome: undefined }),
      ),
    )
  })
})
