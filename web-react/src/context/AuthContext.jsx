/**
 * AuthContext — wraps Django session-auth state.
 *
 * On mount, GETs /api/v1/auth/me/ to see if there's an active session.
 * Exposes:
 *   profile  — { id, email, is_staff } | null
 *   loading  — true during the initial /me/ roundtrip
 *   signIn(email, password)
 *   signOut()
 */
import { createContext, useContext, useEffect, useState, useCallback } from 'react'
import { auth as authApi } from '../lib/api'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [profile, setProfile] = useState(null)
  const [loading, setLoading] = useState(true)

  const refresh = useCallback(async () => {
    try {
      const me = await authApi.me()
      setProfile(me?.is_authenticated ? me : null)
    } catch {
      setProfile(null)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    refresh()
  }, [refresh])

  const signIn = useCallback(
    async (email, password) => {
      const me = await authApi.login(email, password)
      setProfile(me)
      return me
    },
    [],
  )

  const signOut = useCallback(async () => {
    await authApi.logout()
    setProfile(null)
  }, [])

  return (
    <AuthContext.Provider value={{ profile, loading, signIn, signOut, refresh }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used inside <AuthProvider>')
  return ctx
}
