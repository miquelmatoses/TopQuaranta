/**
 * StaffCanconsPage — /staff/cancons
 *
 * Track moderation. Bulk select + approve/reject. Filters for
 * verificada state, ml_classe, whisper, and free-text search.
 */
import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../../lib/api'
import {
  Btn,
  EmptyState,
  Input,
  PageHeader,
  Pagination,
  Pill,
  Select,
  Table,
  TableCard,
  Td,
  Th,
  THead,
  Tr,
} from '../../components/staff/StaffTable'

const MOTIUS = [
  'llengua_incorrecta',
  'artista_incorrecte',
  'album_incorrecte',
  'duplicat',
  'altre',
]

export default function StaffCanconsPage() {
  const navigate = useNavigate()
  const [q, setQ] = useState('')
  const [verificada, setVerificada] = useState('0')
  const [mlClasse, setMlClasse] = useState('')
  const [whisper, setWhisper] = useState('')
  const [page, setPage] = useState(1)
  const [data, setData] = useState(null)
  const [sel, setSel] = useState(new Set())
  const [motiu, setMotiu] = useState('llengua_incorrecta')
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState('')

  function load() {
    const params = new URLSearchParams({ q, verificada, ml_classe: mlClasse, whisper, page })
    api.get(`/staff/cancons/?${params}`).then(setData).catch(() => setData(null))
  }

  useEffect(load, [q, verificada, mlClasse, whisper, page])

  const allSelected = data?.results?.length && data.results.every(r => sel.has(r.pk))

  function toggle(pk) {
    setSel(s => {
      const n = new Set(s)
      if (n.has(pk)) n.delete(pk)
      else n.add(pk)
      return n
    })
  }
  function toggleAll() {
    if (!data) return
    setSel(s => {
      const n = new Set(s)
      const allHere = data.results.every(r => n.has(r.pk))
      data.results.forEach(r => (allHere ? n.delete(r.pk) : n.add(r.pk)))
      return n
    })
  }

  async function act(action) {
    if (sel.size === 0) {
      setMsg('Cap cançó seleccionada.')
      return
    }
    setBusy(true)
    setMsg('')
    try {
      const out = await api.post('/staff/cancons/accio/', {
        action,
        ids: [...sel],
        motiu,
      })
      setMsg(out.msg || `${out.n || sel.size} cançons processades.`)
      setSel(new Set())
      load()
    } catch (e) {
      setMsg(e.payload?.error || e.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <section>
      <PageHeader title="Cançons" subtitle={data ? `${data.total} cançons` : 'Carregant…'} />

      <div className="flex flex-wrap gap-2 mb-3">
        <Input placeholder="Cerca cançó o artista…" value={q} onChange={e => { setPage(1); setQ(e.target.value) }} />
        <Select value={verificada} onChange={e => { setPage(1); setVerificada(e.target.value) }}>
          <option value="0">No verificades</option>
          <option value="1">Verificades</option>
          <option value="">Totes</option>
        </Select>
        <Select value={mlClasse} onChange={e => { setPage(1); setMlClasse(e.target.value) }}>
          <option value="">ML: totes</option>
          <option value="A">Classe A</option>
          <option value="B">Classe B</option>
          <option value="C">Classe C</option>
        </Select>
        <Select value={whisper} onChange={e => { setPage(1); setWhisper(e.target.value) }}>
          <option value="">Whisper: qualsevol</option>
          <option value="ca">ca</option>
          <option value="no_ca">no ca</option>
          <option value="pendent">pendent</option>
        </Select>
      </div>

      {sel.size > 0 && (
        <div className="flex flex-wrap gap-2 mb-3 p-2 bg-tq-yellow/90 text-tq-ink rounded">
          <span className="text-sm font-semibold">{sel.size} seleccionades</span>
          <Select value={motiu} onChange={e => setMotiu(e.target.value)}>
            {MOTIUS.map(m => <option key={m} value={m}>{m}</option>)}
          </Select>
          <Btn onClick={() => act('aprovar')} disabled={busy}>Aprovar</Btn>
          <Btn tone="danger" onClick={() => act('rebutjar')} disabled={busy}>Rebutjar</Btn>
          <Btn tone="secondary" onClick={() => setSel(new Set())} disabled={busy}>Netejar</Btn>
        </div>
      )}

      {msg && <p className="text-sm text-white/80 mb-3">{msg}</p>}

      <TableCard>
        <Table>
          <THead>
            <tr>
              <Th className="w-8"><input type="checkbox" checked={!!allSelected} onChange={toggleAll} /></Th>
              <Th>Cançó</Th>
              <Th>Artista</Th>
              <Th>Àlbum</Th>
              <Th>ML</Th>
              <Th>Whisper</Th>
              <Th>Estat</Th>
              <Th>Preescolta</Th>
            </tr>
          </THead>
          <tbody>
            {data?.results?.length === 0 && (
              <tr><td colSpan={8}><EmptyState>Cap cançó.</EmptyState></td></tr>
            )}
            {data?.results?.map(c => (
              <Tr key={c.pk} onClick={() => navigate(`/staff/cancons/${c.pk}`)}>
                <Td className="w-8" onClick={e => e.stopPropagation()}>
                  <input type="checkbox" checked={sel.has(c.pk)} onChange={() => toggle(c.pk)} />
                </Td>
                <Td>
                  <div className="font-semibold">{c.nom}</div>
                  {c.isrc && <div className="text-[11px] opacity-60">ISRC {c.isrc}</div>}
                </Td>
                <Td>{c.artista.nom}</Td>
                <Td className="text-xs opacity-70">{c.album?.nom || '—'}</Td>
                <Td>
                  {c.ml_classe && <Pill tone={c.ml_classe === 'A' ? 'green' : c.ml_classe === 'C' ? 'red' : 'yellow'}>{c.ml_classe}</Pill>}
                  {c.ml_confianca != null && <span className="text-[11px] ml-1 opacity-60">{Math.round(c.ml_confianca * 100)}%</span>}
                </Td>
                <Td>
                  {c.whisper_lang ? <Pill tone={c.whisper_lang === 'ca' ? 'green' : 'red'}>{c.whisper_lang}</Pill> : <span className="opacity-40 text-xs">—</span>}
                </Td>
                <Td>
                  {c.verificada ? <Pill tone="green">Verificada</Pill> : <Pill tone="gray">Pendent</Pill>}
                  {!c.activa && <Pill tone="red">Inactiva</Pill>}
                </Td>
                <Td className="text-right" onClick={e => e.stopPropagation()}>
                  {c.deezer_id ? (
                    <a
                      href={`https://www.deezer.com/track/${c.deezer_id}`}
                      target="_blank"
                      rel="noopener"
                      className="text-xs underline text-tq-ink/70 hover:text-tq-ink whitespace-nowrap"
                      title="Escoltar a Deezer"
                    >
                      ▶ Deezer
                    </a>
                  ) : (
                    <span className="text-[11px] opacity-40">—</span>
                  )}
                </Td>
              </Tr>
            ))}
          </tbody>
        </Table>
        <Pagination meta={data} onPage={setPage} />
      </TableCard>
    </section>
  )
}
