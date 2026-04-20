/**
 * StaffRankingPage — /staff/ranking
 *
 * Provisional ranking review, per territory. Bulk select + reject
 * (canco or artist). No pagination: always shows the full top-40.
 */
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../../lib/api'
import {
  Btn,
  EmptyState,
  PageHeader,
  Pill,
  Select,
  Table,
  TableCard,
  Td,
  Th,
  THead,
  Tr,
} from '../../components/staff/StaffTable'

export default function StaffRankingPage() {
  const [territori, setTerritori] = useState('CAT')
  const [data, setData] = useState(null)
  const [sel, setSel] = useState(new Set())
  const [motiu, setMotiu] = useState('artista_incorrecte')
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState('')

  function load() {
    setData(null)
    api.get(`/staff/ranking/?territori=${territori}`).then(setData).catch(() => setData(null))
  }
  useEffect(load, [territori])

  function toggle(pk) {
    setSel(s => {
      const n = new Set(s)
      n.has(pk) ? n.delete(pk) : n.add(pk)
      return n
    })
  }

  async function act(action) {
    if (sel.size === 0) { setMsg('Cap entrada seleccionada.'); return }
    if (!confirm(`${action} ${sel.size} entrades amb motiu "${motiu}"?`)) return
    setBusy(true); setMsg('')
    try {
      const out = await api.post('/staff/ranking/accio/', {
        action,
        ids: [...sel],
        motiu,
      })
      setMsg(`Fet. ${out.n || out.n_cancons} cançons afectades.`)
      setSel(new Set())
      load()
    } catch (e) {
      setMsg(e.payload?.error || e.message)
    } finally { setBusy(false) }
  }

  return (
    <section>
      <PageHeader
        title="Ranking provisional"
        subtitle={data ? `${data.entries.length} entrades a ${territori}` : 'Carregant…'}
      />

      <div className="flex flex-wrap gap-2 mb-3">
        <Select value={territori} onChange={e => setTerritori(e.target.value)}>
          {data?.territoris?.map(t => (
            <option key={t.codi} value={t.codi}>{t.codi} — {t.nom}</option>
          ))}
          {!data && <option value="CAT">CAT</option>}
        </Select>
      </div>

      {sel.size > 0 && (
        <div className="flex flex-wrap gap-2 mb-3 p-2 bg-tq-yellow/90 text-tq-ink rounded">
          <span className="text-sm font-semibold">{sel.size} seleccionades</span>
          <Select value={motiu} onChange={e => setMotiu(e.target.value)}>
            {data?.motius?.map(m => <option key={m} value={m}>{m}</option>)}
          </Select>
          <Btn tone="danger" onClick={() => act('rebutjar_canco')} disabled={busy}>Rebutjar cançons</Btn>
          <Btn tone="danger" onClick={() => act('rebutjar_artista')} disabled={busy}>Rebutjar artistes</Btn>
          <Btn tone="secondary" onClick={() => setSel(new Set())} disabled={busy}>Netejar</Btn>
        </div>
      )}

      {msg && <p className="text-sm text-white/80 mb-3">{msg}</p>}

      <TableCard>
        <Table>
          <THead>
            <tr>
              <Th className="w-8"></Th>
              <Th>#</Th>
              <Th>Cançó</Th>
              <Th>Artista</Th>
              <Th>Playcount</Th>
              <Th>Dies al top</Th>
            </tr>
          </THead>
          <tbody>
            {data?.entries?.length === 0 && (
              <tr><td colSpan={6}><EmptyState>Cap entrada.</EmptyState></td></tr>
            )}
            {data?.entries?.map(e => (
              <Tr key={e.pk}>
                <Td><input type="checkbox" checked={sel.has(e.pk)} onChange={() => toggle(e.pk)} /></Td>
                <Td className="font-bold">{e.posicio}</Td>
                <Td>
                  {e.canco_pk ? (
                    <Link className="underline hover:text-tq-ink" to={`/staff/cancons/${e.canco_pk}`}>
                      {e.canco_nom}
                    </Link>
                  ) : e.canco_nom}
                </Td>
                <Td>
                  {e.artista_pk ? (
                    <Link className="underline hover:text-tq-ink" to={`/staff/artistes/${e.artista_pk}`}>
                      {e.artista_nom}
                    </Link>
                  ) : e.artista_nom}
                </Td>
                <Td className="text-xs">{e.lastfm_playcount?.toLocaleString()}</Td>
                <Td className="text-xs">{e.dies_en_top}</Td>
              </Tr>
            ))}
          </tbody>
        </Table>
      </TableCard>
    </section>
  )
}
