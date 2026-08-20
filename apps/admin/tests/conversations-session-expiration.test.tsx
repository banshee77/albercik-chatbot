import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { renderApp } from './testUtils'

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

const TENANT_ME = {
  administrator: { id: 'admin-1', username: 'alice' },
  tenant: { id: 'tenant-1', name: 'Quickstart Co', slug: 'quickstart' },
}

const CONVERSATION_SUMMARY = {
  id: 'conv-1',
  request_id: 'req-1',
  question: 'When are beginner classes?',
  outcome: 'grounded',
  created_at: '2026-08-20T10:15:00Z',
  latency_ms: 1180,
}

const LIST_RESPONSE = { items: [CONVERSATION_SUMMARY], total: 1, limit: 20, offset: 0 }

describe('Conversations — session expiration', () => {
  let fetchMock: ReturnType<typeof vi.fn>

  beforeEach(() => {
    fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  async function logIn(user: ReturnType<typeof userEvent.setup>) {
    renderApp(['/login'])
    await user.type(screen.getByLabelText('Username'), 'alice')
    await user.type(screen.getByLabelText('Password'), 'correct-password')
    await user.click(screen.getByRole('button', { name: 'Log in' }))
    await waitFor(() => expect(screen.getByRole('navigation', { name: 'Primary' })).toBeInTheDocument())
  }

  it('redirects to /login during the initial Conversations list load', async () => {
    fetchMock
      .mockResolvedValueOnce(jsonResponse({ access_token: 'token', token_type: 'bearer', expires_in: 3600 }))
      .mockResolvedValueOnce(jsonResponse(TENANT_ME))

    const user = userEvent.setup()
    await logIn(user)

    fetchMock.mockResolvedValue(jsonResponse({ detail: 'Authentication required or invalid.' }, 401))

    await user.click(
      within(screen.getByRole('navigation', { name: 'Primary' })).getByRole('link', {
        name: 'Conversations',
      }),
    )

    await waitFor(() => expect(screen.getByLabelText('Username')).toBeInTheDocument())
    expect(screen.getByText(/session has expired/i)).toBeInTheDocument()
    expect(screen.queryByText('When are beginner classes?')).not.toBeInTheDocument()
  })

  it('redirects to /login when opening a conversation is rejected for authentication reasons', async () => {
    fetchMock
      .mockResolvedValueOnce(jsonResponse({ access_token: 'token', token_type: 'bearer', expires_in: 3600 }))
      .mockResolvedValueOnce(jsonResponse(TENANT_ME))
      .mockResolvedValueOnce(jsonResponse(LIST_RESPONSE))

    const user = userEvent.setup()
    await logIn(user)
    await user.click(
      within(screen.getByRole('navigation', { name: 'Primary' })).getByRole('link', {
        name: 'Conversations',
      }),
    )
    await waitFor(() => expect(screen.getByText('When are beginner classes?')).toBeInTheDocument())

    fetchMock.mockResolvedValue(jsonResponse({ detail: 'Authentication required or invalid.' }, 401))
    await user.click(screen.getByRole('button', { name: 'When are beginner classes?' }))

    await waitFor(() => expect(screen.getByLabelText('Username')).toBeInTheDocument())
    expect(screen.getByText(/session has expired/i)).toBeInTheDocument()
    expect(screen.queryByText('When are beginner classes?')).not.toBeInTheDocument()
  })
})
