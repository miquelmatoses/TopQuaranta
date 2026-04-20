/**
 * MapaPage — placeholder.
 *
 * The old Django template rendered a three-zoom-level D3 map
 * (territories → comarques → municipis) with artist counts. Porting
 * that to React is its own sprint; for now this page points users to
 * the artistes directory with territory filters, which covers the
 * same "explore by place" need while the real map is being built.
 */
import { Link } from 'react-router-dom'

const TERRITORIS = [
  { codi: 'cat', nom: 'Catalunya' },
  { codi: 'val', nom: 'País Valencià' },
  { codi: 'bal', nom: 'Illes Balears' },
]

export default function MapaPage() {
  return (
    <section className="max-w-3xl mx-auto text-white">
      <h1 className="text-3xl font-bold mb-3">Mapa</h1>
      <p className="text-sm text-tq-ink-muted mb-6">
        El mapa interactiu per comarques i municipis es torna a
        construir. Mentrestant pots explorar per territori:
      </p>
      <ul className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        {TERRITORIS.map(t => (
          <li key={t.codi}>
            <Link
              to={`/artistes?territori=${t.codi}`}
              className="block bg-white text-tq-ink rounded-lg p-4 shadow-md hover:shadow-lg transition-shadow"
            >
              <p className="text-sm font-semibold">{t.nom}</p>
              <p className="text-xs text-gray-500 mt-1">Veure artistes</p>
            </Link>
          </li>
        ))}
      </ul>
    </section>
  )
}
