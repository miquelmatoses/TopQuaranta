/**
 * Card — white surface that floats on the black body.
 *
 * accent: none | yellow | red | green | blue
 *   Default: subtle shadow, no border.
 *   Accent:  4px left border in the accent colour.
 */
const ACCENT_BORDER = {
  yellow: 'border-l-4 border-l-tq-yellow',
  red:    'border-l-4 border-l-red-600',
  green:  'border-l-4 border-l-emerald-600',
  blue:   'border-l-4 border-l-blue-600',
}

export default function Card({ children, accent, className = '' }) {
  return (
    <div
      className={[
        'bg-white text-tq-ink rounded-lg shadow-md',
        accent ? ACCENT_BORDER[accent] : '',
        className,
      ].join(' ')}
    >
      {children}
    </div>
  )
}
