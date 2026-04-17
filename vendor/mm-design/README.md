# mm-design

Centralized design system extracted from the [cercol.team](https://cercol.team) visual identity. Single source of truth for tokens, components, and icons shared across all projects by Miquel Matoses.

---

## Brand palette

```
  #cf3339        #0047ba        #f1c22f        #427c42        #ffffff        #111111
  Red            Blue           Yellow         Green          White          Black
```

**Typography:** Playfair Display (headings) + Roboto (body) + JetBrains Mono (code)

---

## Quick start

No build step. No dependencies. Just link the CSS files you need:

```html
<!-- Tokens -->
<link rel="stylesheet" href="tokens/colors.css">
<link rel="stylesheet" href="tokens/typography.css">
<link rel="stylesheet" href="tokens/spacing.css">

<!-- Components (pick what you need) -->
<link rel="stylesheet" href="components/button/button.css">
<link rel="stylesheet" href="components/card/card.css">
```

Then use the tokens as CSS custom properties:

```css
.my-element {
  color: var(--mm-color-text-primary);
  font-family: var(--mm-font-sans);
  padding: var(--mm-space-4);
  border-radius: var(--mm-radius-base);
}
```

---

## Project structure

```
mm-design/
  tokens/
    colors.css          76 color tokens (brand, semantic, roles, domains, grays)
    colors.json         Same values as nested JSON
    typography.css      Font families, sizes, weights, line-heights, tracking
    typography.json
    spacing.css         Spacing scale, radius, shadows, widths, z-index
    spacing.json
  components/
    button/             Primary, secondary, ghost — sm, md, lg
    card/               Default + accent-red, accent-blue, accent-green, accent-yellow
    badge/              Default, beta, paid, free
    section-label/      Blue, red, green, amber, gray — uppercase eyebrow text
    input/              Text input + textarea with focus and disabled states
    nav/                Horizontal bar with brand blue background
  icons/
    moon/               4 SVGs — new-moon, first-quarter, full-moon, last-quarter
    dimension/          5 SVGs — presence, bond, vision, depth, discipline
    ui/                 16 SVGs — arrows, check, share, globe, close, etc.
    animals/            12 SVGs — role animal icons (R01 Dolphin to R12 Badger)
    react/              MoonIcons.jsx — React component source (reference)
  index.html            Live visual reference — open in any browser
  DESIGN_AUDIT.md       Full audit of cercol.team values
  CLAUDE.md             Project conventions for Claude Code
```

---

## Token naming

All CSS custom properties follow `--mm-[category]-[name]`:

| Prefix | Examples |
|---|---|
| `--mm-color-*` | `--mm-color-primary`, `--mm-color-role-r01`, `--mm-color-gray-200` |
| `--mm-font-*` | `--mm-font-display`, `--mm-font-sans`, `--mm-font-mono` |
| `--mm-text-*` | `--mm-text-xs`, `--mm-text-sm`, `--mm-text-2xl` |
| `--mm-weight-*` | `--mm-weight-normal`, `--mm-weight-semibold`, `--mm-weight-bold` |
| `--mm-leading-*` | `--mm-leading-tight`, `--mm-leading-relaxed` |
| `--mm-tracking-*` | `--mm-tracking-wide`, `--mm-tracking-widest` |
| `--mm-space-*` | `--mm-space-1`, `--mm-space-4`, `--mm-space-8` |
| `--mm-radius-*` | `--mm-radius-base`, `--mm-radius-full` |
| `--mm-shadow-*` | `--mm-shadow-sm`, `--mm-shadow-md`, `--mm-shadow-lg` |
| `--mm-width-*` | `--mm-width-content`, `--mm-width-page` |
| `--mm-z-*` | `--mm-z-base`, `--mm-z-overlay` |

---

## Importing in your project

### React / Vite

```js
// main.tsx or App.tsx
import 'mm-design/tokens/colors.css'
import 'mm-design/tokens/typography.css'
import 'mm-design/tokens/spacing.css'
import 'mm-design/components/button/button.css'
```

### Django / Wagtail

```html
<!-- base.html -->
<link rel="stylesheet" href="{% static 'mm-design/tokens/colors.css' %}">
<link rel="stylesheet" href="{% static 'mm-design/tokens/typography.css' %}">
<link rel="stylesheet" href="{% static 'mm-design/tokens/spacing.css' %}">
```

### Plain HTML / GitHub Pages

```html
<link rel="stylesheet" href="path/to/mm-design/tokens/colors.css">
<link rel="stylesheet" href="path/to/mm-design/tokens/typography.css">
<link rel="stylesheet" href="path/to/mm-design/tokens/spacing.css">
```

---

## Components

Every component is a `.css` file + `.html` example. No JavaScript. CSS classes use the `mm-` prefix.

| Component | Classes | Variants |
|---|---|---|
| **Button** | `.mm-btn --primary --secondary --ghost --sm --md --lg` | 3 variants, 3 sizes, disabled |
| **Card** | `.mm-card --accent-red --accent-blue --accent-green --accent-yellow` | Default + 4 accents |
| **Badge** | `.mm-badge --default --beta --paid --free` | 4 status variants |
| **Section Label** | `.mm-section-label --blue --red --green --amber --gray` | 5 color variants |
| **Input** | `.mm-input` | Default, focus, disabled |
| **Nav** | `.mm-nav > .mm-nav__logo + .mm-nav__links > .mm-nav__link` | Active + inactive links |

---

## Icons

37 standalone SVGs across four families. All stroke-based with `currentColor` (except animals which use `fill`).

| Family | Count | Style | Sizes used |
|---|---|---|---|
| **Moon phases** | 4 | Stroke, 32x32 viewBox | 13-80px |
| **Dimensions** | 5 | Stroke, 24x24 viewBox | 11-36px |
| **Functional UI** | 16 | Stroke, 24x24 viewBox | 13-24px |
| **Animals** | 12 | Fill, varies | 16-128px |

---

## Consuming projects

| Project | Stack | Integration |
|---|---|---|
| [cercol.team](https://cercol.team) | React / Vite | CSS imports in `main.tsx` |
| [topquaranta.cat](https://topquaranta.cat) | Django / Wagtail | `<link>` in base template |
| Portfolio | GitHub Pages | Direct `<link>` references |

---

## Tech constraints

- Vanilla HTML + CSS only. No framework, no build step required.
- Zero npm packages. Zero external dependencies.
- Every `.html` file opens directly in a browser.
- JSON token files available for tooling that needs programmatic access.

---

## License

Personal design system by Miquel Matoses. The cercol.team brand identity and animal illustrations are original artwork.
