/**
 * AdminRoute — gate a route behind `user.is_staff` AND a
 * 2FA-verified session.
 *
 * When the user authenticates via the React API (POST /auth/login/),
 * Django opens a session but never runs django-otp's `otp_login()`,
 * so `user.is_verified()` stays False. Every subsequent call to a
 * staff endpoint then fails with "Staff access required" because
 * `IsStaff` DRF permission requires the OTP flag.
 *
 * To keep the staff flow working without rebuilding the 2FA UI in
 * React, we full-page redirect unverified staff users into the
 * Django 2FA flow at `/compte/2fa/...`, which Caddy still proxies
 * through. That flow writes the OTP flag into the same session
 * cookie the SPA uses, so on return the `IsStaff` checks pass.
 *
 * Destinations:
 *   - has TOTP confirmed, not verified this session → /compte/2fa/verificar/
 *   - has no TOTP yet                              → /compte/2fa/configurar/
 *   - anonymous / not staff                        → /compte/accedir
 */
import { useEffect } from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'

export default function AdminRoute({ children }) {
  const { profile, loading } = useAuth()
  const location = useLocation()

  // Full-page redirect for the 2FA handoff. `<Navigate>` is client-side
  // only and can't leave the SPA, so we use window.location when we
  // need to hand the browser over to Django.
  useEffect(() => {
    if (loading || !profile || !profile.is_staff) return
    if (profile.is_verified) return
    const next = encodeURIComponent(location.pathname + location.search)
    const target = profile.has_totp
      ? `/compte/2fa/verificar/?next=${next}`
      : `/compte/2fa/configurar/?next=${next}`
    window.location.replace(target)
  }, [loading, profile, location])

  if (loading) return null
  if (!profile || !profile.is_staff) {
    return <Navigate to="/compte/accedir" replace />
  }

  // Staff but not OTP-verified: render a tiny placeholder while the
  // effect above kicks the browser into the Django 2FA flow.
  if (!profile.is_verified) {
    return (
      <p className="text-sm text-white/60 italic px-6 py-8">
        Redirigint a la verificació 2FA…
      </p>
    )
  }

  return children
}
