/**
 * AccountButton — header slot for the user/login action.
 *
 * Not authenticated → "Uneix-t'hi" pill linking to /compte/accedir/.
 * Authenticated     → small email chip linking to /compte/ with a
 *                     logout icon button next to it.
 */
import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { useAuth } from '../context/AuthContext'

export default function AccountButton() {
  const { t } = useTranslation()
  const { profile, loading, signOut } = useAuth()

  if (loading) {
    return <span className="h-8 w-20 rounded-full bg-tq-ink/10 animate-pulse" />
  }

  if (!profile) {
    return (
      <Link
        to="/compte/accedir"
        className="inline-flex items-center gap-2 px-4 py-2 bg-tq-ink text-white rounded-full text-sm font-semibold hover:bg-black"
      >
        {t('nav.join', "Uneix-t'hi")}
      </Link>
    )
  }

  return (
    <div className="flex items-center gap-2">
      <Link
        to="/compte"
        className="inline-flex items-center gap-2 px-3 py-1.5 bg-tq-ink/10 text-tq-ink rounded-full text-sm font-medium hover:bg-tq-ink/20"
        title={profile.email}
      >
        {profile.email?.split('@')[0] || 'compte'}
      </Link>
      <button
        type="button"
        onClick={signOut}
        className="text-tq-ink/70 hover:text-tq-ink text-sm"
        aria-label={t('nav.logout', 'Sortir')}
      >
        ↪
      </button>
    </div>
  )
}
