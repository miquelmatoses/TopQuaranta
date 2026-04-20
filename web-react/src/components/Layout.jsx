/**
 * Layout — persistent shell wrapping every route.
 *
 * Header: yellow bar on tq-yellow with ink (black) text.
 *   Left:   TopQuaranta horizontal logo (ink, via currentColor)
 *   Center: public nav (Rànquing / Artistes / Mapa)
 *   Right:  AccountButton, LanguageToggle, mobile hamburger
 *
 * Body: black (tq-ink). Cards inside are white surfaces.
 * Homepage (`/`) opts into the all-yellow theme via `data-theme="yellow"`
 * on `<body>` — set inside HomePage.jsx with a useEffect so the rest
 * of the app stays black.
 */
import { useState } from 'react'
import { Link, NavLink } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import TopQuarantaLogo from './TopQuarantaLogo'
import AccountButton from './AccountButton'
import LanguageToggle from './LanguageToggle'
import { useAuth } from '../context/AuthContext'

function Hamburger({ open }) {
  if (open) {
    return (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none"
           stroke="currentColor" strokeWidth="2.5" strokeLinecap="round"
           strokeLinejoin="round" aria-hidden="true">
        <path d="M18 6 6 18" /><path d="m6 6 12 12" />
      </svg>
    )
  }
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none"
         stroke="currentColor" strokeWidth="2.5" strokeLinecap="round"
         strokeLinejoin="round" aria-hidden="true">
      <line x1="3" y1="6" x2="21" y2="6" />
      <line x1="3" y1="12" x2="21" y2="12" />
      <line x1="3" y1="18" x2="21" y2="18" />
    </svg>
  )
}

export default function Layout({ children }) {
  const { t } = useTranslation()
  const { profile } = useAuth()
  const [menuOpen, setMenuOpen] = useState(false)

  const navLinks = [
    { to: '/ranking',   label: t('nav.ranking',   'Rànquing')  },
    { to: '/artistes',  label: t('nav.artistes',  'Artistes')  },
    { to: '/mapa',      label: t('nav.mapa',      'Mapa')      },
    ...(profile?.is_staff ? [{ to: '/staff', label: 'Staff' }] : []),
  ]

  const linkClass = ({ isActive }) =>
    'shrink-0 text-sm font-semibold px-3 py-2 rounded-sm transition-colors whitespace-nowrap ' +
    (isActive
      ? 'bg-tq-ink text-tq-yellow'
      : 'text-tq-ink/80 hover:text-tq-ink hover:bg-tq-ink/10')

  return (
    <>
      {/* ── Yellow header ── */}
      <header className="bg-tq-yellow text-tq-ink sticky top-0 z-40">
        <div className="max-w-[80rem] mx-auto h-16 flex items-center gap-6 px-6 lg:px-8">
          <Link to="/" className="shrink-0 text-tq-ink" aria-label="TopQuaranta — Inici">
            <TopQuarantaLogo className="h-9 w-auto" />
          </Link>

          <nav
            className="hidden md:flex flex-1 items-center gap-1 min-w-0"
            aria-label="Navegació principal"
          >
            {navLinks.map(({ to, label }) => (
              <NavLink key={to} to={to} className={linkClass}>
                {label}
              </NavLink>
            ))}
          </nav>

          <div className="flex items-center gap-3 shrink-0 ml-auto md:ml-0">
            <AccountButton />
            <LanguageToggle />
            <button
              type="button"
              onClick={() => setMenuOpen(o => !o)}
              aria-label={menuOpen ? 'Tancar menú' : 'Obrir menú'}
              aria-expanded={menuOpen}
              className="md:hidden p-1 text-tq-ink"
            >
              <Hamburger open={menuOpen} />
            </button>
          </div>
        </div>

        {menuOpen && (
          <div className="md:hidden border-t border-tq-ink/10">
            <nav className="flex flex-col px-4 py-3 gap-1 max-w-[80rem] mx-auto"
                 aria-label="Navegació mòbil">
              {navLinks.map(({ to, label }) => (
                <NavLink
                  key={to}
                  to={to}
                  onClick={() => setMenuOpen(false)}
                  className={linkClass}
                >
                  {label}
                </NavLink>
              ))}
            </nav>
          </div>
        )}
      </header>

      {/* ── Main content ── */}
      <main className="max-w-[80rem] mx-auto px-6 lg:px-8 py-8 min-h-[60vh]">
        {children}
      </main>

      {/* ── Footer ── */}
      <footer className="bg-tq-ink text-white border-t border-tq-border mt-12 py-10">
        <div className="max-w-[80rem] mx-auto px-6 lg:px-8 flex flex-wrap items-baseline justify-between gap-4">
          <p className="text-sm text-tq-ink-muted m-0">
            © {new Date().getFullYear()} TopQuaranta
          </p>
          <TopQuarantaLogo className="h-5 w-auto text-white/80" />
        </div>
      </footer>
    </>
  )
}
