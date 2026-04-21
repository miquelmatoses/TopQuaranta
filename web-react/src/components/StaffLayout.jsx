/**
 * StaffLayout — shell for every /staff/* route.
 *
 * Renders a dark vertical sidebar on the left with links to each
 * staff area, and the routed content on the right. The yellow top
 * header from the public Layout is preserved — staff still need one
 * click back to the public site.
 *
 * The sidebar collapses to a horizontal scrolling tab strip below
 * `md` so the panel stays usable on phones for quick review actions.
 */
import { NavLink } from 'react-router-dom'

const SECTIONS = [
  { to: '/staff',            label: 'Panel',       end: true },
  { to: '/staff/estat',      label: 'Estat'        },
  { to: '/staff/pendents',   label: 'Pendents'     },
  { to: '/staff/artistes',   label: 'Artistes'     },
  { to: '/staff/cancons',    label: 'Cançons'      },
  { to: '/staff/albums',     label: 'Albums'       },
  { to: '/staff/ranking',    label: 'Ranking prov.' },
  { to: '/staff/propostes',  label: 'Propostes'    },
  { to: '/staff/solicituds', label: 'Sol·licituds' },
  { to: '/staff/feedback',   label: 'Feedback'     },
  { to: '/staff/publicacions',    label: 'Publicacions' },
  { to: '/staff/directori-usuaris', label: 'Directori usuaris' },
  { to: '/staff/senyal',     label: 'Senyal'       },
  { to: '/staff/historial',  label: 'Historial'    },
  { to: '/staff/configuracio', label: 'Configuració' },
  { to: '/staff/auditlog',   label: 'Auditoria'    },
  { to: '/staff/usuaris',    label: 'Usuaris'      },
]

const linkBase =
  'text-sm px-3 py-2 rounded transition-colors whitespace-nowrap ' +
  'md:w-full md:text-left'

const linkClass = ({ isActive }) =>
  linkBase +
  ' ' +
  (isActive
    ? 'bg-tq-yellow text-tq-ink font-semibold'
    : 'text-white/70 hover:text-white hover:bg-white/10')

export default function StaffLayout({ children }) {
  return (
    <div className="-mx-6 lg:-mx-12 flex flex-col md:flex-row min-h-[70vh]">
      {/* ── Dark sidebar ── */}
      <aside
        className="bg-tq-ink text-white md:w-56 md:shrink-0 md:min-h-[70vh] border-r border-white/5"
        aria-label="Navegació staff"
      >
        <div className="px-4 py-3 border-b border-white/5 hidden md:block">
          <p className="text-[10px] uppercase tracking-widest text-white/50">
            Panell intern
          </p>
          <p className="text-sm font-semibold">Staff</p>
        </div>

        <nav className="flex md:flex-col gap-0.5 px-2 py-2 overflow-x-auto md:overflow-visible">
          {SECTIONS.map(({ to, label, end }) => (
            <NavLink key={to} to={to} end={end} className={linkClass}>
              {label}
            </NavLink>
          ))}
        </nav>
      </aside>

      {/* ── Main staff content ── */}
      <div className="flex-1 min-w-0 px-6 lg:px-12 py-6">{children}</div>
    </div>
  )
}
