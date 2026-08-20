import { useEffect, useState, type ReactNode } from 'react'
import { getMe } from '../api/admin'
import { login as loginRequest } from '../api/auth'
import { setAuthToken, setUnauthorizedHandler } from '../api/client'
import type { ApiError } from '../api/types'
import { AuthContext, type AuthState } from './AuthContext'

const GENERIC_LOGIN_ERROR = 'Invalid username or password.'

const initialState: AuthState = {
  status: 'unauthenticated',
  administrator: null,
  tenant: null,
  errorMessage: null,
  sessionExpired: false,
}

function isApiError(value: unknown): value is ApiError {
  return typeof value === 'object' && value !== null && 'message' in value
}

export function AuthProvider({ children }: { children: ReactNode }) {
  // No persisted token to recover (research.md R1) — a full page load
  // always starts unauthenticated, never silently re-entering
  // "authenticated". There is no async bootstrap check to perform, so
  // this is resolved at construction time rather than via an effect;
  // "initializing" remains a valid, renderable AuthState for whichever
  // future feature adds a real session-recovery check.
  const [state, setState] = useState<AuthState>(initialState)

  useEffect(() => {
    setUnauthorizedHandler(() => {
      setAuthToken(null)
      setState({
        status: 'unauthenticated',
        administrator: null,
        tenant: null,
        errorMessage: null,
        sessionExpired: true,
      })
    })
    return () => setUnauthorizedHandler(null)
  }, [])

  async function login(username: string, password: string): Promise<void> {
    try {
      const { access_token } = await loginRequest(username, password)
      setAuthToken(access_token)
      const me = await getMe()
      setState({
        status: 'authenticated',
        administrator: me.administrator,
        tenant: me.tenant,
        errorMessage: null,
        sessionExpired: false,
      })
    } catch (err) {
      setAuthToken(null)
      const message = isApiError(err) ? err.message : GENERIC_LOGIN_ERROR
      setState({
        status: 'error',
        administrator: null,
        tenant: null,
        errorMessage: message,
        sessionExpired: false,
      })
    }
  }

  function logout(): void {
    setAuthToken(null)
    setState({
      status: 'unauthenticated',
      administrator: null,
      tenant: null,
      errorMessage: null,
      sessionExpired: false,
    })
  }

  return (
    <AuthContext.Provider value={{ ...state, login, logout }}>{children}</AuthContext.Provider>
  )
}
