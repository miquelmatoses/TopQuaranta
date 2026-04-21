/**
 * MapaPage — /mapa
 *
 * SVG map of the Països Catalans. Three drill-down levels:
 *   1. Territoris  (paisos.json)                → click → comarca
 *   2. Comarques   (comarques-<CODI>.json)      → click → municipi
 *   3. Municipis   (municipis-<CODI>.json)      → click → list of artistes
 *
 * Left: the map itself (SVG, equirectangular projection, no tiles).
 * Right: a sticky panel with the current level's KPIs, or — at municipi
 * level when one is selected — the list of artistes living there.
 *
 * Colouring: coropleta groc-clar → tq-yellow segons n_artistes.
 * Non-PPCC artistes (localitat_manual without municipi) are skipped by
 * the backend, so they never affect the map.
 */
import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../lib/api'

const TERRITORI_NOM = {
  CAT: 'Catalunya',
  VAL: 'País Valencià',
  BAL: 'Illes Balears',
  AND: 'Andorra',
  CNO: 'Catalunya del Nord',
  FRA: 'Franja de Ponent',
  ALG: "L'Alguer",
  CAR: 'El Carxe',
}

// Fetch a static GeoJSON from /public/geodata/.
function useGeoJSON(path) {
  const [data, setData] = useState(null)
  useEffect(() => {
    let cancelled = false
    setData(null)
    fetch(path).then(r => r.json()).then(j => { if (!cancelled) setData(j) }).catch(() => {})
    return () => { cancelled = true }
  }, [path])
  return data
}

// Compute bounds from a FeatureCollection. Returns null if empty.
function boundsFromGeoJSON(gj) {
  let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity
  function walk(coords) {
    if (typeof coords[0] === 'number') {
      const [x, y] = coords
      if (x < minX) minX = x; if (x > maxX) maxX = x
      if (y < minY) minY = y; if (y > maxY) maxY = y
    } else {
      for (const c of coords) walk(c)
    }
  }
  for (const ft of gj?.features || []) walk(ft.geometry.coordinates)
  if (!isFinite(minX)) return null
  return { minX, minY, maxX, maxY }
}

// Polygon / MultiPolygon → SVG "d". Y is negated so northern latitudes
// render on top.
function geometryToPath(geom) {
  const rings = geom.type === 'Polygon' ? [geom.coordinates] : geom.coordinates
  const parts = []
  for (const poly of rings) {
    for (const ring of poly) {
      if (!ring.length) continue
      const [x0, y0] = ring[0]
      let d = `M${x0.toFixed(4)},${(-y0).toFixed(4)}`
      for (let i = 1; i < ring.length; i++) {
        const [x, y] = ring[i]
        d += `L${x.toFixed(4)},${(-y).toFixed(4)}`
      }
      d += 'Z'
      parts.push(d)
    }
  }
  return parts.join(' ')
}

// Linear mix between two hex colours, t in [0, 1].
function mix(a, b, t) {
  const ah = parseInt(a.slice(1), 16), bh = parseInt(b.slice(1), 16)
  const ar = (ah >> 16) & 0xff, ag = (ah >> 8) & 0xff, ab = ah & 0xff
  const br = (bh >> 16) & 0xff, bg = (bh >> 8) & 0xff, bb = bh & 0xff
  const r = Math.round(ar + (br - ar) * t)
  const g = Math.round(ag + (bg - ag) * t)
  const b2 = Math.round(ab + (bb - ab) * t)
  return `#${((r << 16) | (g << 8) | b2).toString(16).padStart(6, '0')}`
}

// Quantile-ish colour scale via sqrt to bring small values into view.
function colourFor(n, maxN) {
  if (!n || !maxN) return '#f3f4f6'
  const t = Math.min(1, Math.sqrt(n / maxN))
  return mix('#fef9c3', '#eab308', t)
}

function KPI({ label, value }) {
  return (
    <div>
      <div className="text-[10px] uppercase tracking-widest text-tq-ink/60">{label}</div>
      <div className="text-xl font-bold font-display">{value.toLocaleString('ca')}</div>
    </div>
  )
}

function totals(stats) {
  return stats.reduce(
    (acc, r) => ({
      n_artistes: acc.n_artistes + (r.n_artistes || 0),
      n_albums:   acc.n_albums + (r.n_albums || 0),
      n_cancons:  acc.n_cancons + (r.n_cancons || 0),
      n_ranking:  acc.n_ranking + (r.n_ranking || 0),
    }),
    { n_artistes: 0, n_albums: 0, n_cancons: 0, n_ranking: 0 },
  )
}

export default function MapaPage() {
  const [selTerritori, setSelTerritori] = useState(null) // codi
  const [selComarca,   setSelComarca]   = useState(null) // name
  const [selMunicipi,  setSelMunicipi]  = useState(null) // { codi, comarca, municipi }

  const level =
    selComarca  ? 'municipi' :
    selTerritori ? 'comarca' :
    'territori'

  const geoPath =
    selComarca  ? `/geodata/municipis-${selTerritori}.json` :
    selTerritori ? `/geodata/comarques-${selTerritori}.json` :
    '/geodata/paisos.json'

  const gj = useGeoJSON(geoPath)

  const [stats, setStats] = useState([])
  useEffect(() => {
    const p = new URLSearchParams({ level })
    if (selTerritori && level !== 'territori') p.set('parent', selTerritori)
    if (selComarca && level === 'municipi') {
      p.set('parent', selComarca)
      p.set('territori', selTerritori)
    }
    api.get(`/mapa/stats/?${p}`)
      .then(setStats)
      .catch(() => setStats([]))
  }, [level, selTerritori, selComarca])

  function keyForFeature(ft) {
    const props = ft.properties || {}
    if (level === 'territori') return props.codi
    if (level === 'comarca')   return `${props.codi}::${props.comarca}`
    return `${props.codi}::${props.comarca}::${props.municipi}`
  }

  const statsByKey = useMemo(() => {
    const m = {}
    for (const r of stats) {
      let k
      if (level === 'territori')     k = r.codi
      else if (level === 'comarca')  k = `${r.codi}::${r.comarca}`
      else                           k = `${r.codi}::${r.comarca}::${r.municipi}`
      m[k] = r
    }
    return m
  }, [stats, level])

  const maxN = useMemo(() => {
    let m = 0
    for (const r of stats) if (r.n_artistes > m) m = r.n_artistes
    return m
  }, [stats])

  // Filter features shown to the parent selection (municipis within a
  // single comarca; comarques within one territori).
  const features = useMemo(() => {
    if (!gj) return []
    let feats = gj.features
    if (level === 'comarca' && selTerritori) {
      feats = feats.filter(ft => ft.properties.codi === selTerritori)
    } else if (level === 'municipi' && selComarca) {
      feats = feats.filter(ft => ft.properties.comarca === selComarca)
    }
    return feats
  }, [gj, level, selTerritori, selComarca])

  const featureBounds = useMemo(
    () => (features.length ? boundsFromGeoJSON({ features }) : null),
    [features],
  )

  const [hovered, setHovered] = useState(null)

  function onFeatureClick(ft) {
    const props = ft.properties || {}
    if (level === 'territori') {
      setSelTerritori(props.codi)
    } else if (level === 'comarca') {
      setSelComarca(props.comarca)
    } else {
      setSelMunicipi({
        codi: props.codi,
        comarca: props.comarca,
        municipi: props.municipi,
      })
    }
  }

  function goUp() {
    if (selMunicipi) setSelMunicipi(null)
    else if (selComarca) setSelComarca(null)
    else if (selTerritori) setSelTerritori(null)
  }

  const title =
    selMunicipi ? selMunicipi.municipi :
    selComarca  ? selComarca :
    selTerritori ? TERRITORI_NOM[selTerritori] :
    'Països Catalans'

  const subtitle =
    selMunicipi ? `${selMunicipi.comarca} · ${TERRITORI_NOM[selMunicipi.codi]}` :
    selComarca  ? TERRITORI_NOM[selTerritori] :
    selTerritori ? 'Territori' :
    'Mapa complet'

  // Artist list for the selected municipi.
  const [artistes, setArtistes] = useState(null)
  useEffect(() => {
    if (!selMunicipi) { setArtistes(null); return }
    const p = new URLSearchParams({
      territori: selMunicipi.codi,
      comarca: selMunicipi.comarca,
      municipi: selMunicipi.municipi,
    })
    api.get(`/mapa/municipi-artistes/?${p}`)
      .then(setArtistes)
      .catch(() => setArtistes([]))
  }, [selMunicipi])

  // Which KPIs does the panel show?
  let kpi
  if (selMunicipi) {
    const k = `${selMunicipi.codi}::${selMunicipi.comarca}::${selMunicipi.municipi}`
    kpi = statsByKey[k] || { n_artistes: 0, n_albums: 0, n_cancons: 0, n_ranking: 0 }
  } else if (selComarca) {
    // We're at municipi level; stats already filtered to this comarca.
    kpi = totals(stats)
  } else if (selTerritori) {
    // We're at comarca level; stats filtered to territori.
    kpi = totals(stats)
  } else {
    kpi = totals(stats)
  }

  const showBackButton = !!selTerritori

  const viewBox = featureBounds
    ? (() => {
        const pad = Math.max(
          (featureBounds.maxX - featureBounds.minX) * 0.02,
          (featureBounds.maxY - featureBounds.minY) * 0.02,
          0.01,
        )
        const x = featureBounds.minX - pad
        const y = -featureBounds.maxY - pad
        const w = featureBounds.maxX - featureBounds.minX + 2 * pad
        const h = featureBounds.maxY - featureBounds.minY + 2 * pad
        return `${x} ${y} ${w} ${h}`
      })()
    : '0 0 10 10'

  return (
    <section className="max-w-6xl mx-auto">
      <div className="grid lg:grid-cols-[1fr_320px] gap-4">
        {/* ── Map ── */}
        <div className="bg-white rounded-lg border border-black/5 p-3 min-h-[500px]">
          {!gj && <p className="text-sm text-tq-ink/60 p-6 text-center">Carregant mapa…</p>}
          {gj && (
            <svg
              viewBox={viewBox}
              xmlns="http://www.w3.org/2000/svg"
              className="w-full h-auto max-h-[70vh]"
            >
              {features.map((ft, i) => {
                const k = keyForFeature(ft)
                const s = statsByKey[k]
                const n = s?.n_artistes || 0
                const fill = colourFor(n, maxN)
                const isHov = hovered === k
                const isSel =
                  (level === 'territori' && selTerritori === ft.properties.codi) ||
                  (level === 'comarca' && selComarca === ft.properties.comarca) ||
                  (level === 'municipi' && selMunicipi &&
                    selMunicipi.municipi === ft.properties.municipi &&
                    selMunicipi.comarca === ft.properties.comarca)
                return (
                  <path
                    key={k + '-' + i}
                    d={geometryToPath(ft.geometry)}
                    fill={fill}
                    stroke={isSel ? '#0a0a0a' : '#9ca3af'}
                    strokeWidth={isSel ? 1.5 : 0.5}
                    opacity={isHov ? 0.85 : 1}
                    onMouseEnter={() => setHovered(k)}
                    onMouseLeave={() => setHovered(null)}
                    onClick={() => onFeatureClick(ft)}
                    style={{ cursor: 'pointer', vectorEffect: 'non-scaling-stroke' }}
                  >
                    <title>
                      {ft.properties.municipi || ft.properties.comarca ||
                        TERRITORI_NOM[ft.properties.codi] || ft.properties.codi}
                      {s ? ` — ${s.n_artistes} artistes` : ''}
                    </title>
                  </path>
                )
              })}
            </svg>
          )}
        </div>

        {/* ── Side panel ── */}
        <aside className="bg-white rounded-lg border border-black/5 p-4 text-tq-ink lg:sticky lg:top-4 h-fit">
          {showBackButton && (
            <button
              type="button"
              onClick={goUp}
              className="text-xs font-semibold text-tq-ink/70 hover:text-tq-ink mb-3"
            >
              ← Tornar
            </button>
          )}
          <p className="text-[10px] uppercase tracking-widest text-tq-ink/60">{subtitle}</p>
          <h1 className="text-2xl font-bold font-display leading-tight mt-0.5 mb-4">
            {title}
          </h1>

          <div className="grid grid-cols-2 gap-3 mb-4">
            <div className="col-span-2">
              <div className="text-[10px] uppercase tracking-widest text-tq-ink/60">
                Artistes
              </div>
              <div className="text-4xl font-bold font-display text-tq-yellow-deep">
                {kpi.n_artistes.toLocaleString('ca')}
              </div>
            </div>
            <KPI label="Àlbums" value={kpi.n_albums} />
            <KPI label="Cançons" value={kpi.n_cancons} />
            <KPI label="Al ranking" value={kpi.n_ranking} />
          </div>

          {selMunicipi && (
            <div>
              <h2 className="text-xs font-semibold uppercase tracking-wide text-tq-ink/70 mb-2 mt-4">
                Artistes del municipi
              </h2>
              {artistes === null && <p className="text-sm text-tq-ink/60">Carregant…</p>}
              {artistes && artistes.length === 0 && (
                <p className="text-sm text-tq-ink/60 italic">Cap artista aprovat encara.</p>
              )}
              {artistes && artistes.length > 0 && (
                <ul className="space-y-1 max-h-[40vh] overflow-y-auto">
                  {artistes.map(a => (
                    <li key={a.pk}>
                      <Link
                        to={`/artista/${a.slug}`}
                        className="text-sm underline hover:text-tq-yellow-deep"
                      >
                        {a.nom}
                      </Link>
                      {a.n_ranking > 0 && (
                        <span className="ml-2 text-[10px] font-semibold uppercase text-tq-yellow-deep">
                          {a.n_ranking} al top
                        </span>
                      )}
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}

          {!selTerritori && (
            <p className="text-[11px] text-tq-ink/60 mt-4">
              Clica un territori al mapa per veure'n les comarques.
            </p>
          )}
          {selTerritori && !selComarca && (
            <p className="text-[11px] text-tq-ink/60 mt-4">
              Clica una comarca per veure'n els municipis.
            </p>
          )}
          {selComarca && !selMunicipi && (
            <p className="text-[11px] text-tq-ink/60 mt-4">
              Clica un municipi per veure'n els artistes.
            </p>
          )}
        </aside>
      </div>
    </section>
  )
}
