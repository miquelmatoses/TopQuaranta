/**
 * StaffDirectoriUsuarisPage — /staff/directori-usuaris
 *
 * Staff view over every PerfilUsuari (beyond the public
 * `visible_directori=True` ones). Allows toggling the visibility
 * flag directly from the list — used as a moderation lever for
 * spam / abusive profiles.
 */
import { useEffect, useState } from 'react'
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

export default function StaffDirectoriUsuarisPage() {
  const [q, setQ] = useState('')
  const [visible, setVisible] = useState('')
  const [page, setPage] = useState(1)
  const [data, setData] = useState(null)
  const [busy, setBusy] = useState(null)

  function load() {
    const params = new URLSearchParams({ q, visible, page })
    api.get(`/staff/directori-usuaris/?${params}`).then(setData).catch(() => setData(null))
  }
  useEffect(load, [q, visible, page])

  async function toggle(usuari_id) {
    setBusy(usuari_id)
    try {
      await api.post(`/staff/directori-usuaris/${usuari_id}/toggle/`)
      load()
    } finally {
      setBusy(null)
    }
  }

  return (
    <section>
      <PageHeader
        title="Directori d'usuaris"
        subtitle={data ? `${data.total} usuaris amb perfil` : 'Carregant…'}
      />
      <div className="flex flex-wrap gap-2 mb-3">
        <Input placeholder="Cerca email, username, nom…" value={q} onChange={e => { setPage(1); setQ(e.target.value) }} />
        <Select value={visible} onChange={e => { setPage(1); setVisible(e.target.value) }}>
          <option value="">Visibilitat: totes</option>
          <option value="1">Al directori</option>
          <option value="0">Ocult</option>
        </Select>
      </div>

      <TableCard>
        <Table>
          <THead>
            <tr>
              <Th>Usuari</Th>
              <Th>Nom públic</Th>
              <Th>Rol</Th>
              <Th>Localitat</Th>
              <Th>Publicacions</Th>
              <Th>Estat</Th>
              <Th></Th>
            </tr>
          </THead>
          <tbody>
            {data?.results?.length === 0 && (
              <tr><td colSpan={7}><EmptyState>Cap usuari.</EmptyState></td></tr>
            )}
            {data?.results?.map(u => (
              <Tr key={u.usuari_id}>
                <Td className="text-xs">
                  <div className="font-semibold">{u.username}</div>
                  <div className="opacity-60">{u.email}</div>
                </Td>
                <Td>{u.nom_public || <span className="opacity-40">—</span>}</Td>
                <Td><Pill>{u.rol_musical}</Pill></Td>
                <Td className="text-xs">{u.localitat || <span className="opacity-40">—</span>}</Td>
                <Td>{u.n_publicacions}</Td>
                <Td>
                  {u.visible_directori ? <Pill tone="green">Visible</Pill> : <Pill tone="gray">Ocult</Pill>}
                  {u.is_staff && <Pill tone="yellow">Staff</Pill>}
                  {u.obert_colaboracions && <Pill tone="yellow">Obert</Pill>}
                  {!u.is_active && <Pill tone="red">Inactiu</Pill>}
                </Td>
                <Td className="text-right">
                  <Btn
                    tone={u.visible_directori ? 'danger' : 'primary'}
                    onClick={() => toggle(u.usuari_id)}
                    disabled={busy === u.usuari_id}
                  >
                    {u.visible_directori ? 'Ocultar' : 'Mostrar'}
                  </Btn>
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
