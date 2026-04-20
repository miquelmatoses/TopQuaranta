/**
 * MapaPage — /mapa
 *
 * "Explore by place" without a SVG map — yet. Reuses the existing
 * /api/v1/mapa/artistes/ endpoint (which already returns
 * per-comarca and per-municipi breakdowns with top artists) and
 * renders a territori-tab + comarques grid interface.
 *
 * This is consciously a v1: a real SVG/D3 map with municipis is a
 * separate sprint. The shape here covers the same "who's active in
 * my area" use case for mobile and keyboard users, and works
 * without any client-side cartography.
 */
import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../lib/api'

// Display order — CAT/VAL/BAL first (the core territories), then the
// rest alphabetically. Matches HomePage.
const TERRITORIS = [
  { codi: 'CAT',  nom: 'Catalunya' },
  { codi: 'VAL',  nom: 'País Valencià' },
  { codi: 'BAL',  nom: 'Illes Balears' },
  { codi: 'AND',  nom: 'Andorra' },
  { codi: 'CNO',  nom: 'Catalunya del Nord' },
  { codi: 'FRA',  nom: 'Franja de Ponent' },
  { codi: 'ALG',  nom: "L'Alguer" },
  { codi: 'CAR',  nom: 'El Carxe' },
  { codi: 'ALT',  nom: 'Altres' },
]

// Match the territori stored on Municipi (full name) against our code list.
function codeForName(nom) {
  const t = TERRITORIS.find(t => t.nom === nom)
  return t?.codi
}

export default function MapaPage() {
  const [data, setData] = useState(null)
  const [territori, setTerritori] = useState('CAT')
  const [expanded, setExpanded] = useState(null) // comarca key
  const [error, setError] = useState(null)

  useEffect(() => {
    api.get('/mapa/artistes/').then(setData).catch(e => setError(e.message))
  }, [])

  // Flatten + group: build a per-territori list of comarques (sorted
  // by "has top artist" so populated ones bubble up), each with an
  // optional list of municipis once expanded.
  const comarquesByTerr = useMemo(() => {
    if (!data) return {}
    const out = {}
    for (const [key, c] of Object.entries(data.comarques || {})) {
      const codi = codeForName(c.territori) || 'ALT'
      out[codi] ||= []
      out[codi].push({ key, ...c })
    }
    // Most-active comarques (ones with a top artist) first, else alphabetical.
    for (const codi of Object.keys(out)) {
      out[codi].sort((a, b) => {
        if (!!a.artista !== !!b.artista) return a.artista ? -1 : 1
        return a.nom.localeCompare(b.nom, 'ca')
      })
    }
    return out
  }, [data])

  const municipisByComarca = useMemo(() => {
    if (!data) return {}
    const out = {}
    for (const [key, m] of Object.entries(data.municipis || {})) {
      if (!m.n_artistes) continue
      const com = (m.comarca || '').toLowerCase()
      out[com] ||= []
      out[com].push({ key, ...m })
    }
    for (const com of Object.keys(out)) {
      out[com].sort((a, b) => b.n_artistes - a.n_artistes)
    }
    return out
  }, [data])

  if (error) {
    return (
      <section className="max-w-4xl mx-auto text-white">
        <h1 className="text-3xl font-bold mb-3">Mapa</h1>
        <p className="text-sm text-red-300">No s'han pogut carregar les dades: {error}</p>
      </section>
    )
  }

  const list = comarquesByTerr[territori] || []
  const totalArtistesTerr = list.reduce(
    (n, c) => n + (municipisByComarca[c.nom.toLowerCase()]?.reduce((m, x) => m + x.n_artistes, 0) || 0),
    0,
  )

  return (
    <section className="max-w-5xl mx-auto text-white">
      <header className="mb-6">
        <h1 className="text-3xl font-bold mb-2">Mapa</h1>
        <p className="text-sm text-white/70">
          Explora els artistes per territori i comarca. Clica una comarca
          per veure els municipis on tenen activitat.
        </p>
      </header>

      {/* Territory pills */}
      <nav className="flex flex-wrap gap-1.5 mb-5" aria-label="Territori">
        {TERRITORIS.map(t => {
          const n = comarquesByTerr[t.codi]?.length || 0
          const active = territori === t.codi
          return (
            <button
              key={t.codi}
              type="button"
              onClick={() => { setTerritori(t.codi); setExpanded(null) }}
              className={
                'text-xs font-semibold px-3 py-1.5 rounded-full transition-colors ' +
                (active
                  ? 'bg-tq-yellow text-tq-ink'
                  : 'bg-white/10 text-white/80 hover:bg-white/20')
              }
            >
              {t.nom}
              {n > 0 && (
                <span className="ml-1.5 opacity-60">· {n}</span>
              )}
            </button>
          )
        })}
      </nav>

      {!data && (
        <div className="grid sm:grid-cols-2 md:grid-cols-3 gap-3">
          {Array.from({ length: 9 }).map((_, i) => (
            <div key={i} className="h-24 bg-white/5 rounded-lg animate-pulse" />
          ))}
        </div>
      )}

      {data && list.length === 0 && (
        <p className="text-sm text-white/60 italic">
          Cap comarca amb dades a {TERRITORIS.find(t => t.codi === territori)?.nom}.
        </p>
      )}

      {data && list.length > 0 && (
        <>
          <p className="text-xs text-white/50 mb-3">
            {list.filter(c => c.artista).length} comarques amb artistes al ranking actual.
          </p>
          <ul className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {list.map(c => {
              const key = c.nom.toLowerCase()
              const municipis = municipisByComarca[key] || []
              const isOpen = expanded === key
              const has = !!c.artista
              return (
                <li key={c.key}>
                  <button
                    type="button"
                    onClick={() =>
                      setExpanded(isOpen ? null : key)
                    }
                    disabled={!municipis.length}
                    className={
                      'w-full text-left rounded-lg p-4 transition-all ' +
                      (has
                        ? 'bg-white text-tq-ink hover:shadow-md'
                        : 'bg-white/5 text-white/50')
                    }
                  >
                    <div className="flex items-start justify-between gap-2">
                      <span className="font-semibold">{c.nom}</span>
                      {municipis.length > 0 && (
                        <span className="text-[10px] bg-tq-ink/10 rounded-full px-2 py-0.5">
                          {municipis.length} municipi{municipis.length === 1 ? '' : 's'}
                        </span>
                      )}
                    </div>
                    {has ? (
                      <p className="text-xs mt-1.5">
                        Destacat:{' '}
                        <Link
                          to={`/artista/${c.artista.slug}`}
                          onClick={e => e.stopPropagation()}
                          className="font-semibold underline"
                        >
                          {c.artista.nom}
                        </Link>
                      </p>
                    ) : (
                      <p className="text-xs mt-1.5 italic">Sense activitat actual</p>
                    )}
                  </button>

                  {isOpen && municipis.length > 0 && (
                    <div className="mt-1 ml-2 pl-3 border-l border-white/20 space-y-2">
                      {municipis.map(m => (
                        <div key={m.key} className="text-sm">
                          <p className="font-semibold text-white/90">
                            {m.nom}{' '}
                            <span className="text-xs opacity-60">
                              · {m.n_artistes} {m.n_artistes === 1 ? 'artista' : 'artistes'}
                            </span>
                          </p>
                          {m.artistes && m.artistes.length > 0 && (
                            <ul className="text-xs mt-0.5 flex flex-wrap gap-1">
                              {m.artistes.map(a => (
                                <li key={a.slug}>
                                  <Link
                                    to={`/artista/${a.slug}`}
                                    className="px-2 py-0.5 rounded-full bg-white/10 hover:bg-tq-yellow hover:text-tq-ink transition-colors"
                                  >
                                    {a.nom}
                                  </Link>
                                </li>
                              ))}
                            </ul>
                          )}
                        </div>
                      ))}
                    </div>
                  )}
                </li>
              )
            })}
          </ul>
        </>
      )}

      <footer className="mt-8 text-xs text-white/50">
        <p>
          Vols veure'ls tots? Filtra al{' '}
          <Link to={`/artistes?territori=${territori}`} className="underline">
            directori d'artistes per territori
          </Link>
          .
        </p>
      </footer>
    </section>
  )
}
