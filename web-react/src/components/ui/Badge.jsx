/**
 * Badge — small label pill.
 *
 * variant: default | ink | yellow | success | danger
 */
export default function Badge({ children, variant = 'default', className = '' }) {
  const variants = {
    default: 'bg-gray-100 text-gray-700',
    ink:     'bg-tq-ink text-tq-yellow',
    yellow:  'bg-tq-yellow text-tq-ink',
    success: 'bg-emerald-100 text-emerald-800',
    danger:  'bg-red-100 text-red-800',
  }

  return (
    <span
      className={[
        'inline-flex items-center text-xs font-semibold px-2.5 py-1 rounded',
        variants[variant],
        className,
      ].join(' ')}
    >
      {children}
    </span>
  )
}
