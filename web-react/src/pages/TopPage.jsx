/**
 * TopPage — weekly top 40 per territory.
 *
 * Reads ?t=<code> from the URL; defaults to PPCC ("general").
 * Fetches /api/v1/ranking/?territori=X and renders a compact list.
 */
import { useEffect, useState } from 'react'
import { useSearchParams, Link } from 'react-router-dom'
import { api } from '../lib/api'

const TERRITORIS = [
  { codi: 'PPCC', nom: 'General' },
  { codi: 'CAT',  nom: 'Catalunya' },
  { codi: 'VAL',  nom: 'País Valencià' },
  { codi: 'BAL',  nom: 'Illes Balears' },
  { codi: 'CNO',  nom: 'Catalunya Nord' },
  { codi: 'AND',  nom: 'Andorra' },
  { codi: 'ALG',  nom: "L'Alguer" },
]
const TERRITORI_NOM = Object.fromEntries(TERRITORIS.map(t => [t.codi, t.nom]))

export default function TopPage() {
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
    <section className="max-w-5xl mx-auto text-white">
      <nav className="flex flex-wrap gap-1.5 mb-5" aria-label="Territoris">
        {TERRITORIS.map(t => (
          <button
            key={t.codi}
            type="button"
            onClick={() => setParams({ t: t.codi.toLowerCase() })}
            className={
              'px-3 py-1 rounded-full text-xs font-semibold transition-colors ' +
              (t.codi === territori
                ? 'bg-tq-yellow text-tq-ink'
                : 'bg-white/10 text-white hover:bg-white/20')
            }
          >
            {t.nom}
          </button>
        ))}
      </nav>

      <header className="mb-4">
        <h1 className="text-3xl font-bold">
          Top {TERRITORI_NOM[territori] || territori}
        </h1>
        {data?.setmana && (
          <p className="text-xs text-tq-ink-muted mt-1">
            Setmana del {data.setmana}
            {data.es_provisional && (
              <span className="ml-2 px-1.5 py-0.5 bg-tq-yellow/20 text-tq-yellow text-[10px] font-semibold rounded">
                provisional
              </span>
            )}
          </p>
        )}
      </header>

      {loading && (
        <div className="space-y-1">
          {Array.from({ length: 10 }).map((_, i) => (
            <div key={i} className="h-12 bg-white/5 rounded-md animate-pulse" />
          ))}
        </div>
      )}

      {error && (
        <div className="bg-red-100 text-red-800 p-3 rounded-md text-sm">
          {error}
        </div>
      )}

      {!loading && !error && data?.entries && (
        <ol className="space-y-1">
          {data.entries.map(e => (
            <li key={e.posicio}>
              <div className="flex items-center gap-3 bg-white text-tq-ink rounded-md px-3 py-2 shadow-sm hover:shadow-md transition-shadow">
                <span className="w-8 text-center text-xl font-bold font-display">
                  {e.posicio}
                </span>
                {e.album?.imatge_url && (
                  <img
                    src={e.album.imatge_url}
                    alt=""
                    width="40"
                    height="40"
                    className="rounded-sm object-cover"
                  />
                )}
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-semibold truncate">{e.canco.nom}</p>
                  {e.artista && (
                    <p className="text-xs text-gray-500 truncate">
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
                <span className="text-[10px] text-gray-400 tabular-nums">
                  {e.score?.toFixed(1)}
                </span>
              </div>
            </li>
          ))}
        </ol>
      )}

      {!loading && !error && data?.entries?.length === 0 && (
        <p className="text-tq-ink-muted text-sm">No hi ha encara top per a aquest territori.</p>
      )}
    </section>
  )
}
