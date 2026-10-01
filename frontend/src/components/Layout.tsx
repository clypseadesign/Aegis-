import { NavLink, Outlet, useNavigate } from 'react-router-dom'

import { useAuth } from '../auth/useAuth'

/** Authenticated application shell: header, navigation, and routed content. */
export function Layout() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()

  async function handleLogout() {
    // Revoke server-side first so the token cannot be reused, then navigate.
    await logout()
    navigate('/login', { replace: true })
  }

  return (
    <div className="app-shell">
      <header className="app-header">
        <div className="brand">
          <span className="brand-mark" aria-hidden="true">
            &#9673;
          </span>
          <span className="brand-name">AegisAI</span>
        </div>

        <nav aria-label="Main navigation">
          <NavLink to="/projects">Projects</NavLink>
          <NavLink to="/targets">Targets</NavLink>
        </nav>

        <div className="user-menu">
          <span className="user-email">{user?.email}</span>
          <button type="button" onClick={() => void handleLogout()}>
            Sign out
          </button>
        </div>
      </header>

      <main className="app-main">
        <Outlet />
      </main>
    </div>
  )
}
