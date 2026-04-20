/**
 * HomePage — all-yellow welcome. Sets `data-theme="yellow"` on <body>
 * while mounted so the yellow header continues into the page (mirrors
 * cercol's all-blue home pattern).
 */
import { useEffect } from 'react'
import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'

export default function HomePage() {
  const { t } = useTranslation()

  useEffect(() => {
    document.body.setAttribute('data-theme', 'yellow')
    return () => document.body.removeAttribute('data-theme')
  }, [])

  return (
    <section className="max-w-3xl mx-auto py-16 text-tq-ink">
      <p className="text-xs font-bold uppercase tracking-widest mb-4">
        {t('home.eyebrow', 'El rànquing setmanal de música en català')}
      </p>
      <h1 className="text-5xl md:text-6xl font-bold leading-tight mb-6">
        {t('home.headline', 'La música que sona als Països Catalans, cada setmana')}
      </h1>
      <p className="text-lg leading-relaxed mb-8 max-w-2xl">
        {t(
          'home.body',
          'TopQuaranta mesura què escolten de Catalunya a les Illes Balears, del País Valencià a la Catalunya Nord. 40 cançons. 4 territoris. Una llengua viva.',
        )}
      </p>
      <div className="flex flex-wrap gap-3">
        <Link
          to="/ranking"
          className="inline-flex items-center gap-2 px-6 py-3 bg-tq-ink text-white font-semibold rounded-md hover:bg-black"
        >
          {t('home.ctaRanking', 'Veure el rànquing')}
        </Link>
        <Link
          to="/compte/accedir"
          className="inline-flex items-center gap-2 px-6 py-3 border border-tq-ink text-tq-ink font-semibold rounded-md hover:bg-tq-ink hover:text-white"
        >
          {t('home.ctaJoin', "Uneix-t'hi al projecte")}
        </Link>
      </div>
    </section>
  )
}
