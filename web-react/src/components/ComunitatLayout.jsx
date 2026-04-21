/**
 * ComunitatLayout — shell for every /comunitat/* route.
 *
 * Mirrors StaffLayout: a dark vertical sidebar on md+ with links to
 * each subsection, collapsing to a horizontal scrolling tab strip on
 * mobile. The public Layout's yellow header stays on top so users can
 * one-click back to the rest of the site.
 *
 * Auth-aware: hides sidebar sections that require authentication when
 * the visitor is anonymous. Anonymous visitors get a trimmed nav that
 * only exposes the public feed.
 */
import { NavLink } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'

const linkBase =
  'text-sm px-3 py-2 rounded transition-colors whitespace-nowrap md:w-full md:text-left'

const linkClass = ({ isActive }) =>
  linkBase +
  ' ' +
  (isActive
    ? 'bg-tq-yellow text-tq-ink font-semibold'
    : 'text-white/70 hover:text-white hover:bg-white/10')

export default function ComunitatLayout({ children }) {
  const { profile } = useAuth()

  const sections = profile
    ? [
        { to: '/comunitat',           label: 'Feed',       end: true },
        { to: '/comunitat/directori', label: 'Directori'   },
        { to: '/comunitat/publicar',  label: '+ Publicar'  },
        { to: '/comunitat/public',    label: 'Feed públic' },
      ]
    : [
        { to: '/comunitat/public',    label: 'Feed públic', end: true },
      ]

  return (
    <div className="-mx-6 lg:-mx-12 flex flex-col md:flex-row min-h-[70vh]">
      {/* ── Dark sidebar ── */}
      <aside
        className="bg-tq-ink text-white md:w-56 md:shrink-0 md:min-h-[70vh] border-r border-white/5"
        aria-label="Navegació comunitat"
      >
        <div className="px-4 py-3 border-b border-white/5 hidden md:block">
          <p className="text-[10px] uppercase tracking-widest text-white/50">
            TopQuaranta
          </p>
          <p className="text-sm font-semibold">Comunitat</p>
        </div>

        <nav className="flex md:flex-col gap-0.5 px-2 py-2 overflow-x-auto md:overflow-visible">
          {sections.map(({ to, label, end }) => (
            <NavLink key={to} to={to} end={end} className={linkClass}>
              {label}
            </NavLink>
          ))}
        </nav>
      </aside>

      {/* ── Main content ── */}
      <div className="flex-1 min-w-0 px-6 lg:px-12 py-6">{children}</div>
    </div>
  )
}
