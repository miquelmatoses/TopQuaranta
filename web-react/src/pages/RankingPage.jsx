/**
 * RankingPage — weekly top 40 per territory.
 *
 * Reads ?t=CAT|VAL|BAL|PPCC|ALT from the URL; defaults to PPCC.
 * Fetches /api/v1/ranking/?territori=X and renders the top 40 as a
 * card list. This is the first page wired end-to-end React → Django
 * → Postgres.
 */
import { useEffect, useState } from 'react'
import { useSearchParams, Link } from 'react-router-dom'
import { api } from '../lib/api'
import SectionLabel from '../components/ui/SectionLabel'

const TERRITORIS = ['PPCC', 'CAT', 'VAL', 'BAL']
const TERRITORI_NOM = {
  PPCC: 'Països Catalans',
  CAT:  'Catalunya',
  VAL:  'País Valencià',
  BAL:  'Illes Balears',
  ALT:  'Altres',
}

export default function RankingPage() {
  const [params, setParams] = useSearchParams()
  const territori = (params.get('t') || 'PPCC').toUpperCase()

  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setLoading(true)
    setError(null)
    api.get(`/ranking/?territori=${encodeURIComponent(territori)}`)
      .then(setData)
      .catch(err => setError(err.message || 'Error'))
      .finally(() => setLoading(false))
  }, [territori])

  return (
    <section className="py-8 text-white">
      {/* Territory selector */}
      <nav className="flex flex-wrap gap-2 mb-6" aria-label="Territoris">
        {TERRITORIS.map(t => (
          <button
            key={t}
            type="button"
            onClick={() => setParams({ t: t.toLowerCase() })}
            className={
              'px-4 py-2 rounded-full text-sm font-semibold transition-colors ' +
              (t === territori
                ? 'bg-tq-yellow text-tq-ink'
                : 'bg-white/10 text-white hover:bg-white/20')
            }
          >
            {TERRITORI_NOM[t]}
          </button>
        ))}
      </nav>

      <header className="mb-6">
        <SectionLabel color="yellow">
          Rànquing setmanal — {TERRITORI_NOM[territori] || territori}
        </SectionLabel>
        <h1 className="text-4xl font-bold mt-2">Top 40</h1>
        {data?.setmana && (
          <p className="text-sm text-tq-ink-muted mt-1">
            Setmana del {data.setmana}
            {data.es_provisional && (
              <span className="ml-2 px-2 py-0.5 bg-tq-yellow/20 text-tq-yellow text-xs font-semibold rounded">
                provisional
              </span>
            )}
          </p>
        )}
      </header>

      {loading && (
        <div className="space-y-2">
          {Array.from({ length: 10 }).map((_, i) => (
            <div key={i} className="h-14 bg-white/5 rounded-lg animate-pulse" />
          ))}
        </div>
      )}

      {error && (
        <div className="bg-red-100 text-red-800 p-4 rounded-md">
          {error}
        </div>
      )}

      {!loading && !error && data?.entries && (
        <ol className="space-y-1.5">
          {data.entries.map(e => (
            <li key={e.posicio} className="group">
              <div className="flex items-center gap-4 bg-white text-tq-ink rounded-lg px-4 py-3 shadow-md transition-shadow hover:shadow-lg">
                <span className="w-10 text-center text-3xl font-bold font-display">
                  {e.posicio}
                </span>
                {e.album?.imatge_url && (
                  <img
                    src={e.album.imatge_url}
                    alt=""
                    width="48"
                    height="48"
                    className="rounded-sm object-cover"
                  />
                )}
                <div className="flex-1 min-w-0">
                  <p className="font-semibold truncate">{e.canco.nom}</p>
                  {e.artista && (
                    <p className="text-sm text-gray-600 truncate">
                      {e.artista.slug ? (
                        <Link
                          to={`/artista/${e.artista.slug}`}
                          className="hover:text-tq-yellow-deep"
                        >
                          {e.artista.nom}
                        </Link>
                      ) : (
                        e.artista.nom
                      )}
                    </p>
                  )}
                </div>
                <span className="text-xs text-gray-400 tabular-nums">
                  {e.score?.toFixed(1)}
                </span>
              </div>
            </li>
          ))}
        </ol>
      )}

      {!loading && !error && data?.entries?.length === 0 && (
        <p className="text-tq-ink-muted">No hi ha encara rànquing per a aquest territori.</p>
      )}
    </section>
  )
}
