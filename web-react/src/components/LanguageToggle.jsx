/**
 * LanguageToggle — tiny ca/es/en switcher in the header.
 */
import { useTranslation } from 'react-i18next'

const LANGS = ['ca', 'es', 'en']

export default function LanguageToggle() {
  const { i18n } = useTranslation()
  const current = (i18n.language || 'ca').slice(0, 2)

  return (
    <div className="flex items-center gap-1 text-xs font-semibold">
      {LANGS.map(l => (
        <button
          key={l}
          type="button"
          onClick={() => i18n.changeLanguage(l)}
          className={
            'px-2 py-1 rounded transition-colors ' +
            (l === current
              ? 'bg-tq-ink text-tq-yellow'
              : 'text-tq-ink/60 hover:text-tq-ink')
          }
        >
          {l.toUpperCase()}
        </button>
      ))}
    </div>
  )
}
