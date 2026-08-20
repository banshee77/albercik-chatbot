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

const DOCUMENT = {
  id: 'doc-1',
  filename: 'treningi.pdf',
  content_type: 'text/plain',
  status: 'ready',
  uploaded_at: '2026-08-20T10:00:00Z',
  updated_at: '2026-08-20T10:00:00Z',
  indexed_at: '2026-08-20T10:00:05Z',
  error_message: null,
}

const HEALTH = {
  documents: { total: 1, ready: 1, processing: 0, failed: 0 },
  chunks: 3,
  ready_for_chat: true,
  last_indexed_at: '2026-08-20T10:00:05Z',
}

describe('Knowledge — session expiration', () => {
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

  it('redirects to /login during the initial Knowledge page load', async () => {
    fetchMock
      .mockResolvedValueOnce(jsonResponse({ access_token: 'token', token_type: 'bearer', expires_in: 3600 }))
      .mockResolvedValueOnce(jsonResponse(TENANT_ME))

    const user = userEvent.setup()
    await logIn(user)

    // The Knowledge page's own list/health requests both come back 401.
    fetchMock.mockResolvedValue(jsonResponse({ detail: 'Authentication required or invalid.' }, 401))

    await user.click(within(screen.getByRole('navigation', { name: 'Primary' })).getByRole('link', { name: 'Knowledge' }))

    await waitFor(() => expect(screen.getByLabelText('Username')).toBeInTheDocument())
    expect(screen.getByText(/session has expired/i)).toBeInTheDocument()
    expect(screen.queryByText('treningi.pdf')).not.toBeInTheDocument()
  })

  it('redirects to /login during a mutation, with no stale success indication', async () => {
    fetchMock
      .mockResolvedValueOnce(jsonResponse({ access_token: 'token', token_type: 'bearer', expires_in: 3600 }))
      .mockResolvedValueOnce(jsonResponse(TENANT_ME))
      .mockResolvedValueOnce(jsonResponse([DOCUMENT]))
      .mockResolvedValueOnce(jsonResponse(HEALTH))

    const user = userEvent.setup()
    await logIn(user)
    await user.click(within(screen.getByRole('navigation', { name: 'Primary' })).getByRole('link', { name: 'Knowledge' }))
    await waitFor(() => expect(screen.getByText('treningi.pdf')).toBeInTheDocument())

    await user.click(screen.getByRole('button', { name: 'treningi.pdf' }))
    await screen.findByRole('region', { name: /treningi\.pdf/i })

    // The re-index mutation comes back rejected for authentication reasons.
    fetchMock.mockResolvedValue(jsonResponse({ detail: 'Authentication required or invalid.' }, 401))
    await user.click(screen.getByRole('button', { name: 'Rebuild search index' }))

    await waitFor(() => expect(screen.getByLabelText('Username')).toBeInTheDocument())
    expect(screen.getByText(/session has expired/i)).toBeInTheDocument()
    expect(screen.queryByText('Search index rebuilt.')).not.toBeInTheDocument()
    expect(screen.queryByText('treningi.pdf')).not.toBeInTheDocument()
  })
})
