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
})

describe('LoginPage', () => {
  it('renders labeled, accessible username and password fields', () => {
    renderApp()

    expect(screen.getByLabelText('Username')).toBeInTheDocument()
    expect(screen.getByLabelText('Password')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Log in' })).toBeInTheDocument()
  })

  it('lands on the shell with organization identity after valid credentials', async () => {
    mockedLogin.mockResolvedValue({ access_token: 'a-real-token', token_type: 'bearer', expires_in: 3600 })
    mockedGetMe.mockResolvedValue({
      administrator: { id: 'admin-1', username: 'alice' },
      tenant: { id: 'tenant-1', name: 'Quickstart Co', slug: 'quickstart' },
    })

    const user = userEvent.setup()
    renderApp()

    await user.type(screen.getByLabelText('Username'), 'alice')
    await user.type(screen.getByLabelText('Password'), 'correct-password')
    await user.click(screen.getByRole('button', { name: 'Log in' }))

    await waitFor(() => expect(screen.getByText('Quickstart Co')).toBeInTheDocument())
    expect(mockedGetMe).toHaveBeenCalledTimes(1)
  })

  it('shows one generic authentication-failure message for invalid credentials', async () => {
    mockedLogin.mockRejectedValue({ message: 'Invalid username or password.', status: 401 })

    const user = userEvent.setup()
    renderApp()

    await user.type(screen.getByLabelText('Username'), 'alice')
    await user.type(screen.getByLabelText('Password'), 'wrong-password')
    await user.click(screen.getByRole('button', { name: 'Log in' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('Invalid username or password.')
    expect(mockedGetMe).not.toHaveBeenCalled()
  })

  it('never renders the submitted token/credential value anywhere in the DOM', async () => {
    mockedLogin.mockResolvedValue({ access_token: 'super-secret-token-value', token_type: 'bearer', expires_in: 3600 })
    mockedGetMe.mockResolvedValue({
      administrator: { id: 'admin-1', username: 'alice' },
      tenant: { id: 'tenant-1', name: 'Quickstart Co', slug: 'quickstart' },
    })

    const user = userEvent.setup()
    renderApp()

    await user.type(screen.getByLabelText('Username'), 'alice')
    await user.type(screen.getByLabelText('Password'), 'correct-password')
    await user.click(screen.getByRole('button', { name: 'Log in' }))

    await waitFor(() => expect(screen.getByText('Quickstart Co')).toBeInTheDocument())
    expect(document.body.innerHTML).not.toContain('super-secret-token-value')
    expect(document.body.innerHTML).not.toContain('correct-password')
  })
})
