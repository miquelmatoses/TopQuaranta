<div align="center">

<img src="https://capsule-render.vercel.app/api?type=waving&color=0:0047ba,100:0047ba&height=120&section=header&animation=fadeIn" width="100%" />

# 🎵 TopQuaranta

<a href="https://github.com/miquelmatoses/TopQuaranta">
  <img src="https://readme-typing-svg.herokuapp.com?font=Roboto&weight=600&size=22&pause=1000&duration=1000&color=0047ba&center=true&vCenter=true&width=600&lines=R%C3%A0nquing+setmanal+de+m%C3%BAsica+en+catal%C3%A0;Last.fm+%C2%B7+10+territoris+%C2%B7+Top+40;Django+5.2+%2B+Wagtail+7.0+%2B+PostgreSQL" alt="Typing SVG" />
</a>

<br/>

![Status](https://img.shields.io/badge/En_Desenvolupament-cf3339?style=for-the-badge)
![Django](https://img.shields.io/badge/Django_5.2-0047ba?style=for-the-badge&logo=django&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-0047ba?style=for-the-badge&logo=postgresql&logoColor=white)
![Last.fm](https://img.shields.io/badge/Last.fm-cf3339?style=for-the-badge&logo=lastdotfm&logoColor=white)

</div>

---

## Què és

**TopQuaranta** és un sistema de rànquing setmanal de música en llengua catalana que cobreix tots els territoris de parla catalana.

Missió cultural: demostrar que la música en català és viva, creix, i mereix visibilitat.

El rànquing es publica cada setmana amb un **Top 40** per territori, calculat a partir de dades reals d'escolta.

## Funcionalitats

- 📊 **Senyal diari** via Last.fm — `playcount` (reproduccions acumulades) + `listeners` (oients únics)
- 🏆 **Rànquing setmanal** amb algoritme de 14 CTEs SQL (penalitzacions per antiguitat, monopoli, novetats)
- 🗺️ **10 territoris**: CAT, VAL, BAL, CNO, AND, FRA, ALG, CAR, ALT, PPCC
- ⚙️ **Admin Wagtail** per gestió d'artistes, àlbums, cançons i rànquings
- 📋 **Rànquing provisional** interactiu a l'admin

## Stack

<div align="center">

![Django](https://img.shields.io/badge/Django-0047ba?style=flat-square&logo=django&logoColor=white)
![Wagtail](https://img.shields.io/badge/Wagtail-0047ba?style=flat-square&logo=wagtail&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-0047ba?style=flat-square&logo=postgresql&logoColor=white)
![Python](https://img.shields.io/badge/Python-0047ba?style=flat-square&logo=python&logoColor=white)
![Last.fm](https://img.shields.io/badge/Last.fm-cf3339?style=flat-square&logo=lastdotfm&logoColor=white)
![Hetzner](https://img.shields.io/badge/Hetzner-cf3339?style=flat-square&logo=hetzner&logoColor=white)

</div>

## Estructura

```
TopQuaranta/
├── topquaranta/     # Configuració Django + settings
├── music/           # Models: Artista, Album, Cançó
├── ingesta/         # Pipeline Last.fm → senyal diari
├── ranking/         # Algoritme de rànquing (14-CTE SQL)
├── distribucio/     # Distribució pública (web, futur)
└── legacy/          # Models legacy (només lectura)
```

## Estat

🟢 **Pipeline operacional** — ingesta diària + rànquing setmanal funcionant.

🔧 **Web pública** — pròximament a [topquaranta.cat](https://www.topquaranta.cat).

---

<div align="center">

![Last Updated](https://img.shields.io/badge/Última_actualització-Abril_2026-0047ba?style=flat-square)

<img src="https://capsule-render.vercel.app/api?type=waving&color=0:0047ba,100:0047ba&height=80&section=footer" width="100%" />

</div>
