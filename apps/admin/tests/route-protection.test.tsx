import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import * as adminApi from '../src/api/admin'
import * as authApi from '../src/api/auth'
import { AuthContext } from '../src/auth/AuthContext'
import { ProtectedLayout } from '../src/routes/ProtectedLayout'
import { renderApp } from './testUtils'

vi.mock('../src/api/auth')
vi.mock('../src/api/admin')

const mockedLogin = vi.mocked(authApi.login)
const mockedGetMe = vi.mocked(adminApi.getMe)

const PROTECTED_PATHS = ['/app', '/app/knowledge', '/app/conversations', '/app/analytics']

beforeEach(() => {
  mockedLogin.mockReset()
  mockedGetMe.mockReset()
})

describe('route protection', () => {
  it.each(PROTECTED_PATHS)(
    'redirects an unauthenticated visitor requesting %s to /login',
    async (path) => {
      renderApp([path])

      await waitFor(() => expect(screen.getByLabelText('Username')).toBeInTheDocument())
    },
  )

  it('lets an authenticated administrator reach every /app route', async () => {
    mockedLogin.mockResolvedValue({ access_token: 'token', token_type: 'bearer', expires_in: 3600 })
    mockedGetMe.mockResolvedValue({
      administrator: { id: 'admin-1', username: 'alice' },
      tenant: { id: 'tenant-1', name: 'Quickstart Co', slug: 'quickstart' },
    })

    const user = userEvent.setup()
    const { router } = renderApp(['/login'])

    await user.type(screen.getByLabelText('Username'), 'alice')
    await user.type(screen.getByLabelText('Password'), 'correct-password')
    await user.click(screen.getByRole('button', { name: 'Log in' }))
    await waitFor(() => expect(screen.getByRole('heading', { name: /welcome/i })).toBeInTheDocument())

    await router.navigate('/app/knowledge')
    await waitFor(() => expect(screen.getByRole('heading', { name: 'Knowledge' })).toBeInTheDocument())

    await router.navigate('/app/conversations')
    await waitFor(() =>
      expect(screen.getByRole('heading', { name: 'Conversations' })).toBeInTheDocument(),
    )

    await router.navigate('/app/analytics')
    await waitFor(() => expect(screen.getByRole('heading', { name: 'Analytics' })).toBeInTheDocument())

    expect(screen.queryByLabelText('Username')).not.toBeInTheDocument()
  })

  it('renders only a loading state while AuthState.status is "initializing"', () => {
    render(
      <AuthContext.Provider
        value={{
          status: 'initializing',
          administrator: null,
          tenant: null,
          errorMessage: null,
          sessionExpired: false,
          login: vi.fn(),
          logout: vi.fn(),
        }}
      >
        <MemoryRouter initialEntries={['/app']}>
          <ProtectedLayout />
        </MemoryRouter>
      </AuthContext.Provider>,
    )

    expect(screen.getByRole('status')).toBeInTheDocument()
    expect(screen.queryByLabelText('Username')).not.toBeInTheDocument()
    expect(screen.queryByRole('navigation')).not.toBeInTheDocument()
  })
})
