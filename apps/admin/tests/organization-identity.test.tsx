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

const TENANT_ID = '11111111-1111-1111-1111-111111111111'

beforeEach(async () => {
  mockedLogin.mockReset()
  mockedGetMe.mockReset()
  mockedLogin.mockResolvedValue({ access_token: 'token', token_type: 'bearer', expires_in: 3600 })
  mockedGetMe.mockResolvedValue({
    administrator: { id: 'admin-1', username: 'alice' },
    tenant: { id: TENANT_ID, name: 'Quickstart Co', slug: 'quickstart' },
  })
})

async function loginAndReachShell() {
  const user = userEvent.setup()
  const utils = renderApp(['/login'])
  await user.type(screen.getByLabelText('Username'), 'alice')
  await user.type(screen.getByLabelText('Password'), 'correct-password')
  await user.click(screen.getByRole('button', { name: 'Log in' }))
  await waitFor(() => expect(screen.getByText('Quickstart Co')).toBeInTheDocument())
  return utils
}

describe('organization identity', () => {
  it('shows tenant.name as the primary label and never renders tenant.id as primary text', async () => {
    await loginAndReachShell()

    expect(screen.getByText('Quickstart Co')).toBeInTheDocument()
    expect(screen.queryByText(TENANT_ID)).not.toBeInTheDocument()
    expect(document.body.innerHTML).not.toContain(TENANT_ID)
  })

  it('renders no tenant-switcher control anywhere in the shell', async () => {
    await loginAndReachShell()

    expect(screen.queryByRole('combobox')).not.toBeInTheDocument()
    expect(screen.queryByRole('searchbox')).not.toBeInTheDocument()
    expect(screen.queryByRole('listbox')).not.toBeInTheDocument()
  })
})
