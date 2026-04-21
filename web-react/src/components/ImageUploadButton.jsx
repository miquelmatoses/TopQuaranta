import { useRef, useState } from 'react'
import { api } from '../lib/api'

/** File-picker button that uploads an image and hands back the served URL.
 *
 *  Props:
 *    - kind: "publicacio" | "perfil"
 *    - onUploaded(url): fired after the API returns the stored URL.
 *    - label: optional button text override.
 *    - className: optional extra classes on the trigger button.
 *
 *  Restricted to the server's ACCEPT list so the native dialog filters
 *  early; the backend validates the same set regardless.
 */
export default function ImageUploadButton({
  kind = 'publicacio',
  onUploaded,
  label,
  className = '',
  children,
}) {
  const ref = useRef(null)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')

  async function onPick(e) {
    const f = e.target.files?.[0]
    e.target.value = ''
    if (!f) return
    setBusy(true); setErr('')
    try {
      const fd = new FormData()
      fd.append('fitxer', f)
      fd.append('kind', kind)
      const out = await api.post('/upload/imatge/', fd)
      onUploaded?.(out.url)
    } catch (e) {
      setErr(e.payload?.error || e.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <>
      <button
        type="button"
        onClick={() => ref.current?.click()}
        disabled={busy}
        className={
          'inline-flex items-center gap-1.5 text-xs font-semibold px-2.5 py-1.5 rounded ' +
          'border border-white/30 text-white hover:bg-white/10 disabled:opacity-50 ' +
          className
        }
      >
        {children || (busy ? 'Pujant…' : label || '📎 Pujar imatge')}
      </button>
      <input
        ref={ref}
        type="file"
        accept="image/jpeg,image/png,image/webp"
        className="hidden"
        onChange={onPick}
      />
      {err && <span className="text-[11px] text-red-300 ml-2">{err}</span>}
    </>
  )
}
