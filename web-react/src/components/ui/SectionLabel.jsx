/**
 * SectionLabel — eyebrow text above section headings.
 * All caps, wide letter spacing.
 *
 * color: ink | yellow | muted
 */
const COLOR_MAP = {
  ink:    'text-tq-ink',
  yellow: 'text-tq-yellow',
  muted:  'text-tq-ink-muted',
}

export default function SectionLabel({ children, color = 'muted', className = '' }) {
  return (
    <p className={['text-xs font-semibold uppercase tracking-widest', COLOR_MAP[color], className].join(' ')}>
      {children}
    </p>
  )
}
