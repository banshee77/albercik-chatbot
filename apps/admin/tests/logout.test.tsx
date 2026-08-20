import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import * as adminApi from '../src/api/admin'
import * as authApi from '../src/api/auth'
import { renderApp } from './testUtils'

vi.mock('../src/api/auth')
vi.mock('../src/api/admin')

const mockedLogin = vi.mocked(authApi.login)
const mockedGetMe = vi.mocked(adminApi.getMe)

beforeEach(() => {
  mockedLogin.mockReset()
  mockedGetMe.mockReset()
  mockedLogin.mockResolvedValue({ access_token: 'token', token_type: 'bearer', expires_in: 3600 })
  mockedGetMe.mockResolvedValue({
    administrator: { id: 'admin-1', username: 'alice' },
    tenant: { id: 'tenant-1', name: 'Quickstart Co', slug: 'quickstart' },
  })
})

describe('logout', () => {
  it('clears session/cached state, returns to /login, and never implies server-side revocation', async () => {
    const user = userEvent.setup()
    renderApp(['/login'])

    await user.type(screen.getByLabelText('Username'), 'alice')
    await user.type(screen.getByLabelText('Password'), 'correct-password')
    await user.click(screen.getByRole('button', { name: 'Log in' }))
    await waitFor(() => expect(screen.getByText('Quickstart Co')).toBeInTheDocument())

    await user.click(screen.getByRole('button', { name: 'Log out' }))

    await waitFor(() => expect(screen.getByLabelText('Username')).toBeInTheDocument())
    expect(screen.queryByText('Quickstart Co')).not.toBeInTheDocument()
    expect(document.body.innerHTML).not.toMatch(/revoked|invalidated on the server/i)
  })

  it('redirects to /login instead of showing stale content when returning to a protected route afterward', async () => {
    const user = userEvent.setup()
    const { router } = renderApp(['/login'])

    await user.type(screen.getByLabelText('Username'), 'alice')
    await user.type(screen.getByLabelText('Password'), 'correct-password')
    await user.click(screen.getByRole('button', { name: 'Log in' }))
    await waitFor(() => expect(screen.getByText('Quickstart Co')).toBeInTheDocument())

    await user.click(screen.getByRole('button', { name: 'Log out' }))
    await waitFor(() => expect(screen.getByLabelText('Username')).toBeInTheDocument())

    await router.navigate('/app')

    await waitFor(() => expect(screen.getByLabelText('Username')).toBeInTheDocument())
    expect(screen.queryByText('Quickstart Co')).not.toBeInTheDocument()
  })
})
