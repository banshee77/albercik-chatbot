import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { getMe } from '../src/api/admin'
import { renderApp } from './testUtils'

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

describe('mid-session authentication failure', () => {
  let fetchMock: ReturnType<typeof vi.fn>

  beforeEach(() => {
    fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('clears AuthState and redirects to /login with a generic session-expired message, hiding prior organization data', async () => {
    fetchMock
      .mockResolvedValueOnce(
        jsonResponse({ access_token: 'token', token_type: 'bearer', expires_in: 3600 }),
      )
      .mockResolvedValueOnce(
        jsonResponse({
          administrator: { id: 'admin-1', username: 'alice' },
          tenant: { id: 'tenant-1', name: 'Quickstart Co', slug: 'quickstart' },
        }),
      )

    const user = userEvent.setup()
    renderApp(['/login'])

    await user.type(screen.getByLabelText('Username'), 'alice')
    await user.type(screen.getByLabelText('Password'), 'correct-password')
    await user.click(screen.getByRole('button', { name: 'Log in' }))
    await waitFor(() => expect(screen.getByText('Quickstart Co')).toBeInTheDocument())

    // Simulate the next authenticated request coming back rejected for
    // authentication reasons — going through the real, centralized
    // client.ts 401/403 path (T006, T031), the same one any future
    // authenticated call in this shell shares.
    fetchMock.mockResolvedValueOnce(
      jsonResponse({ detail: 'Authentication required or invalid.' }, 401),
    )
    await getMe().catch(() => {})

    await waitFor(() => expect(screen.getByLabelText('Username')).toBeInTheDocument())
    expect(screen.getByText(/session has expired/i)).toBeInTheDocument()
    expect(screen.queryByText('Quickstart Co')).not.toBeInTheDocument()
    expect(document.body.innerHTML).not.toContain('Quickstart Co')
  })
})
