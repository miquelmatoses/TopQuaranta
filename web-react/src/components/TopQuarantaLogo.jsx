/**
 * TopQuarantaLogo — horizontal rectangular wordmark.
 *
 * Two variants:
 *   - variant="mono" (default): rendered via CSS `mask-image` so the
 *     logo follows the parent element's `color`. Use this when the
 *     logo sits on a branded surface (yellow header, black footer).
 *   - variant="color": rendered as a plain <img> with the full-brand
 *     SVG (blue + red + yellow from the mm-design palette). Use this
 *     on neutral backgrounds (white cards, documentation pages) when
 *     we want the branded multicolour version.
 *
 * The asset files live at /static/web/img/logo-topquaranta-rect*.svg.
 * They're served by Caddy's existing `handle_path /static/*` rule.
 */

// Viewbox aspect ratio of the source SVG: 1876.9116 × 380.45602 → ≈4.93.
const ASPECT_RATIO = 1876.9116 / 380.45602

export default function TopQuarantaLogo({
  className = 'h-7',
  variant = 'mono',
  alt = 'TopQuaranta',
}) {
  const monoUrl = '/static/web/img/logo-topquaranta-rect-mono.svg'
  const colorUrl = '/static/web/img/logo-topquaranta-rect.svg'

  if (variant === 'color') {
    return (
      <img
        src={colorUrl}
        alt={alt}
        className={className}
        style={{ aspectRatio: ASPECT_RATIO }}
      />
    )
  }

  // mask-image trick: the element's backgroundColor is `currentColor`,
  // and the SVG's black shape becomes the alpha mask. Colour follows
  // the parent's CSS `color`. Both the WebKit and standard prefixes
  // are required for Safari.
  return (
    <span
      role="img"
      aria-label={alt}
      className={className}
      style={{
        display: 'inline-block',
        aspectRatio: ASPECT_RATIO,
        backgroundColor: 'currentColor',
        WebkitMaskImage: `url(${monoUrl})`,
        maskImage: `url(${monoUrl})`,
        WebkitMaskRepeat: 'no-repeat',
        maskRepeat: 'no-repeat',
        WebkitMaskPosition: 'center',
        maskPosition: 'center',
        WebkitMaskSize: 'contain',
        maskSize: 'contain',
      }}
    />
  )
}
