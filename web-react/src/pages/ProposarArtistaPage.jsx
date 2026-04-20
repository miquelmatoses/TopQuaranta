/**
 * ProposarArtistaPage — /compte/artista/proposta
 *
 * Authenticated form. Lets a user submit a PropostaArtista with:
 *   - nom (required)
 *   - justificacio (required)
 *   - social URLs (optional, all validated server-side)
 *   - deezer_ids (free-form list; the form exposes one text input per id
 *     with add/remove)
 *   - localitzacions (only "manual" free-text entries from here; the
 *     staff approval step resolves them to a Municipi if they match)
 *
 * Sends to POST /api/v1/compte/propostes/. On success, returns the
 * user to /compte where the new proposal appears in the card grid.
 */
import { useState } from 'react'
import { Navigate, useNavigate } from 'react-router-dom'
import { api } from '../lib/api'
import { useAuth } from '../context/AuthContext'

const SOCIAL_FIELDS = [
  ['spotify_url',    'Spotify'],
  ['viasona_url',    'Viasona'],
  ['web_url',        'Web oficial'],
  ['bandcamp_url',   'Bandcamp'],
  ['youtube_url',    'YouTube'],
  ['viquipedia_url', 'Viquipèdia'],
  ['soundcloud_url', 'SoundCloud'],
  ['tiktok_url',     'TikTok'],
  ['facebook_url',   'Facebook'],
]

function Field({ label, error, children, hint }) {
  return (
    <label className="flex flex-col text-sm">
      <span className="text-xs font-semibold text-white/90">{label}</span>
      {children}
      {hint && <span className="text-[11px] text-white/60 mt-0.5">{hint}</span>}
      {error && <span className="text-[11px] text-red-300 mt-0.5">{error}</span>}
    </label>
  )
}

const inputClass =
  'mt-1 px-3 py-2 rounded-md bg-white text-tq-ink text-sm placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-tq-yellow'

export default function ProposarArtistaPage() {
  const { profile, loading } = useAuth()
  const navigate = useNavigate()

  const [nom, setNom] = useState('')
  const [justificacio, setJustificacio] = useState('')
  const [social, setSocial] = useState(Object.fromEntries(SOCIAL_FIELDS.map(([k]) => [k, ''])))
  const [deezerIds, setDeezerIds] = useState([''])
  const [localitats, setLocalitats] = useState([''])
  const [errors, setErrors] = useState({})
  const [busy, setBusy] = useState(false)

  if (loading) return null
  if (!profile) return <Navigate to="/compte/accedir" replace />

  async function submit(e) {
    e.preventDefault()
    setBusy(true)
    setErrors({})
    try {
      const payload = {
        nom,
        justificacio,
        ...social,
        deezer_ids: deezerIds.map(s => s.trim()).filter(Boolean),
        localitzacions: localitats
          .map(s => s.trim())
          .filter(Boolean)
          .map(s => ({ manual: s })),
      }
      await api.post('/compte/propostes/', payload)
      navigate('/compte')
    } catch (err) {
      if (err.payload?.errors) setErrors(err.payload.errors)
      else setErrors({ __all__: err.message })
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="max-w-2xl mx-auto text-white">
      <h1 className="text-3xl font-bold mb-2">Proposar un artista nou</h1>
      <p className="text-sm text-white/70 mb-6">
        Omple el que sàpigues. L'equip TopQuaranta revisa cada proposta
        abans d'incorporar l'artista al sistema.
      </p>

      {errors.__all__ && (
        <div className="mb-4 p-3 bg-red-100 text-red-800 rounded-md text-sm">
          {errors.__all__}
        </div>
      )}

      <form onSubmit={submit} className="flex flex-col gap-4">
        <Field label="Nom de l'artista *" error={errors.nom}>
          <input
            required
            value={nom}
            onChange={e => setNom(e.target.value)}
            className={inputClass}
            placeholder="p. ex. Sangtraït"
          />
        </Field>

        <Field
          label="Justificació *"
          error={errors.justificacio}
          hint="Per què cal afegir aquest artista? Quins àlbums, activitat recent, etc."
        >
          <textarea
            required
            value={justificacio}
            onChange={e => setJustificacio(e.target.value)}
            rows={5}
            className={inputClass + ' resize-y'}
          />
        </Field>

        <fieldset className="bg-white/5 rounded-md p-4">
          <legend className="text-xs font-semibold uppercase tracking-wide text-white/80 px-1">
            Deezer
          </legend>
          <p className="text-[11px] text-white/60 mb-2">
            Un o més Deezer artist IDs (numèrics). Es troben a la URL del perfil
            de Deezer després de <code>/artist/</code>.
          </p>
          {deezerIds.map((v, i) => (
            <div key={i} className="flex gap-2 mb-2">
              <input
                value={v}
                inputMode="numeric"
                onChange={e =>
                  setDeezerIds(deezerIds.map((x, j) => (j === i ? e.target.value : x)))
                }
                className={inputClass + ' flex-1'}
                placeholder="p. ex. 12345"
              />
              <button
                type="button"
                onClick={() => setDeezerIds(deezerIds.filter((_, j) => j !== i))}
                className="px-2 text-sm text-red-300 hover:text-red-200"
                aria-label="Eliminar"
              >
                ✕
              </button>
            </div>
          ))}
          <button
            type="button"
            onClick={() => setDeezerIds([...deezerIds, ''])}
            className="text-xs font-semibold text-tq-yellow hover:underline"
          >
            + Afegir ID
          </button>
          {errors.deezer_ids && (
            <p className="text-[11px] text-red-300 mt-1">{errors.deezer_ids}</p>
          )}
        </fieldset>

        <fieldset className="bg-white/5 rounded-md p-4">
          <legend className="text-xs font-semibold uppercase tracking-wide text-white/80 px-1">
            Localitats
          </legend>
          <p className="text-[11px] text-white/60 mb-2">
            Ciutat / comarca d'origen. Pots posar-ne més d'una.
          </p>
          {localitats.map((v, i) => (
            <div key={i} className="flex gap-2 mb-2">
              <input
                value={v}
                onChange={e =>
                  setLocalitats(localitats.map((x, j) => (j === i ? e.target.value : x)))
                }
                className={inputClass + ' flex-1'}
                placeholder="p. ex. Lleida, Segrià"
              />
              <button
                type="button"
                onClick={() => setLocalitats(localitats.filter((_, j) => j !== i))}
                className="px-2 text-sm text-red-300 hover:text-red-200"
                aria-label="Eliminar"
              >
                ✕
              </button>
            </div>
          ))}
          <button
            type="button"
            onClick={() => setLocalitats([...localitats, ''])}
            className="text-xs font-semibold text-tq-yellow hover:underline"
          >
            + Afegir localitat
          </button>
        </fieldset>

        <fieldset className="bg-white/5 rounded-md p-4">
          <legend className="text-xs font-semibold uppercase tracking-wide text-white/80 px-1">
            Enllaços
          </legend>
          <div className="grid sm:grid-cols-2 gap-3">
            {SOCIAL_FIELDS.map(([field, label]) => (
              <Field key={field} label={label} error={errors[field]}>
                <input
                  type="url"
                  value={social[field]}
                  onChange={e => setSocial({ ...social, [field]: e.target.value })}
                  className={inputClass}
                  placeholder="https://…"
                />
              </Field>
            ))}
          </div>
        </fieldset>

        <div className="flex gap-2 pt-2">
          <button
            type="submit"
            disabled={busy}
            className="px-4 py-2 bg-tq-yellow text-tq-ink rounded-md font-semibold text-sm disabled:opacity-50"
          >
            {busy ? 'Enviant…' : 'Enviar proposta'}
          </button>
          <button
            type="button"
            onClick={() => navigate('/compte')}
            className="px-4 py-2 border border-white/20 text-white rounded-md text-sm hover:bg-white/10"
          >
            Cancel·lar
          </button>
        </div>
      </form>
    </section>
  )
}
