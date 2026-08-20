import { render } from '@testing-library/react'
import { createMemoryRouter, RouterProvider } from 'react-router'
import { AuthProvider } from '../src/auth/AuthProvider'
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
