/**
 * HomePage — all-yellow territory selector.
 *
 * Layout: featured wide "General" card on top, then a responsive grid
 * of square territory cards below (logo on top, name below, both
 * centred). The whole selector is vertically centred in the viewport.
 *
 * Hover pattern (same as cercol's instrument cards): the whole card
 * flips to ink bg with yellow foreground.
 *
 * Visible territories: PPCC (General), CAT, VAL, BAL, AND, CNO, FRA,
 * ALG. Hidden: CAR (not viable) and ALT (reachable via the others'
 * fallback).
 */
import { useEffect } from 'react'
import { Link } from 'react-router-dom'

const TERRITORIS_GRID = [
  { codi: 'CAT', nom: 'Catalunya' },
  { codi: 'VAL', nom: 'País Valencià' },
  { codi: 'BAL', nom: 'Illes Balears' },
  { codi: 'AND', nom: 'Andorra' },
  { codi: 'CNO', nom: 'Catalunya del Nord' },
  { codi: 'FRA', nom: 'Franja de Ponent' },
  { codi: 'ALG', nom: "L'Alguer" },
]

function TerritoriCard({ codi, nom, featured = false }) {
  const sizing = featured
    ? 'p-8 md:p-10 gap-4 md:flex-row md:items-center md:gap-8'
    : 'p-5 aspect-square gap-3'

  const iconSize = featured ? 'h-20 w-20 md:h-28 md:w-28' : 'h-14 w-14'
  const textSize = featured ? 'text-2xl md:text-3xl' : 'text-sm md:text-base'

  return (
    <Link
      to={`/top?t=${codi.toLowerCase()}`}
      className={[
        'group flex flex-col items-center justify-center text-center',
        'bg-white text-tq-ink rounded-lg shadow-md',
        'transition-colors duration-150',
        'hover:bg-tq-ink hover:text-tq-yellow',
        sizing,
      ].join(' ')}
    >
      <img
        src={`/static/mm-design/icons/territories/territory-${codi.toLowerCase()}.svg`}
        alt=""
        className={`${iconSize} shrink-0 transition-[filter] duration-150 group-hover:invert`}
        aria-hidden="true"
      />
      <h2 className={`${textSize} font-bold font-display leading-tight`}>
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
      <div className="w-full max-w-5xl space-y-4">
        <TerritoriCard codi="PPCC" nom="General" featured />
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3">
          {TERRITORIS_GRID.map(t => (
            <TerritoriCard key={t.codi} codi={t.codi} nom={t.nom} />
          ))}
        </div>
      </div>
    </div>
  )
}
