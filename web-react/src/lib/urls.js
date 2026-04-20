/**
 * SEO-friendly URL builders. Both canco and album can be reached via
 * a flat canonical route (`/canco/<slug>`, `/album/<slug>`) or a
 * nested, keyword-rich one (`/artista/<a>/<album>/<canco>`,
 * `/artista/<a>/<album>`). Prefer the nested form whenever we have
 * the context.
 */

export function cancoUrl({ cancoSlug, artistaSlug, albumSlug }) {
  if (!cancoSlug) return '#'
  if (artistaSlug && albumSlug) {
    return `/artista/${artistaSlug}/${albumSlug}/${cancoSlug}`
  }
  return `/canco/${cancoSlug}`
}

export function albumUrl({ albumSlug, artistaSlug }) {
  if (!albumSlug) return '#'
  if (artistaSlug) {
    return `/artista/${artistaSlug}/${albumSlug}`
  }
  return `/album/${albumSlug}`
}

export function artistaUrl(slug) {
  return slug ? `/artista/${slug}` : '#'
}
