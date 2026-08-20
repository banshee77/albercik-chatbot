import { render } from '@testing-library/react'
import { createMemoryRouter, RouterProvider } from 'react-router'
import { AuthProvider } from '../src/auth/AuthProvider'
import { ConversationsPage } from '../src/routes/ConversationsPage'
import { KnowledgePage } from '../src/routes/KnowledgePage'
import { routeConfig } from '../src/routeConfig'

export function renderApp(initialEntries: string[] = ['/login']) {
  const router = createMemoryRouter(routeConfig, { initialEntries })
  const result = render(
    <AuthProvider>
      <RouterProvider router={router} />
    </AuthProvider>,
  )
  return { router, ...result }
}

/** KnowledgePage reads no auth context directly (Header/Nav own that,
 * via ProtectedLayout) — a direct render is sufficient and avoids the
 * unrelated setup a full route render would need. */
export function renderKnowledgePage() {
  return render(<KnowledgePage />)
}

/** ConversationsPage reads no auth context directly either — same
 * reasoning as renderKnowledgePage() above. */
export function renderConversationsPage() {
  return render(<ConversationsPage />)
}
