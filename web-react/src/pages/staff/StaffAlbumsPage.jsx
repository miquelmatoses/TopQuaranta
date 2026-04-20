/**
 * StaffAlbumsPage — /staff/albums
 *
 * Directory of albums. Filters: search, tipus, descartat. Click row
 * to edit. Shows a thumbnail, cançó counts (total / verificades) and
 * a Deezer preview link.
 */
import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api } from '../../lib/api'
import {
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

export default function StaffAlbumsPage() {
  const navigate = useNavigate()
  const [q, setQ] = useState('')
  const [tipus, setTipus] = useState('')
  const [descartat, setDescartat] = useState('')
  const [page, setPage] = useState(1)
  const [data, setData] = useState(null)

  useEffect(() => {
    const params = new URLSearchParams({ q, tipus, descartat, page })
    api.get(`/staff/albums/?${params}`).then(setData).catch(() => setData(null))
  }, [q, tipus, descartat, page])

  return (
    <section>
      <PageHeader
        title="Àlbums"
        subtitle={data ? `${data.total} àlbums` : 'Carregant…'}
      />

      <div className="flex flex-wrap gap-2 mb-3">
        <Input
          placeholder="Cerca àlbum o artista…"
          value={q}
          onChange={e => { setPage(1); setQ(e.target.value) }}
        />
        <Select value={tipus} onChange={e => { setPage(1); setTipus(e.target.value) }}>
          <option value="">Tots els tipus</option>
          <option value="album">Àlbum</option>
          <option value="single">Single</option>
          <option value="ep">EP</option>
        </Select>
        <Select value={descartat} onChange={e => { setPage(1); setDescartat(e.target.value) }}>
          <option value="">Tots</option>
          <option value="0">No descartats</option>
          <option value="1">Descartats</option>
        </Select>
      </div>

      <TableCard>
        <Table>
          <THead>
            <tr>
              <Th className="w-16"></Th>
              <Th>Àlbum</Th>
              <Th>Artista</Th>
              <Th>Data</Th>
              <Th>Cançons</Th>
              <Th>Tipus</Th>
              <Th>Estat</Th>
              <Th>Preescolta</Th>
            </tr>
          </THead>
          <tbody>
            {data?.results?.length === 0 && (
              <tr><td colSpan={8}><EmptyState>Cap àlbum.</EmptyState></td></tr>
            )}
            {data?.results?.map(a => (
              <Tr key={a.pk} onClick={() => navigate(`/staff/albums/${a.pk}`)}>
                <Td className="w-16">
                  {a.imatge_url ? (
                    <img
                      src={a.imatge_url}
                      alt=""
                      className="w-12 h-12 rounded object-cover"
                    />
                  ) : (
                    <div className="w-12 h-12 bg-tq-ink/10 rounded" aria-hidden />
                  )}
                </Td>
                <Td>
                  <div className="font-semibold">{a.nom}</div>
                  <Link
                    to={`/album/${a.slug}`}
                    onClick={e => e.stopPropagation()}
                    className="text-[11px] underline opacity-60 hover:opacity-100"
                  >
                    perfil públic
                  </Link>
                </Td>
                <Td>
                  {a.artista.slug ? (
                    <Link
                      to={`/staff/artistes/${a.artista.pk}`}
                      onClick={e => e.stopPropagation()}
                      className="underline"
                    >
                      {a.artista.nom}
                    </Link>
                  ) : a.artista.nom}
                </Td>
                <Td className="text-xs opacity-70">{a.data_llancament || '—'}</Td>
                <Td>
                  <span className="text-sm">{a.n_verificades}</span>
                  <span className="text-xs opacity-60"> / {a.n_cancons}</span>
                </Td>
                <Td><Pill>{a.tipus}</Pill></Td>
                <Td>
                  {a.descartat ? <Pill tone="red">Descartat</Pill> : <Pill tone="green">Actiu</Pill>}
                </Td>
                <Td onClick={e => e.stopPropagation()}>
                  {a.deezer_id ? (
                    <a
                      href={`https://www.deezer.com/album/${a.deezer_id}`}
                      target="_blank"
                      rel="noopener"
                      className="text-xs underline text-tq-ink/70 hover:text-tq-ink whitespace-nowrap"
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
