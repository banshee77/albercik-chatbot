import { Navigate, Outlet } from 'react-router'
import { useAuth } from '../auth/AuthContext'
import { Header } from '../components/Header'
import { LoadingState } from '../components/LoadingState'
import { Nav } from '../components/Nav'

export function ProtectedLayout() {
  const { status } = useAuth()

  if (status === 'initializing') {
    return <LoadingState label="Loading…" />
  }

  if (status === 'unauthenticated' || status === 'error') {
    return <Navigate to="/login" replace />
  }

  return (
    <div className="app-shell">
      <Header />
      <Nav />
      <main>
        <Outlet />
      </main>
    </div>
  )
}
