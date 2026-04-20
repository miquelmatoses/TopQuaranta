/**
 * ArtistesPage — directory of approved artists with a full filter panel.
 *
 * Query params mirror the API 1:1 so links are shareable and the URL
 * stays the single source of truth:
 *   q, territori, comarca, municipi, amb_dones, nou, al_top, page.
 *
 * Filters panel:
 *   - Territori:  7 codes (PPCC hidden as "General" since we show
 *     Tots + 7 small territories; for the directory we keep the 7
 *     native territory codes, alphabetical).
 *   - Comarca, municipi: cascading dropdowns driven by
 *     /api/v1/localitzacio/...
 *   - Checkboxes: amb dones, llançaments últim any, al top
 *   - Cerca per nom (debounced via explicit form submit)
 *
 * Cards show the artist's most-recent album cover as a square image;
 * artists with no album get a name-monogram placeholder on the
 * territory colour.
 */
import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { api } from '../lib/api'

/* Alphabetical by name (same as HomePage). "Tots" is the null filter. */
const TERRITORIS = [
  { codi: '',    nom: 'Tots' },
  { codi: 'AND', nom: 'Andorra' },
  { codi: 'CAT', nom: 'Catalunya' },
  { codi: 'CNO', nom: 'Catalunya del Nord' },
  { codi: 'FRA', nom: 'Franja de Ponent' },
  { codi: 'BAL', nom: 'Illes Balears' },
  { codi: 'ALG', nom: "L'Alguer" },
  { codi: 'VAL', nom: 'País Valencià' },
]

const TERRITORI_COLORS = {
  AND: '#7c3aed', CAT: '#c99b0c', CNO: '#0891b2', FRA: '#ea580c',
  BAL: '#0047ba', ALG: '#db2777', VAL: '#cf3339', PPCC: '#427c42',
  ALT: '#6b7280',
}

function initialsFor(nom) {
  if (!nom) return '?'
  const words = nom.split(/\s+/).filter(Boolean)
  if (words.length === 1) return words[0].slice(0, 2).toUpperCase()
  return (words[0][0] + words[words.length - 1][0]).toUpperCase()
}

function ArtistaCard({ a }) {
  const color = TERRITORI_COLORS[a.territoris?.[0]] || '#6b7280'
  return (
    <Link
      to={`/artista/${a.slug}`}
      className="group block bg-white text-tq-ink rounded-lg overflow-hidden shadow-sm hover:shadow-lg transition-all hover:-translate-y-0.5"
    >
      <div className="aspect-square bg-gray-100 relative">
        {a.imatge_url ? (
          <img
            src={a.imatge_url}
            alt=""
            className="w-full h-full object-cover"
            loading="lazy"
          />
        ) : (
          <div
            className="w-full h-full flex items-center justify-center font-display font-bold text-4xl text-white"
            style={{ backgroundColor: color }}
          >
            {initialsFor(a.nom)}
          </div>
        )}
      </div>
      <div className="p-3">
        <p className="font-semibold truncate">{a.nom}</p>
        <p className="text-xs text-gray-500 truncate mt-0.5">
          {a.localitat?.nom || 'Sense localitat'}
          {a.territoris?.length > 0 && <> · {a.territoris.join(', ')}</>}
        </p>
        {a.genere && (
          <p className="text-xs text-gray-400 truncate mt-1">{a.genere}</p>
        )}
      </div>
    </Link>
  )
}

export default function ArtistesPage() {
  const [params, setParams] = useSearchParams()
  const q         = params.get('q')         || ''
  const territori = (params.get('territori') || '').toUpperCase()
  const comarca   = params.get('comarca')   || ''
  const municipi  = params.get('municipi')  || ''
  const ambDones  = params.get('amb_dones') === '1'
  const nou       = params.get('nou')       === '1'
  const alTop     = params.get('al_top')    === '1'
  const page      = parseInt(params.get('page') || '1', 10)

  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(true)
  const [qDraft, setQDraft] = useState(q)

  // Cascading reference data — comarques depend on territori, municipis on comarca.
  const [comarques, setComarques] = useState([])
  const [municipis, setMunicipis] = useState([])

  useEffect(() => { setQDraft(q) }, [q])

  useEffect(() => {
    if (!territori) { setComarques([]); return }
    api.get(`/localitzacio/comarques/?territori=${territori}`)
      .then(setComarques)
      .catch(() => setComarques([]))
  }, [territori])

  useEffect(() => {
    if (!comarca) { setMunicipis([]); return }
    api.get(`/localitzacio/municipis/?comarca=${encodeURIComponent(comarca)}`)
      .then(setMunicipis)
      .catch(() => setMunicipis([]))
  }, [comarca])

  useEffect(() => {
    setLoading(true)
    setError(null)
    const qs = new URLSearchParams()
    if (q) qs.set('q', q)
    if (territori) qs.set('territori', territori)
    if (comarca) qs.set('comarca', comarca)
    if (municipi) qs.set('municipi', municipi)
    if (ambDones) qs.set('amb_dones', '1')
    if (nou) qs.set('nou', '1')
    if (alTop) qs.set('al_top', '1')
    if (page > 1) qs.set('page', String(page))
    qs.set('per_page', '40')
    api.get(`/artistes/?${qs}`)
      .then(setData)
      .catch(e => setError(e.message || 'Error'))
      .finally(() => setLoading(false))
  }, [q, territori, comarca, municipi, ambDones, nou, alTop, page])

  const setParam = (changes) => {
    const next = new URLSearchParams(params)
    for (const [k, v] of Object.entries(changes)) {
      if (v === '' || v === false || v == null) next.delete(k)
      else next.set(k, v === true ? '1' : String(v))
    }
    next.delete('page')
    setParams(next)
  }

  return (
    <section className="max-w-6xl mx-auto text-white">
      <header className="mb-5">
        <h1 className="text-3xl font-bold">Artistes</h1>
        {data && <p className="text-xs text-tq-ink-muted mt-1">{data.total} resultats</p>}
      </header>

      {/* Filters panel */}
      <div className="bg-white/5 border border-white/10 rounded-lg p-4 mb-5 space-y-3">
        {/* Row 1: search + location cascade */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-2">
          <form
            onSubmit={e => { e.preventDefault(); setParam({ q: qDraft, comarca: '', municipi: '' }) }}
            className="flex gap-1"
          >
            <input
              type="search"
              value={qDraft}
              onChange={e => setQDraft(e.target.value)}
              placeholder="Nom de l'artista…"
              className="flex-1 min-w-0 px-3 py-1.5 bg-white/5 border border-white/15 rounded-md text-sm text-white placeholder-white/40 focus:outline-none focus:border-tq-yellow"
            />
            <button type="submit"
              className="px-3 py-1.5 bg-tq-yellow text-tq-ink rounded-md text-sm font-semibold whitespace-nowrap">
              Cercar
            </button>
          </form>

          <select
            value={territori.toLowerCase()}
            onChange={e => setParam({ territori: e.target.value, comarca: '', municipi: '' })}
            className="px-3 py-1.5 bg-white/5 border border-white/15 rounded-md text-sm text-white focus:outline-none focus:border-tq-yellow"
          >
            {TERRITORIS.map(t => (
              <option key={t.codi || 'tots'} value={t.codi.toLowerCase()} className="text-tq-ink">
                Territori: {t.nom}
              </option>
            ))}
          </select>

          <select
            value={comarca}
            onChange={e => setParam({ comarca: e.target.value, municipi: '' })}
            disabled={!territori || comarques.length === 0}
            className="px-3 py-1.5 bg-white/5 border border-white/15 rounded-md text-sm text-white focus:outline-none focus:border-tq-yellow disabled:opacity-40"
          >
            <option value="" className="text-tq-ink">Comarca: Totes</option>
            {comarques.map(c => (
              <option key={c} value={c} className="text-tq-ink">{c}</option>
            ))}
          </select>

          <select
            value={municipi}
            onChange={e => setParam({ municipi: e.target.value })}
            disabled={!comarca || municipis.length === 0}
            className="px-3 py-1.5 bg-white/5 border border-white/15 rounded-md text-sm text-white focus:outline-none focus:border-tq-yellow disabled:opacity-40"
          >
            <option value="" className="text-tq-ink">Municipi: Tots</option>
            {municipis.map(m => (
              <option key={m} value={m} className="text-tq-ink">{m}</option>
            ))}
          </select>
        </div>

        {/* Row 2: boolean facets */}
        <div className="flex flex-wrap gap-2">
          <FilterCheckbox checked={ambDones} onChange={v => setParam({ amb_dones: v })}>
            Amb dones
          </FilterCheckbox>
          <FilterCheckbox checked={nou} onChange={v => setParam({ nou: v })}>
            Llançaments últim any
          </FilterCheckbox>
          <FilterCheckbox checked={alTop} onChange={v => setParam({ al_top: v })}>
            Amb cançons al top
          </FilterCheckbox>
          {(q || territori || comarca || municipi || ambDones || nou || alTop) && (
            <button
              type="button"
              onClick={() => setParams({})}
              className="text-xs text-tq-yellow hover:underline ml-auto"
            >
              Netejar filtres
            </button>
          )}
        </div>
      </div>

      {/* Results */}
      {loading && (
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
          {Array.from({ length: 12 }).map((_, i) => (
            <div key={i} className="aspect-[4/5] bg-white/5 rounded-lg animate-pulse" />
          ))}
        </div>
      )}

      {error && <div className="bg-red-100 text-red-800 p-3 rounded-md text-sm">{error}</div>}

      {!loading && !error && data?.results?.length === 0 && (
        <p className="text-tq-ink-muted text-sm">Cap artista trobat amb aquests filtres.</p>
      )}

      {!loading && !error && data?.results?.length > 0 && (
        <>
          <ul className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
            {data.results.map(a => (
              <li key={a.slug}><ArtistaCard a={a} /></li>
            ))}
          </ul>

          {data.num_pages > 1 && (
            <nav className="flex items-center justify-center gap-2 mt-8" aria-label="Paginació">
              <button type="button"
                disabled={!data.has_previous}
                onClick={() => {
                  const next = new URLSearchParams(params)
                  next.set('page', String(page - 1))
                  setParams(next)
                }}
                className="px-3 py-1 bg-white/10 text-white rounded-md text-sm disabled:opacity-30">
                Anterior
              </button>
              <span className="text-xs text-tq-ink-muted">
                Pàgina {data.page} de {data.num_pages}
              </span>
              <button type="button"
                disabled={!data.has_next}
                onClick={() => {
                  const next = new URLSearchParams(params)
                  next.set('page', String(page + 1))
                  setParams(next)
                }}
                className="px-3 py-1 bg-white/10 text-white rounded-md text-sm disabled:opacity-30">
                Següent
              </button>
            </nav>
          )}
        </>
      )}
    </section>
  )
}

function FilterCheckbox({ checked, onChange, children }) {
  return (
    <label
      className={
        'inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold cursor-pointer transition-colors ' +
        (checked
          ? 'bg-tq-yellow text-tq-ink'
          : 'bg-white/10 text-white hover:bg-white/20')
      }
    >
      <input
        type="checkbox"
        checked={checked}
        onChange={e => onChange(e.target.checked)}
        className="sr-only"
      />
      {children}
    </label>
  )
}
