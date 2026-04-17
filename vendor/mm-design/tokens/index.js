/**
 * mm-design — JavaScript token exports
 *
 * Single source of truth for all design tokens consumed by JS/React projects.
 * Values are kept in sync with the JSON files (colors.json, typography.json, spacing.json).
 * CSS consumers should use the .css files directly; JS consumers import from here.
 */

import colorsData from './colors.json' with { type: 'json' }
import typographyData from './typography.json' with { type: 'json' }
import spacingData from './spacing.json' with { type: 'json' }

// ── Brand & semantic colors (flat object matching cercol's `colors` export) ──

export const colors = {
  // Brand palette
  red:         colorsData.brand.red,
  blue:        colorsData.brand.blue,
  yellow:      colorsData.brand.yellow,
  green:       colorsData.brand.green,
  white:       colorsData.brand.white,
  black:       colorsData.brand.black,

  // Semantic aliases
  primary:     colorsData.semantic.primary,
  primaryDark: colorsData.semantic.primaryDark,

  // Surface / text
  background:  colorsData.semantic.background,
  surface:     colorsData.semantic.surface,
  border:      colorsData.semantic.border,
  textPrimary: colorsData.semantic.textPrimary,
  textMuted:   colorsData.semantic.textMuted,

  // Semantic status
  success:     colorsData.semantic.success,
  warning:     colorsData.semantic.warning,
  error:       colorsData.semantic.error,

  // Report UI
  arcBar:      colorsData.report.arcBar,
  arcLabel:    colorsData.report.arcLabel,
  selfBar:     colorsData.report.selfBar,
  trackBg:     colorsData.report.trackBg,

  // Big Five dimension colors (legacy naming for cercol compatibility)
  openness:          colorsData.brand.blue,
  conscientiousness: colorsData.brand.yellow,
  extraversion:      colorsData.brand.red,
  agreeableness:     colorsData.brand.green,
  neuroticism:       colorsData.brand.black,
}

// ── Typography ───────────────────────────────────────────────────────────────

export const fonts = {
  display: typographyData.families.display,
  sans:    typographyData.families.sans,
  mono:    typographyData.families.mono,
}

// ── Spacing ──────────────────────────────────────────────────────────────────

export const spacing = {
  pageMax: spacingData.maxWidth.page,
}

// ── Domain (Big Five dimension) colors ───────────────────────────────────────

export const DOMAIN_COLORS = {
  presence:   colorsData.domains.presence,
  bond:       colorsData.domains.bond,
  vision:     colorsData.domains.vision,
  discipline: colorsData.domains.discipline,
  depth:      colorsData.domains.depth,
}

/** Tailwind text-color classes per domain */
export const DOMAIN_ICON_CLASSES = {
  presence:   'text-amber-400',
  bond:       'text-emerald-500',
  vision:     `text-[${colorsData.brand.green}]`,
  discipline: 'text-blue-600',
  depth:      'text-red-500',
}

/** Tailwind bg-color classes per domain */
export const DOMAIN_BG_CLASSES = {
  presence:   'bg-amber-400',
  bond:       'bg-emerald-500',
  vision:     `bg-[${colorsData.brand.green}]`,
  discipline: 'bg-blue-600',
  depth:      'bg-red-500',
}

// ── Balance status colors ────────────────────────────────────────────────────

export const BALANCE_COLORS = {
  balanced:     { bg: colorsData.balance.good.bg,    text: colorsData.balance.good.text },
  tiltedHigh:   { bg: colorsData.balance.caution.bg, text: colorsData.balance.caution.text },
  tiltedLow:    { bg: colorsData.balance.caution.bg, text: colorsData.balance.caution.text },
  stronglyHigh: { bg: colorsData.balance.warning.bg, text: colorsData.balance.warning.text },
  stronglyLow:  { bg: colorsData.balance.warning.bg, text: colorsData.balance.warning.text },
  highGood:     { bg: colorsData.balance.good.bg,    text: colorsData.balance.good.text },
  lowGood:      { bg: colorsData.balance.good.bg,    text: colorsData.balance.good.text },
  lowCaution:   { bg: colorsData.balance.warning.bg, text: colorsData.balance.warning.text },
  highCaution:  { bg: colorsData.balance.warning.bg, text: colorsData.balance.warning.text },
}

// ── Role colors (R01–R12) ────────────────────────────────────────────────────

export const ROLE_COLORS = {
  R01: colorsData.roles.r01,
  R02: colorsData.roles.r02,
  R03: colorsData.roles.r03,
  R04: colorsData.roles.r04,
  R05: colorsData.roles.r05,
  R06: colorsData.roles.r06,
  R07: colorsData.roles.r07,
  R08: colorsData.roles.r08,
  R09: colorsData.roles.r09,
  R10: colorsData.roles.r10,
  R11: colorsData.roles.r11,
  R12: colorsData.roles.r12,
}

// ── Interactive colors ───────────────────────────────────────────────────────

export const INTERACTIVE_COLORS = {
  hoverBg:   colorsData.interactive.hoverBg,
  focusRing: colorsData.interactive.focusRing,
  hoverText: colorsData.interactive.hoverText,
}

// ── Gray palette ─────────────────────────────────────────────────────────────

export const GRAY = colorsData.gray
