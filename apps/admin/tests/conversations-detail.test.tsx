import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import * as conversationsApi from '../src/api/conversations'
import { renderConversationsPage } from './testUtils'

vi.mock('../src/api/conversations')

const mockedListConversations = vi.mocked(conversationsApi.listConversations)
const mockedGetConversation = vi.mocked(conversationsApi.getConversation)

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
  sources: [
    { document_id: 'doc-1', label: 'treningi.txt' },
    { document_id: 'doc-2', label: 'kontakt.txt' },
  ],
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
})

async function openDetail(user: ReturnType<typeof userEvent.setup>) {
  renderConversationsPage()
  const row = await screen.findByRole('button', { name: 'When are beginner classes?' })
  await user.click(row)
  return row
}

async function findDetailRegion() {
  return screen.findByRole('region', { name: 'Conversation detail' })
}

describe('Conversation detail — grounded', () => {
  it('loads detail independently of the list, showing question/answer/sources/metadata', async () => {
    mockedGetConversation.mockResolvedValue(GROUNDED_DETAIL)
    const user = userEvent.setup()

    await openDetail(user)

    // List stays rendered — no page-wide loading state.
    expect(screen.getByRole('button', { name: 'When are beginner classes?' })).toBeInTheDocument()

    const detail = await findDetailRegion()
    await waitFor(() =>
      expect(within(detail).getByText('Beginner classes run on Tuesdays at 6pm.')).toBeInTheDocument(),
    )
    expect(within(detail).getByText('treningi.txt')).toBeInTheDocument()
    expect(within(detail).getByText('kontakt.txt')).toBeInTheDocument()
    expect(within(detail).getByText('1180 ms')).toBeInTheDocument()
    expect(within(detail).getByText('ollama')).toBeInTheDocument()
    expect(within(detail).getByText('qwen3:8b')).toBeInTheDocument()
  })

  it('renders no Sources section when the historical snapshot is an empty array', async () => {
    mockedGetConversation.mockResolvedValue({ ...GROUNDED_DETAIL, sources: [] })
    const user = userEvent.setup()

    await openDetail(user)

    const detail = await findDetailRegion()
    await waitFor(() =>
      expect(
        within(detail).getByText('Beginner classes run on Tuesdays at 6pm.'),
      ).toBeInTheDocument(),
    )
    expect(within(detail).queryByRole('region', { name: 'Sources' })).not.toBeInTheDocument()
  })

  it('copies the request ID to the clipboard from Technical details', async () => {
    mockedGetConversation.mockResolvedValue(GROUNDED_DETAIL)
    const user = userEvent.setup()
    // user-event installs its own Clipboard stub on setup() — spy on that
    // rather than replacing `navigator.clipboard` ourselves (research.md R13).
    const writeText = vi.spyOn(navigator.clipboard, 'writeText')

    await openDetail(user)

    const detail = await findDetailRegion()
    await waitFor(() => expect(within(detail).getByText('req-1')).toBeInTheDocument())
    await user.click(within(detail).getByRole('button', { name: 'Copy' }))

    expect(writeText).toHaveBeenCalledWith('req-1')
  })
})

describe('Conversation detail — other outcomes', () => {
  it('renders a Knowledge gap state for insufficient_information, without fabricated sources', async () => {
    mockedGetConversation.mockResolvedValue({
      ...GROUNDED_DETAIL,
      outcome: 'insufficient_information',
      sources: null,
      provider_name: null,
      provider_model: null,
      input_tokens: null,
      output_tokens: null,
    })
    const user = userEvent.setup()

    await openDetail(user)

    const detail = await findDetailRegion()
    await waitFor(() => expect(within(detail).getByText('Knowledge gap')).toBeInTheDocument())
    expect(within(detail).queryByRole('region', { name: 'Sources' })).not.toBeInTheDocument()
  })

  it('renders a neutral Out of scope label', async () => {
    mockedGetConversation.mockResolvedValue({
      ...GROUNDED_DETAIL,
      outcome: 'out_of_scope',
      sources: null,
      provider_name: null,
      provider_model: null,
      input_tokens: null,
      output_tokens: null,
    })
    const user = userEvent.setup()

    await openDetail(user)

    const detail = await findDetailRegion()
    await waitFor(() => expect(within(detail).getByText('Out of scope')).toBeInTheDocument())
  })

  it('renders Assistant unavailable with a mapped safe-category message when present', async () => {
    mockedGetConversation.mockResolvedValue({
      ...GROUNDED_DETAIL,
      outcome: 'unavailable',
      sources: null,
      provider_name: null,
      provider_model: null,
      input_tokens: null,
      output_tokens: null,
      safe_failure_category: 'provider_error',
    })
    const user = userEvent.setup()

    await openDetail(user)

    const detail = await findDetailRegion()
    await waitFor(() =>
      expect(within(detail).getByText('Assistant unavailable')).toBeInTheDocument(),
    )
    expect(
      within(detail).getByText('The assistant provider was unavailable.'),
    ).toBeInTheDocument()
  })

  it('renders the generic Assistant unavailable state alone when no safe category is present', async () => {
    mockedGetConversation.mockResolvedValue({
      ...GROUNDED_DETAIL,
      outcome: 'unavailable',
      sources: null,
      provider_name: null,
      provider_model: null,
      input_tokens: null,
      output_tokens: null,
      safe_failure_category: null,
    })
    const user = userEvent.setup()

    await openDetail(user)

    const detail = await findDetailRegion()
    await waitFor(() =>
      expect(within(detail).getByText('Assistant unavailable')).toBeInTheDocument(),
    )
  })

  it('renders small_talk naturally with no fabricated provider/token data', async () => {
    mockedGetConversation.mockResolvedValue({
      ...GROUNDED_DETAIL,
      outcome: 'small_talk',
      sources: null,
      provider_name: null,
      provider_model: null,
      input_tokens: null,
      output_tokens: null,
    })
    const user = userEvent.setup()

    await openDetail(user)

    const detail = await findDetailRegion()
    await waitFor(() => expect(within(detail).getByText('Small talk')).toBeInTheDocument())
    expect(within(detail).queryByRole('region', { name: 'Operational metadata' })).not.toBeInTheDocument()
  })

  it('shows a safe detail-level error while the list remains usable, never implying a cross-tenant record', async () => {
    mockedGetConversation.mockRejectedValue({ message: "Couldn't load this conversation." })
    const user = userEvent.setup()

    await openDetail(user)

    expect(await screen.findByRole('alert')).toBeInTheDocument()
    // The list is still fully usable.
    expect(screen.getByRole('button', { name: 'When are beginner classes?' })).toBeInTheDocument()
  })
})

describe('Conversation detail — closing', () => {
  it('clears the selection without altering the already-loaded list', async () => {
    mockedGetConversation.mockResolvedValue(GROUNDED_DETAIL)
    const user = userEvent.setup()

    await openDetail(user)

    const detail = await findDetailRegion()
    await waitFor(() =>
      expect(
        within(detail).getByText('Beginner classes run on Tuesdays at 6pm.'),
      ).toBeInTheDocument(),
    )
    await user.click(within(detail).getByRole('button', { name: 'Close' }))

    expect(screen.queryByRole('region', { name: 'Conversation detail' })).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'When are beginner classes?' })).toBeInTheDocument()
  })
})
