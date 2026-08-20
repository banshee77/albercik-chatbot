import { NavLink } from 'react-router'

export function Nav() {
  return (
    <nav aria-label="Primary">
      <ul>
        <li>
          <NavLink to="/app/knowledge">Knowledge</NavLink>
        </li>
        <li>
          <NavLink to="/app/conversations">Conversations</NavLink>
        </li>
        <li>
          <NavLink to="/app/analytics">Analytics</NavLink>
        </li>
      </ul>
    </nav>
  )
}
