/**
 * ArtistaPage — public artist profile.
 *
 * Reads /api/v1/artistes/<slug>/ and renders:
 *   - Header card (name, territories, location, Deezer link)
 *   - Social links row (when any)
 *   - Last 10 weeks in the ranking (grouped by week)
 *   - Verified discography (albums with cover + track count)
 *
 * Unapproved artists ship a minimal "under review" page.
 */
import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api } from '../lib/api'

const TERRITORI_NOM = {
  CAT: 'Catalunya', VAL: 'País Valencià', BAL: 'Illes Balears',
  PPCC: 'General',  ALT: 'Altres',        AND: 'Andorra',
  CNO: 'Catalunya del Nord', FRA: 'Franja de Ponent',
  ALG: "L'Alguer", CAR: 'Carxe',
}

export default function ArtistaPage() {
  const { slug } = useParams()
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setLoading(true)
    setError(null)
    api.get(`/artistes/${slug}/`)
      .then(setData)
      .catch(e => setError(e.status === 404 ? 'Artista no trobat.' : (e.message || 'Error')))
      .finally(() => setLoading(false))
  }, [slug])

  if (loading) {
    return (
      <div className="max-w-4xl mx-auto space-y-4">
        <div className="h-28 bg-white/5 rounded-lg animate-pulse" />
        <div className="h-48 bg-white/5 rounded-lg animate-pulse" />
      </div>
    )
  }

  if (error) {
    return (
      <div className="max-w-4xl mx-auto">
        <div className="bg-red-100 text-red-800 p-3 rounded-md text-sm">{error}</div>
        <p className="mt-4">
          <Link to="/artistes" className="text-tq-yellow">← Torna al directori</Link>
        </p>
      </div>
    )
  }

  if (!data) return null

  const localitatText = (() => {
    const loc = data.localitats?.[0]
    if (!loc) return null
    if (loc.municipi) {
      return `${loc.municipi.nom}, ${loc.municipi.comarca} (${loc.municipi.territori})`
    }
    return loc.manual
  })()

  return (
    <article className="max-w-4xl mx-auto text-white space-y-6">
      {/* Header card */}
      <header className="bg-white text-tq-ink rounded-lg p-6 shadow-md">
        <h1 className="text-3xl font-bold font-display">{data.nom}</h1>
        <div className="flex flex-wrap gap-2 mt-2 text-sm text-gray-600">
          {data.territoris?.length > 0 && (
            <span>{data.territoris.map(c => TERRITORI_NOM[c] || c).join(' · ')}</span>
          )}
          {localitatText && <span>· {localitatText}</span>}
        </div>
        {data.genere && (
          <p className="text-xs text-gray-500 mt-2 uppercase tracking-wide">{data.genere}</p>
        )}
        {!data.aprovat && (
          <p className="mt-3 inline-block px-2 py-0.5 bg-tq-yellow-soft text-tq-yellow-deep text-xs font-semibold rounded">
            Pendent de revisió
          </p>
        )}

        {/* Links row */}
        <div className="flex flex-wrap gap-3 mt-4 text-sm">
          {data.deezer_ids?.[0] && (
            <a
              href={`https://www.deezer.com/artist/${data.deezer_ids[0]}`}
              target="_blank" rel="noopener"
              className="underline text-tq-ink hover:text-tq-yellow-deep"
            >
              Deezer
            </a>
          )}
          {Object.entries(data.social || {}).map(([key, url]) => (
            <a
              key={key}
              href={url}
              target="_blank" rel="noopener"
              className="underline text-tq-ink hover:text-tq-yellow-deep capitalize"
            >
              {key.replace(/_url$/, '').replace(/_/g, ' ')}
            </a>
          ))}
        </div>
      </header>

      {/* Ranking history */}
      {data.historial?.length > 0 && (
        <section className="bg-white text-tq-ink rounded-lg p-6 shadow-md">
          <h2 className="text-xl font-bold font-display mb-3">Últimes setmanes al top</h2>
          <ul className="space-y-3">
            {data.historial.map(week => (
              <li key={week.setmana}>
                <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide">
                  Setmana del {week.setmana}
                </p>
                <ul className="mt-1 flex flex-wrap gap-1.5">
                  {week.entries.map((e, i) => (
                    <li key={`${week.setmana}-${e.territori}-${i}`}>
                      <Link
                        to={e.canco_id ? `/canco/${e.canco_id}` : '#'}
                        className="inline-flex items-center gap-2 px-2 py-1 bg-tq-yellow-soft text-tq-ink text-xs rounded-sm hover:bg-tq-yellow"
                        title={e.canco_nom}
                      >
                        <span className="font-bold tabular-nums">#{e.posicio}</span>
                        <span className="text-[10px] text-gray-500">{e.territori}</span>
                        <span className="truncate max-w-[14rem]">{e.canco_nom}</span>
                      </Link>
                    </li>
                  ))}
                </ul>
              </li>
            ))}
          </ul>
        </section>
      )}

      {/* Discography */}
      {data.discografia?.length > 0 && (
        <section className="bg-white text-tq-ink rounded-lg p-6 shadow-md">
          <h2 className="text-xl font-bold font-display mb-3">Discografia verificada</h2>
          <ul className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3">
            {data.discografia.map(a => (
              <li key={a.slug}>
                <Link to={`/album/${a.slug}`} className="block">
                  {a.imatge_url ? (
                    <img
                      src={a.imatge_url}
                      alt=""
                      className="aspect-square w-full object-cover rounded-md"
                    />
                  ) : (
                    <div className="aspect-square w-full bg-gray-100 rounded-md" />
                  )}
                  <p className="mt-1.5 text-sm font-semibold truncate">{a.nom}</p>
                  <p className="text-xs text-gray-500">
                    {a.data_llancament?.slice(0, 4)} · {a.n_cancons} cançons
                  </p>
                </Link>
              </li>
            ))}
          </ul>
        </section>
      )}
    </article>
  )
}
