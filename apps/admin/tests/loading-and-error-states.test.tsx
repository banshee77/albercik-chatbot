import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { renderApp } from './testUtils'

describe('loading and error states', () => {
  let fetchMock: ReturnType<typeof vi.fn>

  beforeEach(() => {
    fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('shows a generic service-unavailable message, not a raw network error, when the backend is unreachable during login', async () => {
    fetchMock.mockRejectedValue(new TypeError('Failed to fetch'))

    const user = userEvent.setup()
    renderApp()

    await user.type(screen.getByLabelText('Username'), 'alice')
    await user.type(screen.getByLabelText('Password'), 'correct-password')
    await user.click(screen.getByRole('button', { name: 'Log in' }))

    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent(/reach the service/i)
    expect(alert.textContent).not.toMatch(/TypeError|Failed to fetch|fetch/i)
  })

  it('is fully operable using the keyboard alone, including submission', async () => {
    fetchMock.mockRejectedValue(new TypeError('Failed to fetch'))

    const user = userEvent.setup()
    renderApp()

    await user.tab()
    expect(screen.getByLabelText('Username')).toHaveFocus()
    await user.keyboard('alice')

    await user.tab()
    expect(screen.getByLabelText('Password')).toHaveFocus()
    await user.keyboard('correct-password')

    await user.tab()
    expect(screen.getByRole('button', { name: 'Log in' })).toHaveFocus()
    await user.keyboard('{Enter}')

    expect(await screen.findByRole('alert')).toHaveTextContent(/reach the service/i)
  })
})
