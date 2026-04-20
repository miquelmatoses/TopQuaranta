/**
 * AuthCallbackPage — placeholder for OAuth/email-link callbacks once
 * the Django API supports them. Today it just redirects home.
 */
import { useEffect } from 'react'
import { useNavigate } from 'react-router-dom'

export default function AuthCallbackPage() {
  const navigate = useNavigate()
  useEffect(() => {
    navigate('/', { replace: true })
  }, [navigate])
  return null
}
