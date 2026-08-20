import type { ApiError } from './types'

const BASE_URL: string = import.meta.env.VITE_SHIRUNO_API_URL ?? ''

const GENERIC_NETWORK_MESSAGE = "Can't reach the service right now. Please try again."
const GENERIC_SERVER_MESSAGE = 'Something went wrong. Please try again.'

let authToken: string | null = null
let unauthorizedHandler: (() => void) | null = null

/** In-memory only (research.md R1) — never written to localStorage/sessionStorage. */
export function setAuthToken(token: string | null): void {
  authToken = token
}

/** Registered once by AuthProvider; invoked before a 401/403 is rejected (research.md R7). */
export function setUnauthorizedHandler(handler: (() => void) | null): void {
  unauthorizedHandler = handler
}

async function safeErrorMessage(response: Response): Promise<string> {
  try {
    const body: unknown = await response.json()
    if (
      body !== null &&
      typeof body === 'object' &&
      'detail' in body &&
      typeof (body as { detail: unknown }).detail === 'string'
    ) {
      return (body as { detail: string }).detail
    }
  } catch {
    // Response body wasn't JSON — fall through to the generic message.
  }
  return GENERIC_SERVER_MESSAGE
}

export async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const hadToken = authToken !== null

  const headers = new Headers(init.headers)
  // A FormData body (file upload/replace) needs the browser to set its own
  // multipart/form-data boundary — setting Content-Type manually here would
  // break that boundary and the backend's UploadFile parsing.
  if (!(init.body instanceof FormData)) {
    headers.set('Content-Type', 'application/json')
  }
  if (authToken) {
    headers.set('Authorization', `Bearer ${authToken}`)
  }

  let response: Response
  try {
    response = await fetch(`${BASE_URL}${path}`, { ...init, headers })
  } catch {
    // Network-level failure (backend unreachable) — never a raw fetch
    // TypeError or browser error string reaches UI code (FR-018, FR-019).
    const error: ApiError = { message: GENERIC_NETWORK_MESSAGE }
    throw error
  }

  if (!response.ok) {
    const message = await safeErrorMessage(response)
    // Only a request that actually carried a token can be "a session that
    // stopped being valid" (US6) — an unauthenticated request (e.g. the
    // login attempt itself) rejecting with 401 is simply "wrong
    // credentials" (US1), never a session-expired case.
    if (hadToken && (response.status === 401 || response.status === 403)) {
      unauthorizedHandler?.()
    }
    const error: ApiError = { message, status: response.status }
    throw error
  }

  // A 204 (e.g. DELETE) has no body — calling response.json() on it throws.
  if (response.status === 204) {
    return undefined as T
  }

  return (await response.json()) as T
}
