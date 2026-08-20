import { Link } from 'react-router'
import { useAuth } from '../auth/AuthContext'
import { usePageTitle } from '../hooks/usePageTitle'

export function AppHome() {
  usePageTitle('Home')
  const { tenant } = useAuth()

  return (
    <div>
      <h1>Welcome{tenant ? `, ${tenant.name}` : ''}</h1>
      <p>This is the Shiruno Admin Platform shell.</p>
      <nav aria-label="Shortcuts">
        <ul>
          <li>
            <Link to="/app/knowledge">Knowledge</Link>
          </li>
          <li>
            <Link to="/app/conversations">Conversations</Link>
          </li>
          <li>
            <Link to="/app/analytics">Analytics</Link>
          </li>
        </ul>
      </nav>
    </div>
  )
}
