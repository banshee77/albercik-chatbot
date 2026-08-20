import { useAuth } from '../auth/AuthContext'

export function Header() {
  const { administrator, tenant, logout } = useAuth()

  return (
    <header className="app-header">
      <span className="app-header__brand">Shiruno Admin</span>
      {tenant && <span className="app-header__org">{tenant.name}</span>}
      {administrator && <span className="app-header__user">{administrator.username}</span>}
      <button type="button" onClick={logout}>
        Log out
      </button>
    </header>
  )
}
