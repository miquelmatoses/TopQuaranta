/**
 * ArtistaEditPage — /staff/artistes/:pk
 *
 * Complex form: basic fields + social links + multiple locations +
 * multiple Deezer IDs. Saves via PATCH. Locations and Deezer IDs are
 * replace-semantics: we send the full list each time.
 */
import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { api } from '../../lib/api'
import { Btn, Input, PageHeader, Select, TableCard } from '../../components/staff/StaffTable'
import LocationCascade from '../../components/staff/LocationCascade'

export default function ArtistaEditPage() {
  const { pk } = useParams()
  const navigate = useNavigate()
  const [a, setA] = useState(null)
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState('')

  useEffect(() => {
    api.get(`/staff/artistes/${pk}/`).then(setA).catch(e => setErr(e.message))
  }, [pk])

  if (err) return <p className="text-sm text-red-300">{err}</p>
  if (!a) return <p className="text-sm text-white/70">Carregant…</p>

  function patch(partial) {
    setA(prev => ({ ...prev, ...partial }))
  }

  function patchSocial(field, value) {
    setA(prev => ({ ...prev, social: { ...prev.social, [field]: value } }))
  }

  function addLoc() {
    setA(prev => ({
      ...prev,
      localitats: [
        ...(prev.localitats || []),
        { municipi_id: null, municipi_nom: '', comarca: '', territori: '', manual: '' },
      ],
    }))
  }

  function updateLoc(i, patch) {
    setA(prev => ({
      ...prev,
      localitats: prev.localitats.map((l, idx) => (idx === i ? { ...l, ...patch } : l)),
    }))
  }

  function removeLoc(i) {
    setA(prev => ({
      ...prev,
      localitats: prev.localitats.filter((_, idx) => idx !== i),
    }))
  }

  function setDeezerIds(ids) {
    setA(prev => ({ ...prev, deezer_ids: ids }))
  }

  async function save() {
    setBusy(true)
    setErr('')
    setMsg('')
    try {
      const body = {
        nom: a.nom,
        lastfm_nom: a.lastfm_nom,
        genere: a.genere,
        percentatge_femeni: a.percentatge_femeni,
        aprovat: a.aprovat,
        localitats: a.localitats.map(l => ({
          municipi_id: l.municipi_id || null,
          manual: l.manual || '',
        })),
        deezer_ids: a.deezer_ids,
        ...a.social,
      }
      const out = await api.patch(`/staff/artistes/${pk}/`, body)
      setA(out)
      setMsg('Desat.')
    } catch (e) {
      setErr(e.payload?.error || e.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <section>
      <PageHeader
        title={`Editar: ${a.nom}`}
        subtitle={
          <>
            <Link to={`/artista/${a.slug}`} className="underline">perfil públic</Link>
            {' · '}pk={a.pk}
          </>
        }
        right={
          <>
            <Btn tone="outline" size="md" onClick={() => navigate('/staff/artistes')}>Tornar</Btn>
            <Btn size="md" onClick={save} disabled={busy}>Desar</Btn>
          </>
        }
      />

      {err && <p className="text-sm text-red-300 mb-3">{err}</p>}
      {msg && <p className="text-sm text-emerald-300 mb-3">{msg}</p>}

      <div className="grid lg:grid-cols-2 gap-4">
        <TableCard className="p-4">
          <h2 className="font-semibold mb-3">Bàsics</h2>
          <div className="flex flex-col gap-2">
            <label className="text-xs font-semibold">Nom
              <Input value={a.nom} onChange={e => patch({ nom: e.target.value })} className="w-full mt-1 font-normal" />
            </label>
            <label className="text-xs font-semibold">Nom a Last.fm
              <Input value={a.lastfm_nom || ''} onChange={e => patch({ lastfm_nom: e.target.value })} className="w-full mt-1 font-normal" />
            </label>
            <label className="text-xs font-semibold">Gènere
              <Input value={a.genere || ''} onChange={e => patch({ genere: e.target.value })} className="w-full mt-1 font-normal" />
            </label>
            <label className="text-xs font-semibold">% femení
              <Select value={a.percentatge_femeni || ''} onChange={e => patch({ percentatge_femeni: e.target.value })} className="w-full mt-1 font-normal">
                <option value="">—</option>
                {a.percentatge_choices.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
              </Select>
            </label>
            <label className="text-xs font-semibold flex items-center gap-2 mt-1">
              <input type="checkbox" checked={a.aprovat} onChange={e => patch({ aprovat: e.target.checked })} />
              Aprovat
            </label>
          </div>
        </TableCard>

        <TableCard className="p-4">
          <h2 className="font-semibold mb-3">Xarxes</h2>
          <div className="grid grid-cols-2 gap-2">
            {a.social_fields.map(([field, label]) => (
              <label key={field} className="text-xs font-semibold">
                {label}
                <Input
                  value={a.social?.[field] || ''}
                  onChange={e => patchSocial(field, e.target.value)}
                  className="w-full mt-1 font-normal"
                />
              </label>
            ))}
          </div>
        </TableCard>

        <TableCard className="p-4">
          <div className="flex justify-between items-center mb-3">
            <h2 className="font-semibold">Deezer IDs</h2>
            <Btn size="sm" onClick={() => setDeezerIds([...a.deezer_ids, ''])}>+ Afegir</Btn>
          </div>
          <div className="flex flex-col gap-2">
            {a.deezer_ids.map((id, i) => (
              <div key={i} className="flex gap-2">
                <Input
                  value={id}
                  onChange={e => setDeezerIds(a.deezer_ids.map((x, j) => j === i ? e.target.value : x))}
                  className="flex-1"
                  inputMode="numeric"
                />
                <Btn tone="danger" onClick={() => setDeezerIds(a.deezer_ids.filter((_, j) => j !== i))}>×</Btn>
              </div>
            ))}
            {a.deezer_ids.length === 0 && <p className="text-xs opacity-60">Cap Deezer ID.</p>}
          </div>
        </TableCard>

        <TableCard className="p-4">
          <div className="flex justify-between items-center mb-3">
            <h2 className="font-semibold">Localitats</h2>
            <Btn size="sm" onClick={addLoc}>+ Afegir</Btn>
          </div>
          <div className="flex flex-col gap-3">
            {a.localitats.map((l, i) => (
              <div key={i} className="flex gap-2 items-start">
                <div className="flex-1">
                  <LocationCascade
                    value={{
                      territori: l.territori || '',
                      comarca: l.comarca || '',
                      municipi_id: l.municipi_id || null,
                      municipi_nom: l.municipi_nom || '',
                      manual: l.manual || '',
                    }}
                    onChange={next => updateLoc(i, next)}
                  />
                </div>
                <Btn tone="danger" onClick={() => removeLoc(i)}>×</Btn>
              </div>
            ))}
            {a.localitats.length === 0 && <p className="text-xs opacity-60">Cap localitat.</p>}
            <p className="text-[11px] opacity-60 mt-1">
              Tria territori → comarca → municipi. Per a llocs fora dels
              Països Catalans escull "Altres" i escriu el nom de la
              localitat a mà.
            </p>
          </div>
        </TableCard>
      </div>
    </section>
  )
}
