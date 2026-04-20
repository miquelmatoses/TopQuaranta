/**
 * AuthPage — minimal login form. Will grow when Django's full auth
 * API (register, password reset, 2FA challenge) is wired up. For now
 * it's an email+password form that hits /api/v1/auth/login/.
 */
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'

export default function AuthPage() {
  const { signIn } = useAuth()
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError(null)
    setBusy(true)
    try {
      await signIn(email, password)
      navigate('/')
    } catch (err) {
      setError(err.message || 'Error')
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="max-w-md mx-auto py-12">
      <h1 className="text-3xl font-bold mb-6 text-white">Accedir</h1>
      <form onSubmit={handleSubmit} className="space-y-4 bg-white p-6 rounded-lg text-tq-ink">
        <label className="block">
          <span className="text-sm font-semibold">Correu</span>
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            className="mt-1 w-full border border-gray-300 rounded-sm px-3 py-2"
          />
        </label>
        <label className="block">
          <span className="text-sm font-semibold">Contrasenya</span>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            className="mt-1 w-full border border-gray-300 rounded-sm px-3 py-2"
          />
        </label>
        {error && <p className="text-sm text-red-700">{error}</p>}
        <button
          type="submit"
          disabled={busy}
          className="w-full px-4 py-2 bg-tq-ink text-white font-semibold rounded-md disabled:opacity-50"
        >
          {busy ? 'Accedint…' : 'Accedir'}
        </button>
      </form>
    </section>
  )
}
