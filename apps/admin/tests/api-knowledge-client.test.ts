import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import {
  deleteDocument,
  getDocument,
  getKnowledgeHealth,
  listDocuments,
  reindexDocument,
  replaceDocument,
  uploadDocument,
} from '../src/api/knowledge'
import { setAuthToken } from '../src/api/client'

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
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
  chunks: 4,
  ready_for_chat: true,
  last_indexed_at: '2026-08-20T10:00:05Z',
}

describe('knowledge.ts — no client-supplied tenant identifier', () => {
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

  function assertNoTenantIdentifier(): void {
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit | undefined]
    expect(url).not.toMatch(/tenant/i)
    const body = init?.body
    if (typeof body === 'string') {
      expect(body).not.toMatch(/tenant/i)
    }
    expect(Array.from(new Headers(init?.headers).keys())).not.toContain('x-tenant-id')
  }

  it('listDocuments()', async () => {
    fetchMock.mockResolvedValue(jsonResponse([DOCUMENT]))
    await listDocuments()
    assertNoTenantIdentifier()
  })

  it('getKnowledgeHealth()', async () => {
    fetchMock.mockResolvedValue(jsonResponse(HEALTH))
    await getKnowledgeHealth()
    assertNoTenantIdentifier()
  })

  it('getDocument(id)', async () => {
    fetchMock.mockResolvedValue(jsonResponse(DOCUMENT))
    await getDocument('doc-1')
    assertNoTenantIdentifier()
  })

  it('uploadDocument(file)', async () => {
    fetchMock.mockResolvedValue(jsonResponse(DOCUMENT, 201))
    await uploadDocument(new File(['hello'], 'hello.txt', { type: 'text/plain' }))
    assertNoTenantIdentifier()
  })

  it('replaceDocument(id, file)', async () => {
    fetchMock.mockResolvedValue(jsonResponse(DOCUMENT, 201))
    await replaceDocument('doc-1', new File(['hello'], 'hello.txt', { type: 'text/plain' }))
    assertNoTenantIdentifier()
  })

  it('reindexDocument(id)', async () => {
    fetchMock.mockResolvedValue(jsonResponse(DOCUMENT))
    await reindexDocument('doc-1')
    assertNoTenantIdentifier()
  })

  it('deleteDocument(id)', async () => {
    fetchMock.mockResolvedValue(new Response(null, { status: 204 }))
    await deleteDocument('doc-1')
    assertNoTenantIdentifier()
  })
})
