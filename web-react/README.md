# TopQuaranta — web (React)

React + Vite + Tailwind v4 frontend for TopQuaranta. Forked from
[cercol.team](https://github.com/miquelmatoses/cercol) (Sessió 18) and
rebranded with the yellow/black TopQuaranta palette.

Consumes the Django REST API at `/api/v1/*` (same origin in production;
Vite dev server proxies to `http://127.0.0.1:8083` during `npm run dev`).

## Dev

```bash
npm install
npm run dev       # http://localhost:5173, proxying /api/* to Django
npm run build     # outputs to dist/
npm run preview   # serve the production build locally
npm test          # vitest
npm run lint      # eslint
```

## Structure

```
src/
├── App.jsx                  routes + error boundary
├── main.jsx                 entry
├── index.css                Tailwind + theme tokens
├── i18n.js                  ca / es / en locales
├── components/
│   ├── Layout.jsx           yellow header + black body + footer
│   ├── TopQuarantaLogo.jsx  horizontal wordmark + redolí
│   ├── AccountButton.jsx    user chip / sign-in pill
│   ├── AdminRoute.jsx       gate routes behind is_staff
│   ├── LanguageToggle.jsx   ca/es/en
│   └── ui/                  Button, Card, Badge, SectionLabel
├── context/
│   └── AuthContext.jsx      Django session auth
├── lib/
│   └── api.js               DRF client (session cookies + CSRF)
├── locales/                 ca.json, es.json, en.json
└── pages/
    ├── HomePage.jsx         all-yellow welcome
    ├── AuthPage.jsx         login form → /api/v1/auth/login/
    ├── AuthCallbackPage.jsx OAuth callback stub
    └── AdminDashboardPage.jsx  staff landing stub
```

## Theme

Tailwind v4's `@theme` directive in `src/index.css` declares
`tq-yellow`, `tq-ink`, etc. as CSS variables which become utility
classes (`bg-tq-yellow`, `text-tq-ink`, …). Fonts via Google Fonts —
Playfair Display (display) + Roboto (body).

Homepage sets `data-theme="yellow"` on `<body>` so the whole page
paints yellow; other pages stay on the default black body.

## What's deferred (Sprint roadmap)

- Sprint 1 — expand Django DRF (`/api/v1/ranking/`, `/artistes/`,
  `/artista/<slug>/`, `/mapa/`, `/auth/login/` + `/me/` + `/logout/`).
- Sprint 2 — public pages in React: `/ranking`, `/artistes`,
  `/artista/<slug>`, `/album/<slug>`, `/canço/<slug>`, `/mapa`,
  `/com-funciona`.
- Sprint 3 — staff panel in React: `/staff/cancons`,
  `/staff/artistes`, `/staff/pendents`, `/staff/historial`,
  `/staff/auditlog`, etc.
- Sprint 4 — Caddy flip: React bundle served at `/`, Django API at
  `/api/*`. Legacy Django templates deleted.

## Deployment

Production: Caddy serves `dist/` at `/` and proxies `/api/*` to the
Django gunicorn on `:8083`. Details land in `deploy/Caddyfile` when
we do the flip.
