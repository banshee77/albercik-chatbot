import { createContext, useContext } from 'react'
import type { AdministratorIdentity, OrganizationIdentity } from '../api/types'

export type AuthStatus = 'initializing' | 'unauthenticated' | 'authenticated' | 'error'

export interface AuthState {
  status: AuthStatus
  administrator: AdministratorIdentity | null
  tenant: OrganizationIdentity | null
  errorMessage: string | null
  /** Set only when the previous session was cleared by a mid-use auth
   * failure (US6), never on a fresh visit or a deliberate logout. */
  sessionExpired: boolean
}

export interface AuthContextValue extends AuthState {
  login: (username: string, password: string) => Promise<void>
  logout: () => void
}

export const AuthContext = createContext<AuthContextValue | null>(null)

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext)
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider')
  }
  return context
}
