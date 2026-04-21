/**
 * ComptePage — authenticated dashboard, card-grid layout.
 *
 * Layout:
 *   - Row 1: Perfil card (editable via /compte/perfil) + stat tiles
 *            when the user manages a verified artist.
 *   - Row 2: "Els meus artistes" — grid of ArtistaCard + dashed
 *            "Sol·licitar gestió" AddCard.
 *   - Row 3: "Les meves propostes" — grid of PropostaCard + dashed
 *            "Proposar artista" AddCard.
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
const ESTAT_LABEL = { pendent: 'Pendent', aprovat: 'Aprovat', rebutjat: 'Rebutjat' }

function EstatBadge({ estat }) {
  return (
    <span className={`px-2 py-0.5 rounded-full text-[10px] font-semibold ${ESTAT_STYLES[estat] || 'bg-gray-100'}`}>
      {ESTAT_LABEL[estat] || estat}
    </span>
  )
}

function PerfilCard({ user, onLogout }) {
  return (
    <article className="bg-white text-tq-ink rounded-lg shadow-md p-5 flex flex-col">
      <p className="text-xs uppercase tracking-wide text-gray-500">Perfil</p>
      <h2 className="text-lg font-bold font-display mt-1 truncate" title={user?.email}>
        {user?.email}
      </h2>
      {user?.username && user.username !== user.email && (
        <p className="text-sm text-gray-500 truncate mt-0.5">@{user.username}</p>
      )}
      {user?.date_joined && (
        <p className="text-xs text-gray-400 mt-1">
          Membre des del {user.date_joined.slice(0, 10)}
        </p>
      )}
      <div className="flex gap-2 mt-auto pt-4">
        <Link
          to="/compte/perfil"
          className="flex-1 text-center px-3 py-1.5 bg-tq-yellow text-tq-ink rounded-md text-sm font-semibold"
        >
          Editar
        </Link>
        <button
          type="button"
          onClick={onLogout}
          className="px-3 py-1.5 border border-gray-300 text-gray-700 rounded-md text-sm font-semibold hover:bg-gray-100"
        >
          Sortir
        </button>
      </div>
    </article>
  )
}

function StatsCard({ stats, artistaNom }) {
  const tiles = [
    { label: 'Setmanes',       value: stats.setmanes_al_ranking },
    { label: 'Millor posició', value: stats.millor_posicio ? `#${stats.millor_posicio}` : '—' },
    { label: 'Cançons',        value: stats.cancons_al_ranking },
    { label: 'Territoris',     value: stats.territoris_presents },
  ]
  return (
    <article className="bg-white text-tq-ink rounded-lg shadow-md p-5 md:col-span-2">
      <p className="text-xs uppercase tracking-wide text-gray-500 mb-3">
        {artistaNom} al top
      </p>
      <dl className="grid grid-cols-4 gap-2">
        {tiles.map(t => (
          <div key={t.label} className="text-center">
            <dd className="text-2xl font-bold font-display tabular-nums">{t.value ?? '—'}</dd>
            <dt className="text-[10px] text-gray-500 uppercase tracking-wide mt-0.5">{t.label}</dt>
          </div>
        ))}
      </dl>
    </article>
  )
}

function ArtistaCard({ u }) {
  return (
    <Link
      to={artistaUrl(u.artista.slug)}
      className="group bg-white text-tq-ink rounded-lg shadow-md p-4 flex flex-col gap-2 hover:shadow-lg transition-all hover:-translate-y-0.5 min-h-[6.5rem]"
    >
      <p className="font-semibold truncate">{u.artista.nom}</p>
      <div className="flex flex-wrap gap-1.5 mt-auto">
        {u.verificat && (
          <span className="px-2 py-0.5 bg-emerald-100 text-emerald-800 rounded-full text-[10px] font-semibold">
            Verificat
          </span>
        )}
        <EstatBadge estat={u.estat} />
      </div>
    </Link>
  )
}

function PropostaCard({ p }) {
  const inner = (
    <>
      <p className="font-semibold truncate">{p.nom}</p>
      {p.justificacio && (
        <p className="text-xs text-gray-500 line-clamp-2">{p.justificacio}</p>
      )}
      <div className="mt-auto flex items-center gap-2">
        <EstatBadge estat={p.estat} />
        {p.created_at && (
          <span className="text-[10px] text-gray-400">{p.created_at.slice(0, 10)}</span>
        )}
      </div>
    </>
  )
  const classes = "bg-white text-tq-ink rounded-lg shadow-md p-4 flex flex-col gap-2 min-h-[6.5rem] hover:shadow-lg transition-all hover:-translate-y-0.5"
  return p.artista_creat ? (
    <Link to={artistaUrl(p.artista_creat.slug)} className={classes}>{inner}</Link>
  ) : (
    <div className={classes}>{inner}</div>
  )
}

function AddCard({ to, label }) {
  return (
    <Link
      to={to}
      className="flex items-center justify-center bg-transparent border-2 border-dashed border-white/20 hover:border-tq-yellow hover:bg-white/5 text-white rounded-lg p-4 min-h-[6.5rem] transition-colors"
    >
      <span className="text-sm font-semibold">
        <span className="text-tq-yellow mr-1.5">+</span> {label}
      </span>
    </Link>
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

  // Newly registered users without a completed profile land here from
  // the activation email. Bounce them to the guided form once; they
  // can come back via /compte/perfil-usuari any time.
  if (profile.is_authenticated && profile.onboarding_complet === false) {
    return <Navigate to="/onboarding" replace />
  }

  const handleLogout = async () => {
    await signOut()
    navigate('/', { replace: true })
  }

  return (
    <section className="max-w-6xl mx-auto text-white space-y-8">
      {/* Row 1 — Perfil + (stats when verificat) */}
      <div className={
        'grid gap-4 ' +
        (data?.stats ? 'grid-cols-1 md:grid-cols-3' : 'grid-cols-1')
      }>
        <PerfilCard user={data?.user || profile} onLogout={handleLogout} />
        {data?.stats && data?.artista_verificat && (
          <StatsCard stats={data.stats} artistaNom={data.artista_verificat.artista.nom} />
        )}
      </div>

      {/* Perfil comunitari CTA — visible per tots els usuaris */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <Link
          to="/compte/perfil-usuari"
          className="block bg-white/5 border border-white/10 text-white rounded-lg p-4 hover:bg-white/10 transition-colors"
        >
          <p className="text-[10px] uppercase tracking-widest text-white/60">Comunitat</p>
          <p className="font-semibold text-sm mt-1">Perfil de comunitat</p>
          <p className="text-xs text-white/60 mt-1">
            Nom públic, localitat, instruments, visibilitat al directori…
          </p>
        </Link>
        <Link
          to="/comunitat"
          className="block bg-white/5 border border-white/10 text-white rounded-lg p-4 hover:bg-white/10 transition-colors"
        >
          <p className="text-[10px] uppercase tracking-widest text-white/60">Comunitat</p>
          <p className="font-semibold text-sm mt-1">Anar a Comunitat</p>
          <p className="text-xs text-white/60 mt-1">
            Llegir el feed, publicar, explorar el directori.
          </p>
        </Link>
      </div>

      {/* Staff CTA — surface only for staff users */}
      {profile.is_staff && (
        <Link
          to="/staff"
          className="block bg-tq-yellow text-tq-ink rounded-lg p-4 font-semibold text-center hover:bg-tq-yellow-deep hover:text-white transition-colors"
        >
          Anar al panell staff →
        </Link>
      )}

      {loading && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="h-28 bg-white/5 rounded-lg animate-pulse" />
          ))}
        </div>
      )}

      {error && <div className="bg-red-100 text-red-800 p-3 rounded-md text-sm">{error}</div>}

      {!loading && !error && data && (
        <>
          <section>
            <header className="flex items-baseline justify-between mb-3">
              <h2 className="text-lg font-bold font-display">Els meus artistes</h2>
            </header>
            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
              {data.gestio_list.map(u => <ArtistaCard key={u.pk} u={u} />)}
              <AddCard to="/compte/artista/gestio" label="Sol·licitar gestió" />
            </div>
          </section>

          <section>
            <header className="flex items-baseline justify-between mb-3">
              <h2 className="text-lg font-bold font-display">Les meves propostes</h2>
            </header>
            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
              {data.propostes_list.map(p => <PropostaCard key={p.pk} p={p} />)}
              <AddCard to="/compte/artista/proposta" label="Proposar artista" />
            </div>
          </section>
        </>
      )}
    </section>
  )
}
