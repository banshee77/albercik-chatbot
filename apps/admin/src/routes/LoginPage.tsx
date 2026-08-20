import { type FormEvent, useEffect, useState } from 'react'
import { useNavigate } from 'react-router'
import { useAuth } from '../auth/AuthContext'
import { ErrorMessage } from '../components/ErrorMessage'
import { LoadingState } from '../components/LoadingState'
import { usePageTitle } from '../hooks/usePageTitle'

export function LoginPage() {
  usePageTitle('Log in')
  const { status, errorMessage, sessionExpired, login } = useAuth()
  const navigate = useNavigate()

  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [usernameError, setUsernameError] = useState<string | null>(null)
  const [passwordError, setPasswordError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  useEffect(() => {
    if (status === 'authenticated') {
      navigate('/app', { replace: true })
    }
  }, [status, navigate])

  async function handleSubmit(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault()

    const trimmedUsername = username.trim()
    const trimmedPassword = password.trim()
    setUsernameError(trimmedUsername === '' ? 'Enter your username.' : null)
    setPasswordError(trimmedPassword === '' ? 'Enter your password.' : null)
    if (trimmedUsername === '' || trimmedPassword === '') {
      return
    }

    setIsSubmitting(true)
    await login(trimmedUsername, trimmedPassword)
    setIsSubmitting(false)
  }

  return (
    <div className="login-page">
      <h1>Shiruno Admin</h1>
      {sessionExpired && status === 'unauthenticated' && (
        <p role="status">Your session has expired. Please log in again.</p>
      )}
      <form onSubmit={handleSubmit} noValidate>
        <div>
          <label htmlFor="username">Username</label>
          <input
            id="username"
            name="username"
            autoComplete="username"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            aria-invalid={usernameError !== null}
            aria-describedby={usernameError ? 'username-error' : undefined}
          />
          {usernameError && (
            <span id="username-error" role="alert">
              {usernameError}
            </span>
          )}
        </div>
        <div>
          <label htmlFor="password">Password</label>
          <input
            id="password"
            name="password"
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            aria-invalid={passwordError !== null}
            aria-describedby={passwordError ? 'password-error' : undefined}
          />
          {passwordError && (
            <span id="password-error" role="alert">
              {passwordError}
            </span>
          )}
        </div>
        {status === 'error' && errorMessage && <ErrorMessage message={errorMessage} />}
        <button type="submit" disabled={isSubmitting}>
          Log in
        </button>
        {isSubmitting && <LoadingState label="Signing in…" />}
      </form>
    </div>
  )
}
