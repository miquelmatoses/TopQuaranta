/** Strip the most common markdown syntax for a plain-text preview.
 *  Good enough for feed cards where we want a clean 2–3 line excerpt.
 *  Not a real parser — don't use for anything security-sensitive. */
export function stripMarkdown(src) {
  if (!src) return ''
  let s = src
  // images: ![alt](url) → alt (or blank)
  s = s.replace(/!\[([^\]]*)\]\([^)]*\)/g, '$1')
  // links: [text](url) → text
  s = s.replace(/\[([^\]]+)\]\([^)]*\)/g, '$1')
  // code fences → just the content
  s = s.replace(/```[^\n]*\n?([\s\S]*?)```/g, '$1')
  // inline code
  s = s.replace(/`([^`]+)`/g, '$1')
  // headings: leading #'s
  s = s.replace(/^\s{0,3}#{1,6}\s+/gm, '')
  // blockquote markers
  s = s.replace(/^\s{0,3}>\s?/gm, '')
  // list bullets / ordered
  s = s.replace(/^\s{0,3}[-*+]\s+/gm, '')
  s = s.replace(/^\s{0,3}\d+\.\s+/gm, '')
  // bold / italic / strike markers
  s = s.replace(/(\*\*|__)(.+?)\1/g, '$2')
  s = s.replace(/(\*|_)(.+?)\1/g, '$2')
  s = s.replace(/~~(.+?)~~/g, '$1')
  // horizontal rules
  s = s.replace(/^[ \t]*[-*_]{3,}[ \t]*$/gm, '')
  // collapse blank lines
  s = s.replace(/\n{3,}/g, '\n\n')
  return s.trim()
}
