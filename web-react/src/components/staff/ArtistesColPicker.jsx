/**
 * ArtistesColPicker — multi-select of Artistes for canco.artistes_col.
 *
 * Renders the current collaborators as dismissable pills plus a
 * typeahead at the bottom to add new ones (same UX as ArtistaPicker,
 * but additive instead of replacement).
 *
 * Emits `onChange(newList)` with the full Artista[] array each time
 * something is added or removed — the parent just needs to bind the
 * list on its state and send `artistes_col_pks` in the PATCH body.
 *
 * `blockedPk` (optional) prevents adding that artist (used to exclude
 * the main artist from the collab list, mirroring the backend D5
 * check).
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

export default function ArtistesColPicker({ value = [], onChange, blockedPk }) {
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

  const currentPks = new Set(value.map(a => a.pk))

  function add(a) {
    if (currentPks.has(a.pk)) return
    if (blockedPk && a.pk === blockedPk) return
    onChange([...value, a])
    setQ('')
    setOpen(false)
  }

  function remove(pk) {
    onChange(value.filter(a => a.pk !== pk))
  }

  return (
    <div>
      {value.length > 0 ? (
        <ul className="flex flex-wrap gap-1 mb-2">
          {value.map(a => (
            <li key={a.pk}>
              <span className="inline-flex items-center gap-1 bg-tq-ink/5 text-tq-ink text-xs rounded-full pl-2 pr-1 py-0.5">
                <span className="font-semibold">{a.nom}</span>
                {!a.aprovat && (
                  <span className="text-[9px] uppercase bg-yellow-100 text-yellow-900 px-1 rounded">
                    pendent
                  </span>
                )}
                <button
                  type="button"
                  onClick={() => remove(a.pk)}
                  aria-label={`Eliminar ${a.nom}`}
                  className="text-red-600 hover:text-red-800 px-1.5 text-sm leading-none"
                >
                  ×
                </button>
              </span>
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-[11px] opacity-60 mb-2">Cap col·laborador.</p>
      )}

      <div className="relative">
        <input
          value={q}
          onChange={e => {
            setQ(e.target.value)
            setOpen(true)
          }}
          onFocus={() => setOpen(true)}
          onBlur={() => setTimeout(() => setOpen(false), 150)}
          className="w-full text-sm px-2.5 py-1.5 rounded border border-tq-ink/20 bg-white text-tq-ink focus:outline-none focus:ring-2 focus:ring-tq-yellow"
          placeholder="Afegir col·laborador…"
        />
        {open && q.length >= 2 && (
          <ul className="absolute left-0 right-0 top-full mt-1 bg-white text-tq-ink rounded-md shadow-lg max-h-64 overflow-auto z-10 border border-black/10">
            {loading && (
              <li className="px-3 py-2 text-xs text-gray-500">Cercant…</li>
            )}
            {!loading && results.length === 0 && (
              <li className="px-3 py-2 text-xs text-gray-500">Sense resultats</li>
            )}
            {results.map(a => {
              const isBlocked = blockedPk && a.pk === blockedPk
              const isAlreadyThere = currentPks.has(a.pk)
              const disabled = isBlocked || isAlreadyThere
              return (
                <li key={a.pk}>
                  <button
                    type="button"
                    disabled={disabled}
                    onMouseDown={e => {
                      e.preventDefault()
                      if (!disabled) add(a)
                    }}
                    className={
                      'w-full text-left px-3 py-2 text-sm flex items-center gap-2 ' +
                      (disabled
                        ? 'opacity-40 cursor-not-allowed'
                        : 'hover:bg-tq-yellow/10')
                    }
                  >
                    <span className="font-semibold">{a.nom}</span>
                    <span className="text-[10px] opacity-50">pk={a.pk}</span>
                    {isBlocked && (
                      <span className="ml-auto text-[10px] italic">
                        (és l'artista principal)
                      </span>
                    )}
                    {isAlreadyThere && !isBlocked && (
                      <span className="ml-auto text-[10px] italic">
                        (ja afegit)
                      </span>
                    )}
                  </button>
                </li>
              )
            })}
          </ul>
        )}
      </div>
    </div>
  )
}
