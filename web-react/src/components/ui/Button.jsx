/**
 * Button — shared button primitive.
 *
 * variant: primary | secondary | ghost | dark
 *   primary   — yellow fill, ink text (on dark bg pages)
 *   dark      — ink fill, white text
 *   secondary — white bg, ink border+text, hover ink fill
 *   ghost     — transparent, ink text, hover underline
 *
 * size: sm | md | lg. Radius 0.375rem, transition-colors.
 */
export default function Button({
  variant = 'primary',
  size = 'md',
  children,
  onClick,
  disabled,
  type = 'button',
  className = '',
  ...rest
}) {
  const sizes = {
    sm: 'text-xs px-3 py-1.5',
    md: 'text-sm px-5 py-2.5',
    lg: 'text-sm px-6 py-3',
  }

  const variants = {
    primary:
      'bg-tq-yellow text-tq-ink hover:bg-tq-yellow-deep hover:text-white disabled:opacity-50',
    dark:
      'bg-tq-ink text-white hover:bg-black disabled:opacity-50',
    secondary:
      'bg-white border border-tq-ink text-tq-ink hover:bg-tq-ink hover:text-white disabled:opacity-50',
    ghost:
      'text-tq-ink hover:underline disabled:opacity-50',
  }

  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled}
      {...rest}
      className={[
        'font-semibold inline-flex items-center justify-center transition-colors rounded-sm',
        sizes[size],
        variants[variant],
        className,
      ].join(' ')}
    >
      {children}
    </button>
  )
}
