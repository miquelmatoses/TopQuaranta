/**
 * HomePage — all-yellow territory selector.
 *
 * Mirrors cercol's home pattern: full-colour canvas, directly actionable.
 * No hero text. A wide "General" card up top (PPCC), then a grid of
 * territory cards (CAT / VAL / BAL / CNO / AND / FRA / ALG / CAR / ALT)
 * each linking to /top?t=<code>. Each card is a white surface with
 * the territory's SVG mark + name.
 */
import { useEffect } from 'react'
import { Link } from 'react-router-dom'

const TERRITORIS_GRID = [
  { codi: 'CAT', nom: 'Catalunya' },
  { codi: 'VAL', nom: 'País Valencià' },
  { codi: 'BAL', nom: 'Illes Balears' },
  { codi: 'CNO', nom: 'Catalunya Nord' },
  { codi: 'AND', nom: 'Andorra' },
  { codi: 'FRA', nom: 'Sud de França' },
  { codi: 'ALG', nom: "L'Alguer" },
  { codi: 'CAR', nom: 'Carxe' },
  { codi: 'ALT', nom: 'Altres' },
]

function TerritoriCard({ codi, nom, featured }) {
  const iconSize = featured ? 'h-24 w-24' : 'h-12 w-12'
  const nameSize = featured ? 'text-2xl' : 'text-base'
  return (
    <Link
      to={`/top?t=${codi.toLowerCase()}`}
      className={[
        'bg-white text-tq-ink rounded-lg shadow-md hover:shadow-lg transition-all hover:-translate-y-0.5',
        'flex items-center gap-4 p-5',
        featured ? 'md:p-7' : '',
      ].join(' ')}
    >
      <img
        src={`/static/mm-design/icons/territories/territory-${codi.toLowerCase()}.svg`}
        alt=""
        className={`${iconSize} shrink-0`}
        aria-hidden="true"
      />
      <div className="min-w-0">
        <p className="text-[10px] font-semibold uppercase tracking-widest text-gray-400">
          Top {featured ? 'general' : ''}
        </p>
        <h2 className={`${nameSize} font-bold font-display leading-tight mt-0.5`}>
          {nom}
        </h2>
      </div>
    </Link>
  )
}

export default function HomePage() {
  useEffect(() => {
    document.body.setAttribute('data-theme', 'yellow')
    return () => document.body.removeAttribute('data-theme')
  }, [])

  return (
    <div className="max-w-6xl mx-auto space-y-4">
      {/* Featured — General (PPCC) */}
      <TerritoriCard codi="PPCC" nom="General" featured />

      {/* Grid of the rest */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
        {TERRITORIS_GRID.map(t => (
          <TerritoriCard key={t.codi} codi={t.codi} nom={t.nom} />
        ))}
      </div>
    </div>
  )
}
