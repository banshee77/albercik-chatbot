import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { getConversation, listConversations } from '../src/api/conversations'
import { setAuthToken } from '../src/api/client'

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

const LIST_RESPONSE = { items: [], total: 0, limit: 20, offset: 0 }

const DETAIL_RESPONSE = {
  id: 'conv-1',
  request_id: 'req-1',
  question: 'When are beginner classes?',
  answer: 'Beginner classes run on Tuesdays.',
  outcome: 'grounded',
  created_at: '2026-08-20T10:15:00Z',
  latency_ms: 1180,
  sources: [{ document_id: 'doc-1', label: 'treningi.txt' }],
  provider_name: 'ollama',
  provider_model: 'qwen3:8b',
  input_tokens: 512,
  output_tokens: 96,
  safe_failure_category: null,
}

describe('conversations.ts', () => {
  let fetchMock: ReturnType<typeof vi.fn>

  beforeEach(() => {
    fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)
    setAuthToken('a-real-token')
  })

  afterEach(() => {
    vi.unstubAllGlobals()
    setAuthToken(null)
  })

  function calledUrl(): string {
    return (fetchMock.mock.calls[0] as [string, RequestInit | undefined])[0]
  }

  function assertNoTenantIdentifier(): void {
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit | undefined]
    expect(url).not.toMatch(/tenant/i)
    const body = init?.body
    if (typeof body === 'string') {
      expect(body).not.toMatch(/tenant/i)
    }
    expect(Array.from(new Headers(init?.headers).keys())).not.toContain('x-tenant-id')
  }

  it('listConversations() with no params issues a bare GET with no query string', async () => {
    fetchMock.mockResolvedValue(jsonResponse(LIST_RESPONSE))
    await listConversations()
    expect(calledUrl()).toMatch(/\/api\/v1\/admin\/conversations$/)
    assertNoTenantIdentifier()
  })

  it('getConversation(id) issues GET /api/v1/admin/conversations/{id}', async () => {
    fetchMock.mockResolvedValue(jsonResponse(DETAIL_RESPONSE))
    await getConversation('conv-1')
    expect(calledUrl()).toMatch(/\/api\/v1\/admin\/conversations\/conv-1$/)
    assertNoTenantIdentifier()
  })

  it('constructs the query string for a combination of q/outcome/start_date/end_date', async () => {
    fetchMock.mockResolvedValue(jsonResponse(LIST_RESPONSE))
    await listConversations({
      q: 'swallow',
      outcome: 'insufficient_information',
      start_date: '2026-08-01',
      end_date: '2026-08-20T23:59:59.999',
      limit: 20,
      offset: 0,
    })
    const url = new URL(calledUrl())
    expect(url.searchParams.get('q')).toBe('swallow')
    expect(url.searchParams.get('outcome')).toBe('insufficient_information')
    expect(url.searchParams.get('start_date')).toBe('2026-08-01')
    expect(url.searchParams.get('end_date')).toBe('2026-08-20T23:59:59.999')
    expect(url.searchParams.get('limit')).toBe('20')
    expect(url.searchParams.get('offset')).toBe('0')
  })

  it('omits each param that is undefined rather than sending an empty value', async () => {
    fetchMock.mockResolvedValue(jsonResponse(LIST_RESPONSE))
    await listConversations({ outcome: 'grounded' })
    const url = new URL(calledUrl())
    expect(url.searchParams.has('q')).toBe(false)
    expect(url.searchParams.get('outcome')).toBe('grounded')
    expect(url.searchParams.has('start_date')).toBe(false)
    expect(url.searchParams.has('end_date')).toBe(false)
  })
})
