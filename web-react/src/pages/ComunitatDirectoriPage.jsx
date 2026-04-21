/**
 * ComunitatDirectoriPage — /comunitat/directori
 *
 * Authenticated-users-only directory of people who've opted in
 * (visible_directori=True). No individual profile page exists —
 * this listing is the maximum exposure surface.
 */
import { useEffect, useState } from 'react'
import { Link, Navigate } from 'react-router-dom'
import { api } from '../lib/api'
import { useAuth } from '../context/AuthContext'
import { ComunitatNav } from './ComunitatPage'

const TERRITORIS = [
  ['',      'Tots els territoris'],
  ['CAT',   'Catalunya'],
  ['VAL',   'País Valencià'],
  ['BAL',   'Illes Balears'],
  ['AND',   'Andorra'],
  ['CNO',   'Catalunya del Nord'],
  ['FRA',   'Franja de Ponent'],
  ['ALG',   "L'Alguer"],
  ['ALT',   'Altres'],
]

export default function ComunitatDirectoriPage() {
  const { profile, loading } = useAuth()
  const [q, setQ] = useState('')
  const [rol, setRol] = useState('')
  const [territori, setTerritori] = useState('')
  const [obert, setObert] = useState(false)
  const [data, setData] = useState(null)
  const [page, setPage] = useState(1)

  useEffect(() => {
    if (!profile) return
    const p = new URLSearchParams({ page })
    if (q) p.set('q', q)
    if (rol) p.set('rol', rol)
    if (territori) p.set('territori', territori)
    if (obert) p.set('obert', '1')
    api.get(`/comunitat/directori/?${p}`).then(setData).catch(() => setData(null))
  }, [profile, q, rol, territori, obert, page])

  if (loading) return null
  if (!profile) return <Navigate to="/compte/accedir?next=/comunitat/directori" replace />

  return (
    <section className="max-w-4xl mx-auto text-white">
      <ComunitatNav />
      <h1 className="text-2xl font-bold mb-1">Directori de la comunitat</h1>
      <p className="text-xs text-white/60 mb-4">
        Usuaris que han decidit ser visibles. Si no hi apareixes, marca la
        casella "Vull aparèixer al directori" al teu <Link to="/compte/perfil-usuari" className="underline">perfil</Link>.
      </p>

      <div className="flex flex-wrap gap-2 mb-4">
        <input
          value={q}
          onChange={e => { setPage(1); setQ(e.target.value) }}
          placeholder="Cerca nom, instrument, bio…"
          className="px-3 py-1.5 rounded border border-white/20 bg-white/5 text-sm text-white placeholder-white/40 focus:outline-none focus:border-tq-yellow"
        />
        <select value={rol} onChange={e => { setPage(1); setRol(e.target.value) }}
                className="px-3 py-1.5 rounded border border-white/20 bg-white/5 text-sm text-white focus:outline-none focus:border-tq-yellow">
          <option value="" className="text-tq-ink">Rol: tots</option>
          {(data?.rol_choices || []).map(([v, l]) => (
            <option key={v} value={v} className="text-tq-ink">{l}</option>
          ))}
        </select>
        <select value={territori} onChange={e => { setPage(1); setTerritori(e.target.value) }}
                className="px-3 py-1.5 rounded border border-white/20 bg-white/5 text-sm text-white focus:outline-none focus:border-tq-yellow">
          {TERRITORIS.map(([c, l]) => (
            <option key={c} value={c} className="text-tq-ink">{l}</option>
          ))}
        </select>
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={obert} onChange={e => { setPage(1); setObert(e.target.checked) }} />
          Obert a col·laboracions
        </label>
      </div>

      {!data && <p className="text-sm text-white/70">Carregant…</p>}
      {data?.results?.length === 0 && (
        <p className="text-sm text-white/60 italic">Cap usuari amb aquests filtres.</p>
      )}

      <ul className="grid sm:grid-cols-2 gap-3">
        {data?.results?.map(u => (
          <li key={u.usuari_id} className="bg-white text-tq-ink rounded-lg p-4">
            <div className="flex items-start gap-3">
              {u.imatge_url ? (
                <img src={u.imatge_url} alt="" className="w-12 h-12 rounded-full object-cover" />
              ) : (
                <div className="w-12 h-12 rounded-full bg-tq-ink/10 flex items-center justify-center text-xs font-bold">
                  {(u.nom_public || u.username).slice(0, 2).toUpperCase()}
                </div>
              )}
              <div className="min-w-0 flex-1">
                <p className="font-bold truncate">{u.nom_public}</p>
                <p className="text-[11px] opacity-70">
                  {u.rol_musical}
                  {u.instruments && ` · ${u.instruments}`}
                </p>
                {u.localitat && <p className="text-[11px] opacity-60 mt-0.5">{u.localitat}</p>}
                {u.obert_colaboracions && (
                  <span className="inline-block mt-1 text-[10px] font-semibold uppercase bg-tq-yellow text-tq-ink px-2 py-0.5 rounded">
                    Obert a col·laboracions
                  </span>
                )}
                {u.artistes_gestionats?.length > 0 && (
                  <p className="text-xs mt-2">
                    Gestiona:{' '}
                    {u.artistes_gestionats.map((a, i) => (
                      <span key={a.slug}>
                        {i > 0 && ', '}
                        <Link to={`/artista/${a.slug}`} className="underline hover:text-tq-yellow-deep">{a.nom}</Link>
                      </span>
                    ))}
                  </p>
                )}
              </div>
            </div>
          </li>
        ))}
      </ul>

      {data?.num_pages > 1 && (
        <div className="flex items-center gap-2 mt-4 text-xs text-white/60">
          <button disabled={!data.has_previous} onClick={() => setPage(p => p - 1)}
                  className="px-3 py-1 rounded border border-white/20 disabled:opacity-40">Anterior</button>
          <span>Pàg {data.page} de {data.num_pages} · {data.total} usuaris</span>
          <button disabled={!data.has_next} onClick={() => setPage(p => p + 1)}
                  className="px-3 py-1 rounded border border-white/20 disabled:opacity-40">Següent</button>
        </div>
      )}
    </section>
  )
}
