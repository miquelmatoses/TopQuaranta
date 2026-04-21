/**
 * PropostaDetailPage — /staff/propostes/:pk
 *
 * Detail + approve/reject. Approving creates the Artista and links it.
 */
import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { api } from '../../lib/api'
import { Btn, PageHeader, Pill, TableCard } from '../../components/staff/StaffTable'

export default function PropostaDetailPage() {
  const { pk } = useParams()
  const navigate = useNavigate()
  const [p, setP] = useState(null)
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    api.get(`/staff/propostes/${pk}/`).then(setP).catch(e => setErr(e.message))
  }, [pk])

  if (err) return <p className="text-red-300">{err}</p>
  if (!p) return <p className="text-white/70">Carregant…</p>

  async function aprovar() {
    if (!confirm(`Crear l'artista «${p.nom}»?`)) return
    setBusy(true); setErr('')
    try {
      const out = await api.post(`/staff/propostes/${pk}/aprovar/`)
      navigate(`/staff/artistes/${out.artista_pk}`)
    } catch (e) {
      // 409 conflicts come with a `conflicts` array detailing which
      // Deezer IDs clash and who owns them — print a useful message.
      if (e.status === 409 && e.payload?.conflicts) {
        const lines = e.payload.conflicts
          .map(c => `· ${c.deezer_id} → «${c.owner_nom}» (pk=${c.owner_pk})`)
          .join('\n')
        setErr(`${e.payload.error}\n\n${lines}`)
      } else {
        setErr(e.payload?.error || e.message)
      }
    } finally { setBusy(false) }
  }

  async function rebutjar() {
    if (!confirm('Rebutjar aquesta proposta?')) return
    setBusy(true); setErr('')
    try {
      await api.post(`/staff/propostes/${pk}/rebutjar/`)
      navigate('/staff/propostes')
    } catch (e) {
      setErr(e.payload?.error || e.message)
    } finally { setBusy(false) }
  }

  return (
    <section>
      <PageHeader
        title={p.nom}
        subtitle={<>Proposta de {p.usuari.email} · {p.created_at?.slice(0, 10)}</>}
        right={
          <>
            <Btn tone="secondary" size="md" onClick={() => navigate('/staff/propostes')}>Tornar</Btn>
            {p.estat === 'pendent' && (
              <>
                <Btn size="md" onClick={aprovar} disabled={busy}>Aprovar</Btn>
                <Btn tone="danger" size="md" onClick={rebutjar} disabled={busy}>Rebutjar</Btn>
              </>
            )}
          </>
        }
      />
      {err && (
        <pre className="text-red-300 mb-3 whitespace-pre-wrap font-sans text-sm">{err}</pre>
      )}

      <div className="mb-3">
        <Pill tone={p.estat === 'aprovat' ? 'green' : p.estat === 'rebutjat' ? 'gray' : 'yellow'}>{p.estat}</Pill>
        {p.artista_creat && (
          <Link to={`/staff/artistes/${p.artista_creat.pk}`} className="ml-2 underline text-white/90 text-sm">
            Artista creat
          </Link>
        )}
      </div>

      <div className="grid lg:grid-cols-2 gap-4">
        <TableCard className="p-4">
          <h2 className="font-semibold mb-2">Justificació</h2>
          <p className="text-sm whitespace-pre-wrap">{p.justificacio || <em className="opacity-60">—</em>}</p>
        </TableCard>

        <TableCard className="p-4">
          <h2 className="font-semibold mb-2">Localitzacions</h2>
          {p.localitzacions?.length ? (
            <ul className="text-sm space-y-1">
              {p.localitzacions.map((l, i) => <li key={i}>· {l}</li>)}
            </ul>
          ) : (
            <p className="text-sm opacity-60">—</p>
          )}
        </TableCard>

        <TableCard className="p-4">
          <h2 className="font-semibold mb-2">Deezer</h2>
          {p.deezer_ids?.length ? (
            <ul className="text-sm space-y-1">
              {p.deezer_ids.map(id => <li key={id}>· {id}</li>)}
            </ul>
          ) : (
            <p className="text-sm opacity-60">—</p>
          )}
        </TableCard>

        <TableCard className="p-4">
          <h2 className="font-semibold mb-2">Xarxes</h2>
          {Object.keys(p.social || {}).length ? (
            <ul className="text-sm space-y-1">
              {Object.entries(p.social).map(([k, v]) => (
                <li key={k}>
                  <span className="font-semibold">{k}:</span>{' '}
                  <a href={v} target="_blank" rel="noopener" className="underline break-all">{v}</a>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm opacity-60">—</p>
          )}
        </TableCard>
      </div>
    </section>
  )
}
