/**
 * PerfilUsuariPage — /compte/perfil-usuari
 *
 * User-controlled surface for PerfilUsuari. Mirrors the OnboardingPage
 * form shape but stays on /compte/ when saved (no navigation away).
 */
import { useEffect, useState } from 'react'
import { Navigate, useNavigate } from 'react-router-dom'
import { api } from '../lib/api'
import { useAuth } from '../context/AuthContext'
import LocationCascade from '../components/staff/LocationCascade'

const inputClass =
  'mt-1 px-3 py-2 rounded-md bg-white text-tq-ink text-sm placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-tq-yellow'

function Field({ label, hint, error, children }) {
  return (
    <label className="flex flex-col text-sm">
      <span className="text-xs font-semibold text-white/90">{label}</span>
      {children}
      {hint && <span className="text-[11px] text-white/60 mt-0.5">{hint}</span>}
      {error && <span className="text-[11px] text-red-300 mt-0.5">{error}</span>}
    </label>
  )
}

export default function PerfilUsuariPage() {
  const { profile, loading } = useAuth()
  const navigate = useNavigate()
  const [perfil, setPerfil] = useState(null)
  const [loc, setLoc] = useState({ territori: '', comarca: '', municipi_id: null, manual: '' })
  const [errors, setErrors] = useState({})
  const [msg, setMsg] = useState('')
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    if (loading || !profile) return
    api.get('/compte/perfil-usuari/').then(p => {
      setPerfil(p)
      if (p.localitat) {
        setLoc({
          territori: p.localitat.territori,
          comarca: p.localitat.comarca,
          municipi_id: p.localitat.pk,
          municipi_nom: p.localitat.nom,
          manual: '',
        })
      }
    }).catch(() => {})
  }, [loading, profile])

  if (loading) return null
  if (!profile) return <Navigate to="/compte/accedir?next=/compte/perfil-usuari" replace />
  if (!perfil) return (
    <section className="max-w-2xl mx-auto py-12 text-white/70 text-sm">Carregant…</section>
  )

  function patch(p) { setPerfil(prev => ({ ...prev, ...p })) }
  function patchSocial(k, v) {
    setPerfil(prev => ({ ...prev, social: { ...prev.social, [k]: v } }))
  }

  async function save() {
    setBusy(true)
    setErrors({})
    setMsg('')
    try {
      const out = await api.patch('/compte/perfil-usuari/', {
        nom_public: perfil.nom_public || '',
        bio: perfil.bio || '',
        rol_musical: perfil.rol_musical || 'escoltador',
        instruments: perfil.instruments || '',
        visible_directori: !!perfil.visible_directori,
        obert_colaboracions: !!perfil.obert_colaboracions,
        imatge_url: perfil.imatge_url || '',
        localitat_pk: loc.municipi_id || null,
        ...(perfil.social || {}),
      })
      setPerfil(out)
      setMsg('Canvis desats.')
    } catch (err) {
      if (err.payload?.errors) setErrors(err.payload.errors)
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="max-w-2xl mx-auto text-white">
      <p className="text-[10px] uppercase tracking-widest text-white/60 mb-1">Perfil comunitari</p>
      <h1 className="text-3xl font-bold mb-4">El teu perfil</h1>
      {msg && <div className="mb-4 p-3 bg-emerald-900/40 text-emerald-200 rounded-md text-sm">{msg}</div>}

      <div className="flex flex-col gap-4">
        <Field label="Nom públic" error={errors.nom_public}>
          <input value={perfil.nom_public || ''} onChange={e => patch({ nom_public: e.target.value })} className={inputClass} />
        </Field>

        <Field label="Rol musical" error={errors.rol_musical}>
          <select value={perfil.rol_musical} onChange={e => patch({ rol_musical: e.target.value })} className={inputClass}>
            {(perfil.rol_choices || []).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
          </select>
        </Field>

        <Field label="Instruments / àmbit" error={errors.instruments}>
          <input value={perfil.instruments || ''} onChange={e => patch({ instruments: e.target.value })} className={inputClass} />
        </Field>

        <Field label="Localitat">
          <div className="mt-1"><LocationCascade value={loc} onChange={setLoc} /></div>
        </Field>

        <Field label="Bio (màxim 2 000 caràcters)" error={errors.bio}>
          <textarea rows={4} value={perfil.bio || ''} onChange={e => patch({ bio: e.target.value })} className={inputClass + ' resize-y'} />
        </Field>

        <Field label="URL imatge de perfil" error={errors.imatge_url}>
          <input type="url" value={perfil.imatge_url || ''} onChange={e => patch({ imatge_url: e.target.value })} className={inputClass} />
        </Field>

        <fieldset className="bg-white/5 rounded-md p-4">
          <legend className="text-xs font-semibold uppercase tracking-wide text-white/80 px-1">Visibilitat</legend>
          <label className="flex items-center gap-2 text-sm mb-2">
            <input type="checkbox" checked={!!perfil.visible_directori} onChange={e => patch({ visible_directori: e.target.checked })} />
            Aparèixer al <strong>directori intern</strong>.
          </label>
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={!!perfil.obert_colaboracions} onChange={e => patch({ obert_colaboracions: e.target.checked })} />
            Obert a <strong>col·laboracions</strong>.
          </label>
        </fieldset>

        <fieldset className="bg-white/5 rounded-md p-4">
          <legend className="text-xs font-semibold uppercase tracking-wide text-white/80 px-1">Enllaços</legend>
          <div className="grid sm:grid-cols-2 gap-3">
            {(perfil.social_fields || []).map(([f, label]) => (
              <Field key={f} label={label} error={errors[f]}>
                <input type="url" value={perfil.social?.[f] || ''} onChange={e => patchSocial(f, e.target.value)} className={inputClass} placeholder="https://…" />
              </Field>
            ))}
          </div>
        </fieldset>

        <div className="flex gap-2 pt-2">
          <button type="button" onClick={save} disabled={busy} className="px-4 py-2 bg-tq-yellow text-tq-ink rounded-md font-semibold text-sm disabled:opacity-50">
            {busy ? 'Desant…' : 'Desar canvis'}
          </button>
          <button type="button" onClick={() => navigate('/compte')} className="px-4 py-2 border border-white/20 text-white rounded-md text-sm hover:bg-white/10">
            Tornar
          </button>
        </div>
      </div>
    </section>
  )
}
