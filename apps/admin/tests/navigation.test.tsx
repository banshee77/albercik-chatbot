import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import * as adminApi from '../src/api/admin'
import * as authApi from '../src/api/auth'
import * as knowledgeApi from '../src/api/knowledge'
import { renderApp } from './testUtils'

vi.mock('../src/api/auth')
vi.mock('../src/api/admin')
vi.mock('../src/api/knowledge')

const mockedLogin = vi.mocked(authApi.login)
const mockedGetMe = vi.mocked(adminApi.getMe)
const mockedListDocuments = vi.mocked(knowledgeApi.listDocuments)
const mockedGetKnowledgeHealth = vi.mocked(knowledgeApi.getKnowledgeHealth)

beforeEach(() => {
  mockedLogin.mockReset()
  mockedGetMe.mockReset()
  mockedListDocuments.mockReset()
  mockedGetKnowledgeHealth.mockReset()
  mockedLogin.mockResolvedValue({ access_token: 'token', token_type: 'bearer', expires_in: 3600 })
  mockedGetMe.mockResolvedValue({
    administrator: { id: 'admin-1', username: 'alice' },
    tenant: { id: 'tenant-1', name: 'Quickstart Co', slug: 'quickstart' },
  })
  mockedListDocuments.mockResolvedValue([])
  mockedGetKnowledgeHealth.mockResolvedValue({
    documents: { total: 0, ready: 0, processing: 0, failed: 0 },
    chunks: 0,
    ready_for_chat: false,
    last_indexed_at: null,
  })
})

async function login(user: ReturnType<typeof userEvent.setup>) {
  renderApp(['/login'])
  await user.type(screen.getByLabelText('Username'), 'alice')
  await user.type(screen.getByLabelText('Password'), 'correct-password')
  await user.click(screen.getByRole('button', { name: 'Log in' }))
  await waitFor(() => expect(screen.getByRole('heading', { name: /welcome/i })).toBeInTheDocument())
}

describe('primary navigation', () => {
  it('contains exactly Knowledge, Conversations, and Analytics — no other entries', async () => {
    const user = userEvent.setup()
    await login(user)

    const nav = screen.getByRole('navigation', { name: 'Primary' })
    const links = within(nav).getAllByRole('link')
    expect(links.map((link) => link.textContent)).toEqual(['Knowledge', 'Conversations', 'Analytics'])
  })

  it('reaches Knowledge, Conversations, and Analytics from primary navigation', async () => {
    const user = userEvent.setup()
    await login(user)

    const nav = screen.getByRole('navigation', { name: 'Primary' })

    await user.click(within(nav).getByRole('link', { name: 'Knowledge' }))
    await waitFor(() => expect(screen.getByRole('heading', { name: 'Knowledge' })).toBeInTheDocument())

    await user.click(within(nav).getByRole('link', { name: 'Conversations' }))
    await waitFor(() =>
      expect(screen.getByRole('heading', { name: 'Conversations' })).toBeInTheDocument(),
    )

    await user.click(within(nav).getByRole('link', { name: 'Analytics' }))
    await waitFor(() => expect(screen.getByRole('heading', { name: 'Analytics' })).toBeInTheDocument())
  })

  it('is reachable and activatable using the keyboard alone', async () => {
    const user = userEvent.setup()
    await login(user)

    const nav = screen.getByRole('navigation', { name: 'Primary' })
    const knowledgeLink = within(nav).getByRole('link', { name: 'Knowledge' })

    knowledgeLink.focus()
    expect(knowledgeLink).toHaveFocus()
    await user.keyboard('{Enter}')

    await waitFor(() => expect(screen.getByRole('heading', { name: 'Knowledge' })).toBeInTheDocument())
  })
})
