/**
 * ArtistaPicker — typeahead search + "Crear nou" escape hatch.
 *
 * Used on CancoEditPage + AlbumEditPage to reassign a track or album
 * to a different (or brand-new) artist. The "Crear nou" button opens
 * /staff/artistes/crear in a new tab so the staff flow isn't lost —
 * when they come back, the typeahead will find the freshly-created
 * artist immediately.
 */
import { useEffect, useState } from 'react'
import { api } from '../../lib/api'

function useDebounced(value, ms = 200) {
  const [v, setV] = useState(value)
  useEffect(() => {
    const t = setTimeout(() => setV(value), ms)
    return () => clearTimeout(t)
  }, [value, ms])
  return v
}

export default function ArtistaPicker({ value, onChange }) {
  const [q, setQ] = useState('')
  const dq = useDebounced(q)
  const [results, setResults] = useState([])
  const [open, setOpen] = useState(false)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!dq || dq.length < 2) {
      setResults([])
      return
    }
    setLoading(true)
    api
      .get(`/staff/artistes/search/?q=${encodeURIComponent(dq)}`)
      .then(r => setResults(r.results || []))
      .catch(() => setResults([]))
      .finally(() => setLoading(false))
  }, [dq])

  if (value) {
    return (
      <div className="flex items-center gap-2 bg-tq-ink/5 text-tq-ink rounded-md px-3 py-2 text-sm">
        <span className="font-semibold">{value.nom}</span>
        <span className="text-[10px] opacity-60">pk={value.pk}</span>
        {!value.aprovat && (
          <span className="text-[10px] uppercase bg-yellow-200 text-yellow-900 px-1.5 py-0.5 rounded">
            {value.pendent_review ? 'pendent' : 'no aprovat'}
          </span>
        )}
        <button
          type="button"
          onClick={() => onChange(null)}
          className="ml-auto text-xs text-red-600 hover:underline"
        >
          canviar
        </button>
      </div>
    )
  }

  return (
    <div className="relative">
      <div className="flex gap-2">
        <input
          value={q}
          onChange={e => {
            setQ(e.target.value)
            setOpen(true)
          }}
          onFocus={() => setOpen(true)}
          onBlur={() => setTimeout(() => setOpen(false), 150)}
          className="flex-1 text-sm px-2.5 py-1.5 rounded border border-tq-ink/20 bg-white text-tq-ink focus:outline-none focus:ring-2 focus:ring-tq-yellow"
          placeholder="Cerca artista per reassignar…"
        />
        <a
          href="/staff/artistes/crear"
          target="_blank"
          rel="noopener"
          className="text-xs font-semibold px-2.5 py-1.5 rounded bg-tq-yellow text-tq-ink hover:bg-tq-yellow-deep hover:text-white whitespace-nowrap"
        >
          + Crear
        </a>
      </div>
      {open && q.length >= 2 && (
        <ul className="absolute left-0 right-0 top-full mt-1 bg-white text-tq-ink rounded-md shadow-lg max-h-64 overflow-auto z-10 border border-black/10">
          {loading && <li className="px-3 py-2 text-xs text-gray-500">Cercant…</li>}
          {!loading && results.length === 0 && (
            <li className="px-3 py-2 text-xs text-gray-500">
              Sense resultats. Fes servir "+ Crear" per afegir-lo al sistema.
            </li>
          )}
          {results.map(a => (
            <li key={a.pk}>
              <button
                type="button"
                onMouseDown={e => {
                  e.preventDefault()
                  onChange(a)
                  setQ('')
                  setOpen(false)
                }}
                className="w-full text-left px-3 py-2 text-sm hover:bg-tq-yellow/10 flex items-center gap-2"
              >
                <span className="font-semibold">{a.nom}</span>
                <span className="text-[10px] opacity-50">pk={a.pk}</span>
                {!a.aprovat && (
                  <span className="ml-auto text-[10px] uppercase bg-yellow-100 text-yellow-900 px-1.5 py-0.5 rounded">
                    {a.pendent_review ? 'pendent' : 'no aprovat'}
                  </span>
                )}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
