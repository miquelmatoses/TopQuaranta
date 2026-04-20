/**
 * CancoEditPage — /staff/cancons/:pk
 *
 * Simple edit form for a single track.
 */
import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { api } from '../../lib/api'
import { Btn, Input, PageHeader, TableCard } from '../../components/staff/StaffTable'
import ArtistaPicker from '../../components/staff/ArtistaPicker'

export default function CancoEditPage() {
  const { pk } = useParams()
  const navigate = useNavigate()
  const [c, setC] = useState(null)
  const [err, setErr] = useState('')
  const [msg, setMsg] = useState('')
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    api.get(`/staff/cancons/${pk}/`).then(setC).catch(e => setErr(e.message))
  }, [pk])

  if (err) return <p className="text-red-300">{err}</p>
  if (!c) return <p className="text-white/70">Carregant…</p>

  function patch(p) { setC(prev => ({ ...prev, ...p })) }

  async function save() {
    setBusy(true); setErr(''); setMsg('')
    try {
      const out = await api.patch(`/staff/cancons/${pk}/`, {
        nom: c.nom,
        isrc: c.isrc,
        lastfm_nom: c.lastfm_nom,
        verificada: c.verificada,
        activa: c.activa,
        data_llancament: c.data_llancament,
        deezer_id: c.deezer_id,
        // Empty string means "don't change" on the backend.
        artista_pk: c.artista?.pk,
      })
      setC(out)
      setMsg('Desat.')
    } catch (e) {
      setErr(e.payload?.error || e.message)
    } finally { setBusy(false) }
  }

  return (
    <section>
      <PageHeader
        title={`Editar cançó: ${c.nom}`}
        subtitle={<Link to={`/canco/${c.slug}`} className="underline">perfil públic</Link>}
        right={
          <>
            {c.deezer_id && (
              <a
                href={`https://www.deezer.com/track/${c.deezer_id}`}
                target="_blank"
                rel="noopener"
                className="text-sm font-semibold px-3 py-1.5 rounded bg-white/10 text-white hover:bg-white/20 transition-colors"
              >
                ▶ Escoltar a Deezer
              </a>
            )}
            <Btn tone="secondary" size="md" onClick={() => navigate('/staff/cancons')}>Tornar</Btn>
            <Btn size="md" onClick={save} disabled={busy}>Desar</Btn>
          </>
        }
      />
      {err && <p className="text-red-300 mb-3">{err}</p>}
      {msg && <p className="text-emerald-300 mb-3">{msg}</p>}
      <TableCard className="p-4 max-w-2xl">
        <div className="grid gap-3">
          <label className="text-xs font-semibold">Nom
            <Input value={c.nom} onChange={e => patch({ nom: e.target.value })} className="w-full mt-1 font-normal" />
          </label>
          <div className="text-xs font-semibold">
            Artista
            <div className="mt-1 font-normal">
              <ArtistaPicker
                value={c.artista?.pk ? c.artista : null}
                onChange={next => patch({ artista: next })}
              />
            </div>
            <p className="mt-1 text-[11px] font-normal text-tq-ink/60">
              Si l'artista correcte no existeix, clica "+ Crear" per afegir-lo
              primer, després torna aquí i tria'l de la llista.
            </p>
          </div>
          {c.album && (
            <label className="text-xs font-semibold">Àlbum
              <div className="mt-1 font-normal text-sm">
                <Link className="underline" to={`/staff/albums/${c.album.pk}`}>{c.album.nom}</Link>
              </div>
            </label>
          )}
          <label className="text-xs font-semibold">ISRC
            <Input value={c.isrc || ''} onChange={e => patch({ isrc: e.target.value })} className="w-full mt-1 font-normal" />
          </label>
          <label className="text-xs font-semibold">Nom Last.fm
            <Input value={c.lastfm_nom || ''} onChange={e => patch({ lastfm_nom: e.target.value })} className="w-full mt-1 font-normal" />
          </label>
          <label className="text-xs font-semibold">Deezer ID
            <Input value={c.deezer_id || ''} inputMode="numeric" onChange={e => patch({ deezer_id: e.target.value })} className="w-full mt-1 font-normal" />
          </label>
          <label className="text-xs font-semibold">Data llançament
            <Input type="date" value={c.data_llancament || ''} onChange={e => patch({ data_llancament: e.target.value })} className="w-full mt-1 font-normal" />
          </label>
          <label className="text-xs font-semibold flex items-center gap-2">
            <input type="checkbox" checked={c.verificada} onChange={e => patch({ verificada: e.target.checked })} />
            Verificada
          </label>
          <label className="text-xs font-semibold flex items-center gap-2">
            <input type="checkbox" checked={c.activa} onChange={e => patch({ activa: e.target.checked })} />
            Activa
          </label>
        </div>
      </TableCard>
    </section>
  )
}
