/**
 * ArtistesPage — directory of approved artists.
 *
 * Query params mirror the API: ?q=...&territori=CAT|VAL|BAL.
 * Renders a responsive card grid; each card links to /artista/<slug>.
 * Pagination is keyboard-visible (prev/next buttons) — no infinite
 * scroll for now; the page count is bounded and easy to navigate.
 */
import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { api } from '../lib/api'

const TERRITORI_FILTERS = [
  { codi: '',    label: 'Tots'      },
  { codi: 'CAT', label: 'Catalunya' },
  { codi: 'VAL', label: 'País Valencià' },
  { codi: 'BAL', label: 'Illes Balears' },
]

export default function ArtistesPage() {
  const [params, setParams] = useSearchParams()
  const q = params.get('q') || ''
  const territori = (params.get('territori') || '').toUpperCase()
  const page = parseInt(params.get('page') || '1', 10)

  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(true)
  // Local-edit buffer for the search input so typing is snappy.
  const [qDraft, setQDraft] = useState(q)

  useEffect(() => { setQDraft(q) }, [q])

  useEffect(() => {
    setLoading(true)
    setError(null)
    const qs = new URLSearchParams()
    if (q) qs.set('q', q)
    if (territori) qs.set('territori', territori)
    if (page > 1) qs.set('page', String(page))
    qs.set('per_page', '40')
    api.get(`/artistes/?${qs}`)
      .then(setData)
      .catch(e => setError(e.message || 'Error'))
      .finally(() => setLoading(false))
  }, [q, territori, page])

  const setParam = (k, v) => {
    const next = new URLSearchParams(params)
    if (v) next.set(k, v); else next.delete(k)
    if (k !== 'page') next.delete('page')  // reset pagination on filter change
    setParams(next)
  }

  const submitSearch = (e) => {
    e.preventDefault()
    setParam('q', qDraft)
  }

  return (
    <section className="max-w-6xl mx-auto text-white">
      <header className="mb-6">
        <h1 className="text-3xl font-bold">Artistes</h1>
        {data && (
          <p className="text-xs text-tq-ink-muted mt-1">
            {data.total} resultats
          </p>
        )}
      </header>

      {/* Filters */}
      <form onSubmit={submitSearch} className="flex flex-wrap gap-2 mb-5">
        <div className="flex flex-wrap gap-1.5">
          {TERRITORI_FILTERS.map(t => (
            <button
              key={t.codi || 'tots'}
              type="button"
              onClick={() => setParam('territori', t.codi.toLowerCase())}
              className={
                'px-3 py-1 rounded-full text-xs font-semibold transition-colors ' +
                (t.codi === territori || (!territori && !t.codi)
                  ? 'bg-tq-yellow text-tq-ink'
                  : 'bg-white/10 text-white hover:bg-white/20')
              }
            >
              {t.label}
            </button>
          ))}
        </div>
        <div className="flex-1" />
        <input
          type="search"
          value={qDraft}
          onChange={e => setQDraft(e.target.value)}
          placeholder="Cercar per nom…"
          className="px-3 py-1 bg-white/5 border border-white/15 rounded-md text-sm text-white placeholder-white/40 focus:outline-none focus:border-tq-yellow"
        />
        <button
          type="submit"
          className="px-3 py-1 bg-tq-yellow text-tq-ink rounded-md text-sm font-semibold"
        >
          Cercar
        </button>
      </form>

      {/* Results */}
      {loading && (
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
          {Array.from({ length: 12 }).map((_, i) => (
            <div key={i} className="h-24 bg-white/5 rounded-lg animate-pulse" />
          ))}
        </div>
      )}

      {error && <div className="bg-red-100 text-red-800 p-3 rounded-md text-sm">{error}</div>}

      {!loading && !error && data?.results?.length === 0 && (
        <p className="text-tq-ink-muted text-sm">Cap artista trobat amb aquests criteris.</p>
      )}

      {!loading && !error && data?.results?.length > 0 && (
        <>
          <ul className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
            {data.results.map(a => (
              <li key={a.slug}>
                <Link
                  to={`/artista/${a.slug}`}
                  className="block h-full bg-white text-tq-ink rounded-lg p-4 shadow-sm hover:shadow-md transition-shadow"
                >
                  <p className="font-semibold truncate">{a.nom}</p>
                  <p className="text-xs text-gray-500 truncate mt-0.5">
                    {a.localitat?.nom || 'Sense localitat'}
                    {a.territoris.length > 0 && <> · {a.territoris.join(', ')}</>}
                  </p>
                  {a.genere && (
                    <p className="text-xs text-gray-400 truncate mt-1">{a.genere}</p>
                  )}
                </Link>
              </li>
            ))}
          </ul>

          {/* Pagination */}
          {data.num_pages > 1 && (
            <nav className="flex items-center justify-center gap-2 mt-8" aria-label="Paginació">
              <button
                type="button"
                disabled={!data.has_previous}
                onClick={() => setParam('page', String(page - 1))}
                className="px-3 py-1 bg-white/10 text-white rounded-md text-sm disabled:opacity-30"
              >
                Anterior
              </button>
              <span className="text-xs text-tq-ink-muted">
                Pàgina {data.page} de {data.num_pages}
              </span>
              <button
                type="button"
                disabled={!data.has_next}
                onClick={() => setParam('page', String(page + 1))}
                className="px-3 py-1 bg-white/10 text-white rounded-md text-sm disabled:opacity-30"
              >
                Següent
              </button>
            </nav>
          )}
        </>
      )}
    </section>
  )
}
