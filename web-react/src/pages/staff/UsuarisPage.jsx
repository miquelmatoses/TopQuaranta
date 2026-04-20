/**
 * UsuarisPage — /staff/usuaris
 *
 * Registered users list. Filter by active/role/search. Row links to
 * detail page.
 */
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
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

export default function UsuarisPage() {
  const navigate = useNavigate()
  const [q, setQ] = useState('')
  const [estat, setEstat] = useState('')
  const [rol, setRol] = useState('')
  const [page, setPage] = useState(1)
  const [data, setData] = useState(null)

  useEffect(() => {
    const params = new URLSearchParams({ q, estat, rol, page })
    api.get(`/staff/usuaris/?${params}`).then(setData).catch(() => setData(null))
  }, [q, estat, rol, page])

  return (
    <section>
      <PageHeader title="Usuaris" subtitle={data ? `${data.total} usuaris` : 'Carregant…'} />

      <div className="flex flex-wrap gap-2 mb-3">
        <Input placeholder="Cerca email / username…" value={q} onChange={e => { setPage(1); setQ(e.target.value) }} />
        <Select value={estat} onChange={e => { setPage(1); setEstat(e.target.value) }}>
          <option value="">Estat: tots</option>
          <option value="actius">Actius</option>
          <option value="inactius">Inactius</option>
        </Select>
        <Select value={rol} onChange={e => { setPage(1); setRol(e.target.value) }}>
          <option value="">Rol: tots</option>
          <option value="staff">Staff</option>
          <option value="usuari">Usuari</option>
        </Select>
      </div>

      <TableCard>
        <Table>
          <THead>
            <tr>
              <Th>Email</Th>
              <Th>Username</Th>
              <Th>Estat</Th>
              <Th>Propostes</Th>
              <Th>Sol·l aprovades</Th>
              <Th>Registrat</Th>
              <Th>Últim login</Th>
            </tr>
          </THead>
          <tbody>
            {data?.results?.length === 0 && (
              <tr><td colSpan={7}><EmptyState>Cap usuari.</EmptyState></td></tr>
            )}
            {data?.results?.map(u => (
              <Tr key={u.pk} onClick={() => navigate(`/staff/usuaris/${u.pk}`)}>
                <Td className="font-semibold">{u.email}</Td>
                <Td>{u.username}</Td>
                <Td>
                  {u.is_active ? <Pill tone="green">Actiu</Pill> : <Pill tone="gray">Inactiu</Pill>}
                  {u.is_staff && <Pill tone="yellow">Staff</Pill>}
                  {u.has_totp && <Pill tone="green">2FA</Pill>}
                </Td>
                <Td>{u.n_propostes}</Td>
                <Td>{u.n_sollicituds_aprovades}</Td>
                <Td className="text-xs opacity-70">{u.date_joined?.slice(0, 10)}</Td>
                <Td className="text-xs opacity-70">{u.last_login?.slice(0, 10) || '—'}</Td>
              </Tr>
            ))}
          </tbody>
        </Table>
        <Pagination meta={data} onPage={setPage} />
      </TableCard>
    </section>
  )
}
