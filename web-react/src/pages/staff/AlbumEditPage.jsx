/**
 * AlbumEditPage — /staff/albums/:pk
 *
 * Single-album editor. Lists contained tracks with quick-links to
 * their individual staff edit pages.
 */
import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { api } from '../../lib/api'
import {
  Btn,
  Input,
  PageHeader,
  Pill,
  Table,
  TableCard,
  Td,
  Th,
  THead,
  Tr,
} from '../../components/staff/StaffTable'

export default function AlbumEditPage() {
  const { pk } = useParams()
  const navigate = useNavigate()
  const [a, setA] = useState(null)
  const [err, setErr] = useState('')
  const [msg, setMsg] = useState('')
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    api.get(`/staff/albums/${pk}/`).then(setA).catch(e => setErr(e.message))
  }, [pk])

  if (err) return <p className="text-red-300">{err}</p>
  if (!a) return <p className="text-white/70">Carregant…</p>

  function patch(p) { setA(prev => ({ ...prev, ...p })) }

  async function save() {
    setBusy(true); setErr(''); setMsg('')
    try {
      const out = await api.patch(`/staff/albums/${pk}/`, {
        nom: a.nom,
        data_llancament: a.data_llancament,
        tipus: a.tipus,
        deezer_id: a.deezer_id,
        imatge_url: a.imatge_url,
        descartat: a.descartat,
      })
      setA(out)
      setMsg('Desat.')
    } catch (e) {
      setErr(e.payload?.error || e.message)
    } finally { setBusy(false) }
  }

  return (
    <section>
      <PageHeader
        title={`Àlbum: ${a.nom}`}
        subtitle={`de ${a.artista.nom}`}
        right={
          <>
            <Btn tone="secondary" size="md" onClick={() => navigate(-1)}>Tornar</Btn>
            <Btn size="md" onClick={save} disabled={busy}>Desar</Btn>
          </>
        }
      />
      {err && <p className="text-red-300 mb-3">{err}</p>}
      {msg && <p className="text-emerald-300 mb-3">{msg}</p>}

      <div className="grid lg:grid-cols-[1fr_1.5fr] gap-4">
        <TableCard className="p-4">
          <h2 className="font-semibold mb-3">Metadades</h2>
          <div className="grid gap-3">
            <label className="text-xs font-semibold">Nom
              <Input value={a.nom} onChange={e => patch({ nom: e.target.value })} className="w-full mt-1 font-normal" />
            </label>
            <label className="text-xs font-semibold">Data llançament
              <Input type="date" value={a.data_llancament || ''} onChange={e => patch({ data_llancament: e.target.value })} className="w-full mt-1 font-normal" />
            </label>
            <label className="text-xs font-semibold">Tipus
              <Input value={a.tipus || ''} onChange={e => patch({ tipus: e.target.value })} className="w-full mt-1 font-normal" />
            </label>
            <label className="text-xs font-semibold">Deezer ID
              <Input value={a.deezer_id || ''} inputMode="numeric" onChange={e => patch({ deezer_id: e.target.value })} className="w-full mt-1 font-normal" />
            </label>
            <label className="text-xs font-semibold">URL imatge
              <Input value={a.imatge_url || ''} onChange={e => patch({ imatge_url: e.target.value })} className="w-full mt-1 font-normal" />
            </label>
            <label className="text-xs font-semibold flex items-center gap-2">
              <input type="checkbox" checked={a.descartat} onChange={e => patch({ descartat: e.target.checked })} />
              Descartat
            </label>
            {a.imatge_url && (
              <img src={a.imatge_url} alt="" className="mt-2 w-32 h-32 rounded object-cover" />
            )}
          </div>
        </TableCard>

        <TableCard>
          <h2 className="p-3 font-semibold">Cançons ({a.cancons.length})</h2>
          <Table>
            <THead>
              <tr><Th>Nom</Th><Th>Verificada</Th><Th></Th></tr>
            </THead>
            <tbody>
              {a.cancons.map(c => (
                <Tr key={c.pk}>
                  <Td>{c.nom}</Td>
                  <Td>{c.verificada ? <Pill tone="green">Sí</Pill> : <Pill tone="gray">No</Pill>}</Td>
                  <Td className="text-right">
                    <Link className="underline text-xs" to={`/staff/cancons/${c.pk}`}>editar</Link>
                  </Td>
                </Tr>
              ))}
            </tbody>
          </Table>
        </TableCard>
      </div>
    </section>
  )
}
