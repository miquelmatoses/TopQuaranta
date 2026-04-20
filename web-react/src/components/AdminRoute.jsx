/**
 * AdminRoute — gate a route behind `user.is_staff`.
 *
 * While auth is loading we render nothing; once resolved, non-staff
 * users are redirected to /compte/accedir.
 */
import { Navigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'

export default function AdminRoute({ children }) {
  const { profile, loading } = useAuth()
  if (loading) return null
  if (!profile || !profile.is_staff) {
    return <Navigate to="/compte/accedir" replace />
  }
  return children
}
