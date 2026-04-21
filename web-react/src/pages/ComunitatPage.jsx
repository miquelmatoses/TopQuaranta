/**
 * ComunitatPage — /comunitat
 *
 * Unified feed of publications. Authenticated users see internal +
 * public publications plus their own drafts/pending/rejected. The
 * anonymous public feed lives at /comunitat/public (separate page).
 *
 * Layout chrome (sidebar with Feed / Directori / Publicar / Feed
 * públic) is provided by the shared `ComunitatLayout` via App.jsx.
 * Individual pages render only their own content.
 */
import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api } from '../lib/api'
import { useAuth } from '../context/AuthContext'

function PillFilter({ value, onChange }) {
  const opts = [
    ['',          'Tot'],
    ['internes',  'Internes'],
    ['publiques', 'Públiques'],
    ['meves',     'Meves'],
  ]
  return (
    <div className="flex gap-1 flex-wrap">
      {opts.map(([v, l]) => (
        <button
          key={v}
          type="button"
          onClick={() => onChange(v)}
          className={
            'text-xs font-semibold px-3 py-1 rounded-full transition-colors ' +
            (value === v
              ? 'bg-tq-yellow text-tq-ink'
              : 'bg-white/10 text-white/80 hover:bg-white/20')
          }
        >
          {l}
        </button>
      ))}
    </div>
  )
}

function formatDate(iso) {
  if (!iso) return ''
  return iso.slice(0, 10)
}

function EstatBadge({ estat }) {
  const tone = {
    esborrany: 'bg-gray-300 text-gray-800',
    pendent:   'bg-yellow-200 text-yellow-900',
    publicat:  'bg-emerald-200 text-emerald-900',
    rebutjat:  'bg-red-200 text-red-900',
  }[estat] || 'bg-gray-300 text-gray-800'
  return (
    <span className={'text-[10px] uppercase tracking-wide font-semibold px-2 py-0.5 rounded-full ' + tone}>
      {estat}
    </span>
  )
}

export default function ComunitatPage() {
  const { profile } = useAuth()
  const navigate = useNavigate()
  const [filtre, setFiltre] = useState('')
  const [data, setData] = useState(null)
  const [page, setPage] = useState(1)

  useEffect(() => {
    const params = new URLSearchParams({ filtre, page })
    api.get(`/comunitat/publicacions/?${params}`).then(setData).catch(() => setData(null))
  }, [filtre, page])

  if (!profile) {
    // Non-authenticated users see only the public-feed page.
    return (
      <section className="max-w-3xl mx-auto text-white">
        <h1 className="text-3xl font-bold mb-2">Comunitat TopQuaranta</h1>
        <p className="text-sm text-white/70 mb-6">
          El feed intern és només per a usuaris registrats. Mentrestant pots
          llegir les publicacions públiques.
        </p>
        <div className="flex gap-2">
          <Link
            to="/comunitat/public"
            className="px-4 py-2 bg-tq-yellow text-tq-ink rounded-md text-sm font-semibold"
          >
            Publicacions públiques
          </Link>
          <Link
            to="/compte/accedir"
            className="px-4 py-2 border border-white/20 rounded-md text-sm hover:bg-white/10"
          >
            Entrar / registrar-se
          </Link>
        </div>
      </section>
    )
  }

  return (
    <section className="max-w-3xl mx-auto text-white">
      <div className="flex items-start justify-between gap-3 mb-4 flex-wrap">
        <div>
          <h1 className="text-2xl font-bold">Feed</h1>
          <p className="text-xs text-white/60">
            Internes (només registrats) + públiques + les teves.
          </p>
        </div>
        <PillFilter value={filtre} onChange={v => { setPage(1); setFiltre(v) }} />
      </div>

      {!data && <p className="text-sm text-white/70">Carregant…</p>}
      {data?.results?.length === 0 && (
        <p className="text-sm text-white/60 italic">Cap publicació encara.</p>
      )}
      <ul className="space-y-3">
        {data?.results?.map(p => (
          <li key={p.pk}>
            <Link
              to={`/comunitat/${p.pk}`}
              className="block bg-white text-tq-ink rounded-lg p-4 hover:shadow transition-shadow"
            >
              <div className="flex items-center justify-between gap-2 mb-1">
                <h2 className="font-bold text-lg truncate">{p.titol}</h2>
                <div className="flex gap-1 shrink-0">
                  {p.visibilitat === 'publica' && (
                    <span className="text-[10px] uppercase font-semibold px-2 py-0.5 rounded-full bg-blue-100 text-blue-800">
                      Pública
                    </span>
                  )}
                  <EstatBadge estat={p.estat} />
                </div>
              </div>
              <p className="text-sm text-tq-ink/70 line-clamp-3 whitespace-pre-wrap">{p.cos}</p>
              <p className="text-[11px] text-tq-ink/50 mt-2">
                per {p.autor.nom_public}
                {p.autor.is_staff && ' · staff'}
                {p.publicat_at && ` · ${formatDate(p.publicat_at)}`}
              </p>
            </Link>
          </li>
        ))}
      </ul>

      {data?.num_pages > 1 && (
        <div className="flex items-center gap-2 mt-4 text-xs text-white/60">
          <button
            disabled={!data.has_previous}
            onClick={() => setPage(p => p - 1)}
            className="px-3 py-1 rounded border border-white/20 disabled:opacity-40"
          >
            Anterior
          </button>
          <span>Pàg {data.page} de {data.num_pages}</span>
          <button
            disabled={!data.has_next}
            onClick={() => setPage(p => p + 1)}
            className="px-3 py-1 rounded border border-white/20 disabled:opacity-40"
          >
            Següent
          </button>
        </div>
      )}
    </section>
  )
}
