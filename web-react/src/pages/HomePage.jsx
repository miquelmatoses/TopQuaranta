/**
 * HomePage — all-yellow territory selector.
 *
 * Layout: featured wide "General" card on top, then a single row of
 * 7 square territory cards below (one per viable territory), each
 * tinted with its own colour. Alphabetical by name.
 *
 * Hover pattern (same as cercol's instrument cards): card base is
 * white with the territory colour applied to icon + text; on hover
 * the card fills with the territory colour and the foreground flips
 * to white.
 *
 * Icons are served as monochrome SVGs via CSS `mask-image` so they
 * inherit the element's `color` — standard `<img src>` would render
 * the SVG's default black fill regardless of `currentColor`.
 *
 * Visible territories: PPCC (featured) + alphabetical 7. Hidden:
 * CAR (not viable) and ALT (reachable via the fallback API).
 */
import { useEffect } from 'react'
import { Link } from 'react-router-dom'

/* Territory colours — CAT/VAL/BAL/PPCC match mm-design's brand palette
 * (web/static/web/css/style.css:37-41). AND/CNO/FRA/ALG are new here;
 * pick distinct hues that keep contrast both on white (base) and as a
 * full fill (hover). */
const COLORS = {
  PPCC: '#427c42',  // mm green
  CAT:  '#c99b0c',  // deeper yellow than mm — readable on white
  VAL:  '#cf3339',  // mm red
  BAL:  '#0047ba',  // mm blue
  AND:  '#7c3aed',  // violet
  CNO:  '#0891b2',  // teal
  FRA:  '#ea580c',  // orange
  ALG:  '#db2777',  // pink
}

/* Alphabetical by Catalan name. */
const TERRITORIS_GRID = [
  { codi: 'AND', nom: 'Andorra' },
  { codi: 'CAT', nom: 'Catalunya' },
  { codi: 'CNO', nom: 'Catalunya del Nord' },
  { codi: 'FRA', nom: 'Franja de Ponent' },
  { codi: 'BAL', nom: 'Illes Balears' },
  { codi: 'ALG', nom: "L'Alguer" },
  { codi: 'VAL', nom: 'País Valencià' },
]

function TerritoriCard({ codi, nom, featured = false }) {
  const color = COLORS[codi]
  const iconUrl = `/static/mm-design/icons/territories/territory-${codi.toLowerCase()}.svg`

  const sizing = featured
    ? 'p-8 md:p-10 gap-4 md:flex-row md:items-center md:gap-8'
    : 'p-3 aspect-square gap-2'
  const iconClass = featured ? 'h-20 w-20 md:h-28 md:w-28' : 'h-10 w-10 md:h-12 md:w-12'
  const textClass = featured ? 'text-2xl md:text-3xl' : 'text-xs md:text-sm'

  return (
    <Link
      to={`/top?t=${codi.toLowerCase()}`}
      style={{ '--tc': color }}
      className={[
        'group flex flex-col items-center justify-center text-center',
        'bg-white rounded-lg shadow-md',
        'text-[var(--tc)] hover:bg-[var(--tc)] hover:text-white',
        'transition-colors duration-150',
        sizing,
      ].join(' ')}
    >
      <span
        aria-hidden="true"
        className={`${iconClass} shrink-0`}
        style={{
          display: 'inline-block',
          backgroundColor: 'currentColor',
          WebkitMaskImage: `url(${iconUrl})`,
          maskImage: `url(${iconUrl})`,
          WebkitMaskRepeat: 'no-repeat',
          maskRepeat: 'no-repeat',
          WebkitMaskPosition: 'center',
          maskPosition: 'center',
          WebkitMaskSize: 'contain',
          maskSize: 'contain',
        }}
      />
      <h2 className={`${textClass} font-bold font-display leading-tight`}>
        {nom}
      </h2>
    </Link>
  )
}

export default function HomePage() {
  useEffect(() => {
    document.body.setAttribute('data-theme', 'yellow')
    return () => document.body.removeAttribute('data-theme')
  }, [])

  return (
    <div className="min-h-[calc(100vh-10rem)] flex items-center justify-center">
      <div className="w-full max-w-6xl space-y-4">
        <TerritoriCard codi="PPCC" nom="General" featured />
        <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-2 md:gap-3">
          {TERRITORIS_GRID.map(t => (
            <TerritoriCard key={t.codi} codi={t.codi} nom={t.nom} />
          ))}
        </div>
      </div>
    </div>
  )
}
