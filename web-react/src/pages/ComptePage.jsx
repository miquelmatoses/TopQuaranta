/**
 * ComptePage — authenticated dashboard.
 *
 * Hides if the user isn't logged in (redirects to /compte/accedir).
 * Renders:
 *   - User identity chip + logout button
 *   - Primary stat block (if the user manages a verified artist)
 *   - List of artist-management links (UserArtista) with status badges
 *   - List of new-artist proposals (PropostaArtista) with status badges
 *   - CTAs to "Demanar gestió" and "Proposar artista nou"
 */
import { useEffect, useState } from 'react'
import { Link, Navigate, useNavigate } from 'react-router-dom'
import { api } from '../lib/api'
import { useAuth } from '../context/AuthContext'
import { artistaUrl } from '../lib/urls'

const ESTAT_STYLES = {
  pendent:  'bg-tq-yellow-soft text-tq-yellow-deep',
  aprovat:  'bg-emerald-100 text-emerald-800',
  rebutjat: 'bg-red-100 text-red-800',
}
const ESTAT_LABEL = {
  pendent: 'Pendent', aprovat: 'Aprovat', rebutjat: 'Rebutjat',
}

function EstatBadge({ estat }) {
  return (
    <span className={`px-2 py-0.5 rounded-full text-[10px] font-semibold ${ESTAT_STYLES[estat] || 'bg-gray-100'}`}>
      {ESTAT_LABEL[estat] || estat}
    </span>
  )
}

function StatCard({ label, value }) {
  return (
    <div className="bg-white text-tq-ink rounded-lg p-4 shadow-sm">
      <p className="text-3xl font-bold font-display tabular-nums">{value ?? '—'}</p>
      <p className="text-xs text-gray-500 uppercase tracking-wide mt-1">{label}</p>
    </div>
  )
}

export default function ComptePage() {
  const { profile, loading: authLoading, signOut } = useAuth()
  const navigate = useNavigate()
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (authLoading || !profile) return
    setLoading(true)
    api.get('/compte/dashboard/')
      .then(setData)
      .catch(e => setError(e.message || 'Error'))
      .finally(() => setLoading(false))
  }, [authLoading, profile])

  if (authLoading) return null
  if (!profile) return <Navigate to="/compte/accedir" replace />

  const handleLogout = async () => {
    await signOut()
    navigate('/', { replace: true })
  }

  return (
    <section className="max-w-4xl mx-auto text-white space-y-6">
      {/* Identity */}
      <header className="flex flex-wrap items-center gap-3">
        <div className="flex-1">
          <p className="text-xs text-tq-ink-muted uppercase tracking-wide">El meu compte</p>
          <h1 className="text-2xl font-bold font-display">{profile.email}</h1>
          {data?.user?.date_joined && (
            <p className="text-xs text-tq-ink-muted mt-1">
              Membre des del {data.user.date_joined.slice(0, 10)}
            </p>
          )}
        </div>
        {profile.is_staff && (
          <Link
            to="/staff"
            className="px-4 py-2 bg-tq-yellow text-tq-ink rounded-full text-sm font-semibold"
          >
            Panell staff
          </Link>
        )}
        <button
          type="button"
          onClick={handleLogout}
          className="px-4 py-2 bg-white/10 hover:bg-white/20 text-white rounded-full text-sm font-semibold"
        >
          Sortir
        </button>
      </header>

      {loading && <div className="h-32 bg-white/5 rounded-lg animate-pulse" />}
      {error && <div className="bg-red-100 text-red-800 p-3 rounded-md text-sm">{error}</div>}

      {!loading && !error && data && (
        <>
          {/* Stats — only when we manage a verified artist */}
          {data.stats && data.artista_verificat && (
            <section>
              <p className="text-xs uppercase tracking-wide text-tq-ink-muted mb-2">
                {data.artista_verificat.artista.nom} al top
              </p>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                <StatCard label="Setmanes" value={data.stats.setmanes_al_ranking} />
                <StatCard label="Millor posició" value={data.stats.millor_posicio && `#${data.stats.millor_posicio}`} />
                <StatCard label="Cançons" value={data.stats.cancons_al_ranking} />
                <StatCard label="Territoris" value={data.stats.territoris_presents} />
              </div>
            </section>
          )}

          {/* Managed artists */}
          <section className="bg-white text-tq-ink rounded-lg p-5 shadow-md">
            <div className="flex items-baseline justify-between mb-3">
              <h2 className="text-lg font-bold font-display">Artistes que gestiono</h2>
              <Link
                to="/compte/artista/gestio"
                className="text-xs text-tq-yellow-deep underline"
              >
                Demanar gestió d&apos;un artista
              </Link>
            </div>
            {data.gestio_list.length === 0 ? (
              <p className="text-sm text-gray-500">
                Encara no tens cap artista vinculat. Si ets artista o representes algú
                que ja apareix al directori, pots sol·licitar-ne la gestió.
              </p>
            ) : (
              <ul className="space-y-1">
                {data.gestio_list.map(u => (
                  <li key={u.pk} className="flex items-center gap-3 py-2 border-b border-gray-100 last:border-b-0">
                    <Link
                      to={artistaUrl(u.artista.slug)}
                      className="font-semibold hover:text-tq-yellow-deep flex-1 truncate"
                    >
                      {u.artista.nom}
                    </Link>
                    {u.verificat && (
                      <span className="px-2 py-0.5 bg-emerald-100 text-emerald-800 rounded-full text-[10px] font-semibold">
                        Verificat
                      </span>
                    )}
                    <EstatBadge estat={u.estat} />
                  </li>
                ))}
              </ul>
            )}
          </section>

          {/* Proposals */}
          <section className="bg-white text-tq-ink rounded-lg p-5 shadow-md">
            <div className="flex items-baseline justify-between mb-3">
              <h2 className="text-lg font-bold font-display">Propostes d&apos;artista</h2>
              <Link
                to="/compte/artista/proposta"
                className="text-xs text-tq-yellow-deep underline"
              >
                Proposar un artista nou
              </Link>
            </div>
            {data.propostes_list.length === 0 ? (
              <p className="text-sm text-gray-500">
                Coneixes algun artista en català que no hi sigui? Proposa-l&apos;hi.
                Si la proposta s&apos;aprova, l&apos;afegim al catàleg.
              </p>
            ) : (
              <ul className="space-y-1">
                {data.propostes_list.map(p => (
                  <li key={p.pk} className="flex items-center gap-3 py-2 border-b border-gray-100 last:border-b-0">
                    {p.artista_creat ? (
                      <Link
                        to={artistaUrl(p.artista_creat.slug)}
                        className="font-semibold hover:text-tq-yellow-deep flex-1 truncate"
                      >
                        {p.nom}
                      </Link>
                    ) : (
                      <span className="font-semibold flex-1 truncate">{p.nom}</span>
                    )}
                    <EstatBadge estat={p.estat} />
                  </li>
                ))}
              </ul>
            )}
          </section>
        </>
      )}
    </section>
  )
}
