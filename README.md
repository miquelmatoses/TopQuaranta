<div align="center">

<img src="https://capsule-render.vercel.app/api?type=waving&color=0:0047ba,100:0047ba&height=120&section=header&animation=fadeIn" width="100%" />

# 🎵 TopQuaranta

<a href="https://www.topquaranta.cat">
  <img src="https://readme-typing-svg.herokuapp.com?font=Roboto&weight=600&size=22&pause=1000&duration=1000&color=0047ba&center=true&vCenter=true&width=600&lines=R%C3%A0nquing+setmanal+de+m%C3%BAsica+en+catal%C3%A0;Last.fm+%2B+Deezer+%C2%B7+10+territoris+%C2%B7+Top+40;Django+5.2+%2B+PostgreSQL+%C2%B7+Codi+obert" alt="Typing SVG" />
</a>

<br/>

![Status](https://img.shields.io/badge/Live-12b76a?style=for-the-badge)
![Django](https://img.shields.io/badge/Django_5.2-0047ba?style=for-the-badge&logo=django&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-0047ba?style=for-the-badge&logo=postgresql&logoColor=white)
![Last.fm](https://img.shields.io/badge/Last.fm-cf3339?style=for-the-badge&logo=lastdotfm&logoColor=white)
![CI](https://img.shields.io/github/actions/workflow/status/miquelmatoses/TopQuaranta/ci.yml?branch=main&style=for-the-badge&label=CI)

</div>

---

## <img src="https://raw.githubusercontent.com/miquelmatoses/mm-design/main/icons/readme/icon-music-red.svg" width="20" height="20" /> Què és

**TopQuaranta** és el rànquing setmanal públic de música en llengua catalana
per als Països Catalans. Cada setmana publica un **Top 40** per territori,
calculat a partir d'escoltes reals de Last.fm amb metadades de Deezer.

Missió cultural: demostrar que la música en català és **viva**, creix, i
mereix visibilitat. No monetitzem, no venem dades. El codi és obert perquè
qualsevol pugui revisar com es calcula.

## <img src="https://raw.githubusercontent.com/miquelmatoses/mm-design/main/icons/readme/icon-bolt-yellow.svg" width="20" height="20" /> Funcionalitats

- 📊 **Senyal diari** via Last.fm — `playcount` + `listeners` amb
  normalització per percentil.
- 🏆 **Rànquing setmanal** amb algoritme de 14 CTEs SQL (penalitzacions
  per antiguitat, monopoli, novetats). Transparència algorítmica
  pública a [/com-funciona/](https://www.topquaranta.cat/com-funciona/).
- 🗺️ **10 territoris**: CAT, VAL, BAL, CNO, AND, FRA, ALG, CAR, ALT, PPCC.
- 👥 **Panell staff** per gestionar artistes, propostes, cançons i
  coeficients; tota acció destructiva queda a `StaffAuditLog`.
- 🧠 **ML** per a pre-classificar cançons noves (A/B/C) i prioritzar la
  revisió humana.
- 🔒 **Seguretat**: Argon2 password hashing, 2FA TOTP staff,
  django-axes, CSP estricta.

## <img src="https://raw.githubusercontent.com/miquelmatoses/mm-design/main/icons/readme/icon-stack-blue.svg" width="20" height="20" /> Stack

<div align="center">

![Django](https://img.shields.io/badge/Django_5.2-0047ba?style=flat-square&logo=django&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-0047ba?style=flat-square&logo=postgresql&logoColor=white)
![Python](https://img.shields.io/badge/Python_3.10-0047ba?style=flat-square&logo=python&logoColor=white)
![Last.fm](https://img.shields.io/badge/Last.fm-cf3339?style=flat-square&logo=lastdotfm&logoColor=white)
![Deezer](https://img.shields.io/badge/Deezer-12b76a?style=flat-square)
![Caddy](https://img.shields.io/badge/Caddy-0047ba?style=flat-square)
![Hetzner](https://img.shields.io/badge/Hetzner-cf3339?style=flat-square)

</div>

## <img src="https://raw.githubusercontent.com/miquelmatoses/mm-design/main/icons/readme/icon-folder-blue.svg" width="20" height="20" /> Estructura

```
TopQuaranta/
├── topquaranta/   # Configuració Django + settings (base / production / web_server / test)
├── music/         # Models: Artista, Album, Canco, ArtistaDeezer, ArtistaLocalitat
├── ingesta/       # Pipeline Last.fm + Deezer (clients + management commands)
├── ranking/       # Algoritme setmanal (algorisme.py, 14 CTEs) + models
├── web/           # Públic + panell staff + API v1 (/api/v1/*)
├── comptes/       # Usuari custom, PropostaArtista, 2FA
├── bin/           # Ops scripts (tq-run, tq-recover, tq-health, tq-backup, tq-restore-test)
├── deploy/        # Caddyfile + systemd service + logrotate config
└── vendor/        # mm-design tokens (vendored)
```

## <img src="https://raw.githubusercontent.com/miquelmatoses/mm-design/main/icons/readme/icon-code-blue.svg" width="20" height="20" /> Desenvolupament local

Requisits: Python 3.10, PostgreSQL 14+ (o SQLite per a tests).

```bash
# 1. Clone
git clone git@github.com:miquelmatoses/TopQuaranta.git
cd TopQuaranta

# 2. Entorn virtual + dependencies
python3.10 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt

# 3. Variables d'entorn (vegeu CLAUDE.md §7 per la llista completa)
cp .env.example .env   # si existeix, o crea'l amb DATABASE_URL, LASTFM_API_KEY, etc.

# 4. Tests (SQLite in-memory, cap API externa)
pytest -q

# 5. Instal·la els pre-commit hooks (black + isort + missing-migration check)
pre-commit install

# 6. Servidor local
DJANGO_SETTINGS_MODULE=topquaranta.settings.local python manage.py migrate
DJANGO_SETTINGS_MODULE=topquaranta.settings.local python manage.py runserver
```

## <img src="https://raw.githubusercontent.com/miquelmatoses/mm-design/main/icons/readme/icon-user-blue.svg" width="20" height="20" /> Contribuir

- **Llegeix primer**: [`CLAUDE.md`](./CLAUDE.md) (convencions de codi,
  estructura, convencions de commit).
- **Emergències / incidents**: [`RUNBOOK.md`](./RUNBOOK.md).
- **Història del projecte**: [`ROADMAP.md`](./ROADMAP.md) i
  [`CHANGELOG.md`](./CHANGELOG.md).
- **Política d'API**: [`web/api/VERSIONING.md`](./web/api/VERSIONING.md).
- **Política de claus SSH**: [`deploy/SSH_KEY_POLICY.md`](./deploy/SSH_KEY_POLICY.md).

Cada commit ha de passar:
- **pytest** (sense xarxa: mocks per a Last.fm / Deezer).
- **black** + **isort** (configurats a `pyproject.toml`).
- **makemigrations --check** (cap canvi de model sense migració).

El CI (GitHub Actions) ho valida. El pre-commit local ho fa en segons.

## <img src="https://raw.githubusercontent.com/miquelmatoses/mm-design/main/icons/readme/icon-pulse-green.svg" width="20" height="20" /> Estat

🟢 **En producció**: [topquaranta.cat](https://www.topquaranta.cat).

El pipeline corre automàticament via cron (hourly `obtenir_novetats`,
daily `obtenir_senyal`, weekly `calcular_ranking` oficials; vegeu
`/etc/cron.d/topquaranta` i `ROADMAP.md`). Health: `tq-health` sobre el
servidor.

---

<div align="center">

![Last Updated](https://img.shields.io/badge/Última_actualització-Abril_2026-0047ba?style=flat-square)
![License](https://img.shields.io/badge/Codi-AGPL_3.0-cf3339?style=flat-square)
![Data](https://img.shields.io/badge/Dades-CC_BY_4.0-12b76a?style=flat-square)

<img src="https://capsule-render.vercel.app/api?type=waving&color=0:0047ba,100:0047ba&height=80&section=footer" width="100%" />

</div>
