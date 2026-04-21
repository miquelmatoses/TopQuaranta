/**
 * ComunitatDetailPage — /comunitat/:pk
 *
 * Single publication view. Author / staff see edit + delete buttons;
 * others see read-only. Reuses the server-side authorisation checks
 * (API returns 404 to unauthorised callers on unpublished rows).
 */
import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { api } from '../lib/api'
import { useAuth } from '../context/AuthContext'

function EstatBadge({ estat }) {
  const tone = {
    esborrany: 'bg-gray-300 text-gray-800',
    pendent:   'bg-yellow-200 text-yellow-900',
    publicat:  'bg-emerald-200 text-emerald-900',
    rebutjat:  'bg-red-200 text-red-900',
  }[estat] || 'bg-gray-300 text-gray-800'
  return (
    <span className={'text-[10px] uppercase tracking-wide font-semibold px-2 py-0.5 rounded-full ' + tone}>
      {estat}
    </span>
  )
}

export default function ComunitatDetailPage() {
  const { pk } = useParams()
  const { profile } = useAuth()
  const navigate = useNavigate()
  const [pub, setPub] = useState(null)
  const [err, setErr] = useState(null)

  useEffect(() => {
    api.get(`/comunitat/publicacions/${pk}/`).then(setPub).catch(e => setErr(e.message))
  }, [pk])

  if (err) {
    return (
      <section className="max-w-3xl mx-auto text-white">
        <p className="text-sm text-red-300">{err}</p>
      </section>
    )
  }
  if (!pub) return (
    <section className="max-w-3xl mx-auto py-6 text-white/70 text-sm">Carregant…</section>
  )

  const canEdit = profile?.is_staff || (profile?.username === pub.autor.username)

  async function remove() {
    if (!confirm('Esborrar aquesta publicació?')) return
    await api.delete(`/comunitat/publicacions/${pk}/`)
    navigate('/comunitat')
  }

  return (
    <article className="max-w-3xl mx-auto text-white">
      <div className="flex items-start justify-between gap-2 mb-3">
        <div>
          <p className="text-[10px] uppercase tracking-widest text-white/60">
            per {pub.autor.nom_public}
            {pub.autor.is_staff && ' · staff'}
          </p>
          <h1 className="text-3xl font-bold font-display mt-1">{pub.titol}</h1>
        </div>
        <div className="flex gap-1">
          {pub.visibilitat === 'publica' && (
            <span className="text-[10px] uppercase font-semibold px-2 py-0.5 rounded-full bg-blue-100 text-blue-800">
              Pública
            </span>
          )}
          <EstatBadge estat={pub.estat} />
        </div>
      </div>
      {pub.publicat_at && (
        <p className="text-xs text-white/50 mb-4">Publicat {pub.publicat_at.slice(0, 10)}</p>
      )}

      <div className="bg-white text-tq-ink rounded-lg p-6 whitespace-pre-wrap leading-relaxed">
        {pub.cos}
      </div>

      {pub.notes_staff && (
        <div className="mt-4 bg-red-100 text-red-900 rounded-md p-3 text-sm">
          <strong>Nota del staff:</strong> {pub.notes_staff}
        </div>
      )}

      {canEdit && (
        <div className="flex gap-2 mt-5">
          <Link
            to={`/comunitat/${pub.pk}/editar`}
            className="px-3 py-1.5 bg-tq-yellow text-tq-ink rounded-md text-sm font-semibold"
          >
            Editar
          </Link>
          <button
            type="button"
            onClick={remove}
            className="px-3 py-1.5 border border-red-400 text-red-300 rounded-md text-sm hover:bg-red-400 hover:text-white"
          >
            Esborrar
          </button>
        </div>
      )}
    </article>
  )
}
