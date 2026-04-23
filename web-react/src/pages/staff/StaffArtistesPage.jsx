/**
 * StaffArtistesPage — /staff/artistes
 *
 * Approved-artist directory with filters (aprovat, deezer, territori,
 * search). Each row links to the edit page. Header has a "Nou artista"
 * button.
 */
import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
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

const TERRITORIS = [
  ['', 'Tots els territoris'],
  ['CAT', 'Catalunya'],
  ['VAL', 'País Valencià'],
  ['BAL', 'Illes Balears'],
  ['AND', 'Andorra'],
  ['CNO', 'Catalunya del Nord'],
  ['FRA', 'Franja de Ponent'],
  ['ALG', "L'Alguer"],
  ['PPCC', 'Països Catalans'],
  ['ALT', 'Altres'],
]

export default function StaffArtistesPage() {
  const navigate = useNavigate()
  const [q, setQ] = useState('')
  const [aprovat, setAprovat] = useState('1')
  const [deezer, setDeezer] = useState('')
  const [territori, setTerritori] = useState('')
  const [mb, setMb] = useState('')
  const [page, setPage] = useState(1)
  const [data, setData] = useState(null)

  useEffect(() => {
    const params = new URLSearchParams({
      q,
      aprovat,
      deezer,
      territori,
      mb,
      page,
    })
    api.get(`/staff/artistes/?${params}`).then(setData).catch(() => setData(null))
  }, [q, aprovat, deezer, territori, mb, page])

  return (
    <section>
      <PageHeader
        title="Artistes"
        subtitle={data ? `${data.total} artistes` : 'Carregant…'}
        right={
          <Btn tone="primary" size="md" onClick={() => navigate('/staff/artistes/crear')}>
            + Nou artista
          </Btn>
        }
      />

      <div className="flex flex-wrap gap-2 mb-3">
        <Input
          placeholder="Cerca per nom…"
          value={q}
          onChange={e => {
            setPage(1)
            setQ(e.target.value)
          }}
        />
        <Select value={aprovat} onChange={e => { setPage(1); setAprovat(e.target.value) }}>
          <option value="1">Aprovats</option>
          <option value="0">No aprovats</option>
          <option value="">Tots</option>
        </Select>
        <Select value={deezer} onChange={e => { setPage(1); setDeezer(e.target.value) }}>
          <option value="">Deezer: qualsevol</option>
          <option value="si">Té Deezer</option>
          <option value="no">Sense Deezer</option>
        </Select>
        <Select value={territori} onChange={e => { setPage(1); setTerritori(e.target.value) }}>
          {TERRITORIS.map(([c, l]) => (
            <option key={c} value={c}>{l}</option>
          ))}
        </Select>
        <Select value={mb} onChange={e => { setPage(1); setMb(e.target.value) }}>
          <option value="">MusicBrainz: qualsevol</option>
          <option value="sense_mbid">Sense MBID</option>
          <option value="amb_mbid">Amb MBID</option>
          <option value="dissolt">Dissolts</option>
          <option value="no_sincronitzat">No sincronitzats</option>
        </Select>
      </div>

      <TableCard>
        <Table>
          <THead>
            <tr>
              <Th>Nom</Th>
              <Th>Territoris</Th>
              <Th>Localitat</Th>
              <Th>Deezer</Th>
              <Th>MB</Th>
              <Th>Estat</Th>
              <Th></Th>
            </tr>
          </THead>
          <tbody>
            {data?.results?.length === 0 && (
              <tr><td colSpan={7}><EmptyState>Cap artista.</EmptyState></td></tr>
            )}
            {data?.results?.map(a => (
              <Tr key={a.pk} onClick={() => navigate(`/staff/artistes/${a.pk}`)}>
                <Td>
                  <div className="font-semibold">{a.nom}</div>
                  {a.genere && <div className="text-xs opacity-60">{a.genere}</div>}
                </Td>
                <Td>
                  <div className="flex flex-wrap gap-1">
                    {a.territoris.map(t => <Pill key={t}>{t}</Pill>)}
                  </div>
                </Td>
                <Td className="text-xs">
                  {a.localitat ? (a.localitat.municipi_nom || a.localitat.manual) : <span className="opacity-40">—</span>}
                </Td>
                <Td className="text-xs">{a.deezer_ids.length ? a.deezer_ids.join(', ') : <span className="opacity-40">—</span>}</Td>
                <Td>
                  {a.musicbrainz_id ? (
                    <Pill tone="green">MBID</Pill>
                  ) : a.mb_last_sync ? (
                    <Pill tone="gray">Sense MBID</Pill>
                  ) : (
                    <span className="opacity-40 text-xs">—</span>
                  )}
                  {a.mb_end_date && (
                    <Pill tone="red">Dissolt {a.mb_end_date.slice(0, 4)}</Pill>
                  )}
                </Td>
                <Td>
                  {a.aprovat && <Pill tone="green">Aprovat</Pill>}
                  {!a.aprovat && a.pendent_review && <Pill tone="yellow">Pendent</Pill>}
                  {!a.aprovat && !a.pendent_review && <Pill tone="gray">Descartat</Pill>}
                </Td>
                <Td className="text-right">
                  <Link
                    to={`/artista/${a.slug}`}
                    onClick={e => e.stopPropagation()}
                    className="text-xs underline opacity-70 hover:opacity-100"
                  >
                    perfil públic
                  </Link>
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
