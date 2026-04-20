/**
 * AccountButton — header slot for the user/login action.
 *
 * Always a single silhouette icon on the yellow bar.
 *   - Not authenticated → links to /compte/accedir.
 *   - Authenticated     → links to /compte (user area). The logout
 *                         action lives inside that page.
 * Title attr shows the email on hover for logged-in users.
 */
import { Link } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'

function UserIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none"
         stroke="currentColor" strokeWidth="1.8" strokeLinecap="round"
         strokeLinejoin="round" aria-hidden="true">
      <circle cx="12" cy="8.5" r="3.2" />
      <path d="M4.5 20.5 C5 16 8.2 13.5 12 13.5 C15.8 13.5 19 16 19.5 20.5" />
    </svg>
  )
}

export default function AccountButton() {
  const { profile, loading } = useAuth()
  if (loading) {
    return <span className="h-8 w-8 rounded-full bg-tq-ink/10 animate-pulse" />
  }

  const to = profile ? '/compte' : '/compte/accedir'
  const label = profile ? profile.email : 'Accedir'

  return (
    <Link
      to={to}
      title={label}
      aria-label={label}
      className="inline-flex items-center justify-center h-8 w-8 rounded-full text-tq-ink hover:bg-tq-ink hover:text-tq-yellow transition-colors"
    >
      <UserIcon />
    </Link>
  )
}
