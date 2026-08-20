import { createBrowserRouter, RouterProvider } from 'react-router'
import { routeConfig } from './routeConfig'

const router = createBrowserRouter(routeConfig)

export function App() {
  return <RouterProvider router={router} />
}
