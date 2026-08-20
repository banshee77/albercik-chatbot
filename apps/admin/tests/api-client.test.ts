import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { getMe } from '../src/api/admin'
import { login } from '../src/api/auth'
import { setAuthToken } from '../src/api/client'

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

describe('api client — no client-supplied tenant identifier', () => {
  let fetchMock: ReturnType<typeof vi.fn>

  beforeEach(() => {
    fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)
    setAuthToken(null)
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('never sends a tenant identifier on the login request', async () => {
    fetchMock.mockResolvedValue(
      jsonResponse({ access_token: 'token', token_type: 'bearer', expires_in: 3600 }),
    )

    await login('alice', 'correct-password')

    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit]
    expect(url).not.toMatch(/tenant/i)
    expect(String(init.body)).not.toMatch(/tenant/i)
    expect(Array.from(new Headers(init.headers).keys())).not.toContain('x-tenant-id')
  })

  it('never sends a tenant identifier on the /admin/me request', async () => {
    setAuthToken('a-real-token')
    fetchMock.mockResolvedValue(
      jsonResponse({
        administrator: { id: 'admin-1', username: 'alice' },
        tenant: { id: 'tenant-1', name: 'Quickstart Co', slug: 'quickstart' },
      }),
    )

    await getMe()

    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit | undefined]
    expect(url).not.toMatch(/tenant/i)
    expect(Array.from(new Headers(init?.headers).keys())).not.toContain('x-tenant-id')
  })
})
