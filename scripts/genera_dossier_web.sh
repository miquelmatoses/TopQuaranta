#!/usr/bin/env bash
set -euo pipefail

# ——— Paths del projecte ———
PROJECT_ROOT="/root/TopQuaranta"
CMS_DIR="$PROJECT_ROOT/web_cms"
VENV_PY="$PROJECT_ROOT/venv/bin/python"
OUT="$PROJECT_ROOT/dossier_web.txt"

# ——— Entorn Django (producció) ———
export DJANGO_SETTINGS_MODULE="tqcms.settings.production"

cd "$CMS_DIR"

# —— Utilitats locals —— #
have() { command -v "$1" >/dev/null 2>&1; }
if have rg; then
  RG="rg -n --hidden --glob '!venv' --glob '!**/__pycache__/*'"
else
  RG="grep -nR --exclude-dir=venv --exclude-dir='**/__pycache__' --line-number"
fi
p() { sed -n "${2:-1},${3:-200}p" "$1"; } # p <file> [start] [end]

{
  echo "==== 📂 ESTRUCTURA (resum) ===="
  tree -a -L 3 -I '__pycache__|*.pyc|*.pyo|*.log|staticfiles|node_modules' .

  echo -e "\n==== 🗂️ .ENV (claus sanejades) ===="
  if [ -f .env ]; then
    sed -E 's/^([[:space:]]*#.*)$/\1/g; s@^([A-Za-z0-9_]+)=.*@\1=****@' .env
  else
    echo "No s'ha trobat .env"
  fi

  echo -e "\n==== ⚙️ SETTINGS CLAU (diffsettings) ===="
  "$VENV_PY" manage.py diffsettings | egrep -i '^(ALLOWED_HOSTS|DEBUG|CSRF_TRUSTED_ORIGINS|SECURE_|SESSION_COOKIE_|CSRF_\
COOKIE_|USE_X_FORWARDED_HOST|SECURE_PROXY_SSL_HEADER|WAGTAIL|STATIC_|MEDIA_|DATABASES|INSTALLED_APPS|MIDDLEWARE|ROOT_URL\
CONF|TEMPLATES)'

  echo -e "\n==== ✅ Django check --deploy ===="
  "$VENV_PY" manage.py check --deploy || true

  echo -e "\n==== 🔁 Migrations (plan) ===="
  "$VENV_PY" manage.py showmigrations --plan

  echo -e "\n==== 🌐 Ports i processos web ===="
  ss -tulpn | grep -E 'LISTEN' | grep -E '(:80|:443|:8081)' || true
  echo
  echo "→ gunicorn PIDs i comandament:"
  ps -o pid,cmd -C gunicorn || true

  echo -e "\n==== 🧩 Systemd units (caddy/django) ===="
  systemctl is-active caddy >/dev/null 2>&1 && systemctl status --no-pager caddy | sed -n '1,60p'
  echo
  for SVC in topquaranta_web.service; do
    if systemctl list-units --type=service --all | grep -q "$SVC"; then
      echo "---- systemctl status $SVC ----"
      systemctl status --no-pager "$SVC" | sed -n '1,80p'
      echo "---- systemctl cat $SVC ----"
      systemctl cat "$SVC"
    fi
  done

  echo -e "\n==== 📜 Logs recents (gunicorn/caddy) ===="
  journalctl -u caddy -n 80 --no-pager 2>/dev/null || true
  echo
  journalctl -u topquaranta_web.service -n 120 --no-pager 2>/dev/null || true

  echo -e "\n==== 🌍 Config Caddy ===="
  if [ -f /etc/caddy/Caddyfile ]; then
    echo "---- /etc/caddy/Caddyfile ----"
    sed -n '1,200p' /etc/caddy/Caddyfile
  else
    echo "No s'ha trobat /etc/caddy/Caddyfile"
  fi
  echo
  echo "→ Versió Caddy:"
  caddy version 2>/dev/null || true
  echo
  echo "→ Mòduls Caddy (resum):"
  caddy list-modules 2>/dev/null | head -n 30 || true
  echo
  echo "→ Certs emmagatzemats per Caddy:"
  ls -R /var/lib/caddy/.local/share/caddy/certificates 2>/dev/null || echo "No s'han llistat certificats (pot requerir p\
ermisos o ruta distinta)."

  echo -e "\n==== 🔐 Prova TLS amb curl (headers) ===="
  BASE_URL="$("$VENV_PY" - <<'PY'
from django.conf import settings
print(getattr(settings, "WAGTAILADMIN_BASE_URL", "") or "")
PY
  )"
  if [ -z "$BASE_URL" ]; then
    BASE_URL="https://188-245-60-20.sslip.io"
  fi
  curl -vkI "$BASE_URL" 2>&1 | sed -n '1,40p'

  echo -e "\n==== 🐘 DB settings efectives ===="
  "$VENV_PY" - <<'PY'
from django.conf import settings
db=settings.DATABASES["default"]
print("ENGINE:", db["ENGINE"])
print("HOST:", db["HOST"])
print("PORT:", db["PORT"])
print("NAME:", db["NAME"])
print("USER:", db["USER"])
print("PASSWORD:", "****" if db.get("PASSWORD") else "(buit)")
PY

  echo -e "\n==== 📦 Paquets Python (freeze) ===="
  "$PROJECT_ROOT/venv/bin/pip" freeze | egrep -i '^(Django|wagtail|gunicorn|whitenoise|psycopg|django-allauth|caddy)' ||\
 "$PROJECT_ROOT/venv/bin/pip" freeze | head -n 50

  echo -e "\n==== 🗂️ Static/Media paths i existència ===="
  "$VENV_PY" - <<'PY'
import os
from django.conf import settings
print("STATIC_URL:", settings.STATIC_URL)
print("STATIC_ROOT:", settings.STATIC_ROOT, "→ exists:", os.path.isdir(settings.STATIC_ROOT))
print("STATICFILES_DIRS:", settings.STATICFILES_DIRS)
print("MEDIA_URL:", settings.MEDIA_URL)
print("MEDIA_ROOT:", settings.MEDIA_ROOT, "→ exists:", os.path.isdir(settings.MEDIA_ROOT))
PY

  echo -e "\n==== 🧭 URL root i versió Wagtail ===="
  "$VENV_PY" - <<'PY'
from django.conf import settings
print("ROOT_URLCONF:", settings.ROOT_URLCONF)
try:
    from wagtail import VERSION as WV
    print("Wagtail version:", ".".join(map(str,WV)))
except Exception as e:
    print("Wagtail version: (no disponible)", e)
PY

  # ———— CODI CLAU (RESUMS I EXTRACTES) ————

  echo -e "\n==== 🧠 Models & StreamFields — home/models.py ===="
  if [ -f home/models.py ]; then
    echo "— Classes Page / StreamFields:"
    $RG -e '^class .*Page' -e 'StreamField' -e '^    content_panels' home/models.py || true
    echo
    echo "— Mètodes (get_context / serve):"
    $RG -e 'def (get_context|serve)\(' home/models.py || true
    echo
    echo "— Capçalera (1–220):"
    nl -ba home/models.py | sed -n '1,220p'
  else
    echo "home/models.py no trobat"
  fi

  echo -e "\n==== 🧱 Blocks — home/blocks.py ===="
  if [ -f home/blocks.py ]; then
    echo "— Definicions de Block:"
    $RG -e '^class .*Block' -e 'StructBlock' -e 'ListBlock' home/blocks.py || true
    echo
    echo "— Fragments (1–200):"
    nl -ba home/blocks.py | sed -n '1,200p'
  else
    echo "home/blocks.py no trobat"
  fi

  echo -e "\n==== 🧭 URLs principals — tqcms/urls.py ===="
  if [ -f tqcms/urls.py ]; then
    nl -ba tqcms/urls.py | sed -n '1,300p'
  else
    echo "tqcms/urls.py no trobat"
  fi

  echo -e "\n==== 🪝 Wagtail hooks — home/wagtail_hooks.py ===="
  if [ -f home/wagtail_hooks.py ]; then
    echo "— Hooks registrats:"
    $RG -e 'hooks\.register' -e 'register_snippet' -e 'modeladmin_register' home/wagtail_hooks.py || true
    echo
    echo "— Contingut (1–200):"
    nl -ba home/wagtail_hooks.py | sed -n '1,200p'
  else
    echo "home/wagtail_hooks.py no trobat"
  fi

  echo -e "\n==== 👤 Registre / Login (Allauth) — settings & vistes ===="
  echo "— Ajustos allauth (settings):"
  $VENV_PY - <<'PY'
from django.conf import settings
keys = ['INSTALLED_APPS','AUTHENTICATION_BACKENDS','LOGIN_REDIRECT_URL','ACCOUNT_AUTHENTICATION_METHOD','ACCOUNT_EMAIL_R\
EQUIRED','ACCOUNT_EMAIL_VERIFICATION','ACCOUNT_LOGIN_ATTEMPTS_LIMIT','ACCOUNT_SIGNUP_REDIRECT_URL']
for k in keys:
    v = getattr(settings,k,None)
    if v is not None:
        print(f"{k} =", v)
PY
  if [ -f home/views_signup.py ]; then
    echo
    echo "— home/views_signup.py (1–220):"
    nl -ba home/views_signup.py | sed -n '1,220p'
  else
    echo "home/views_signup.py no trobat (potser useu only-urls/templates)."
  fi
  echo
  echo "— Plantilles allauth personalitzades:"
  find . -type f -path "./**/templates/**/account/*.html" -maxdepth 6 2>/dev/null || true

  echo -e "\n==== 🎨 Base template — tqcms/templates/base.html ===="
  if [ -f tqcms/templates/base.html ]; then
    nl -ba tqcms/templates/base.html | sed -n '1,300p'
  else
    echo "tqcms/templates/base.html no trobat"
  fi

  # ———— NOVES SECCIONS DEMANADES — SNIPPETS, TEMPLATES, ETC. ————

  echo -e "\n==== 🧩 Snippets (models marcats amb @register_snippet) ===="
  $RG -e '@register_snippet' -e 'from wagtail\.snippets' -e 'SnippetChooserBlock' . || echo "Cap referència a snippets t\
robada."
  echo
  echo "— Fitxers amb @register_snippet (capçalera 1–160):"
  # Imprimeix els primers 160 de cada fitxer que conté @register_snippet
  for f in $( $RG -l -e '@register_snippet' . || true ); do
    echo "---- $f ----"
    nl -ba "$f" | sed -n '1,160p'
  done

  echo -e "\n==== 🧾 Templates — índex general ===="
  if [ -d templates ]; then
    tree -a -L 3 templates
  else
    echo "Carpeta templates no trobada"
  fi

  echo -e "\n==== 🧾 Templates — blocks/*.html (1–160 c/u) ===="
  if [ -d templates/blocks ]; then
    for t in templates/blocks/*.html; do
      [ -f "$t" ] || continue
      echo "---- $t ----"
      nl -ba "$t" | sed -n '1,160p'
    done
  else
    echo "No hi ha templates/blocks"
  fi

  echo -e "\n==== 🧾 Templates — home/*.html (1–200 c/u) ===="
  if [ -d templates/home ]; then
    for t in templates/home/*.html; do
      [ -f "$t" ] || continue
      echo "---- $t ----"
      nl -ba "$t" | sed -n '1,200p'
    done
  else
    echo "No hi ha templates/home"
  fi

  echo -e "\n==== 🧾 Templates — includes/*.html (1–160 c/u) ===="
  if [ -d templates/includes ]; then
    for t in templates/includes/*.html; do
      [ -f "$t" ] || continue
      echo "---- $t ----"
      nl -ba "$t" | sed -n '1,160p'
    done
  else
    echo "No hi ha templates/includes"
  fi

  echo -e "\n==== 🧾 Templates — snippets/*.html (1–160 c/u) ===="
  if [ -d templates/snippets ]; then
    for t in templates/snippets/*.html; do
      [ -f "$t" ] || continue
      echo "---- $t ----"
      nl -ba "$t" | sed -n '1,160p'
    done
  else
    echo "No hi ha templates/snippets"
  fi

  echo -e "\n==== 🧾 Templates — account/*.html (Allauth) (1–160 c/u) ===="
  if ls templates/**/account/*.html >/dev/null 2>&1; then
    for t in $(ls templates/**/account/*.html); do
      echo "---- $t ----"
      nl -ba "$t" | sed -n '1,160p'
    done
  else
    echo "No hi ha templates d'account personalitzades"
  fi

  echo -e "\n==== 🏷️ templatetags personalitzats ===="
  if ls */templatetags/*.py >/dev/null 2>&1; then
    for f in $(ls */templatetags/*.py); do
      echo "---- $f (1–160) ----"
      nl -ba "$f" | sed -n '1,160p'
    done
  else
    echo "No s'han trobat templatetags"
  fi

  echo -e "\n==== 📝 Forms rellevants (home/forms.py 1–220) ===="
  if [ -f home/forms.py ]; then
    nl -ba home/forms.py | sed -n '1,220p'
  else
    echo "home/forms.py no trobat"
  fi

  echo -e "\n==== 🛠️ Management commands (llistat i capçalera) ===="
  if ls */management/commands/*.py >/dev/null 2>&1; then
    ls -1 */management/commands/*.py
    echo
    for f in $(ls */management/commands/*.py); do
      echo "---- $f (1–120) ----"
      nl -ba "$f" | sed -n '1,120p'
    done
  else
    echo "No s'han trobat management commands"
  fi

  echo -e "\n==== 🧱 Admin ModelAdmin/Model definitions (resum) ===="
  $RG -e 'class .*Admin' -e 'modeladmin_register' -e 'admin\.register' . || echo "No s'han trobat registres d'admin espe\
cífics."
  echo
  echo "— Capçaleres de possibles arxius d'admin.py:"
  for f in $( $RG -l -e 'admin\.site\.register|admin\.register|ModelAdmin|modeladmin_register' . || true ); do
    echo "---- $f ----"
    nl -ba "$f" | sed -n '1,120p'
  done

  echo -e "\n==== 🧾 Altres templates útils (search/*.html, tags/*.html, 1–160) ===="
  if ls templates/search/*.html >/dev/null 2>&1; then
    for t in templates/search/*.html; do
      echo "---- $t ----"
      nl -ba "$t" | sed -n '1,160p'
    done
  fi
  if ls templates/tags/*.html >/dev/null 2>&1; then
    for t in templates/tags/*.html; do
      echo "---- $t ----"
      nl -ba "$t" | sed -n '1,160p'
    done
  fi

  echo -e "\n==== 🗃️ Arxius de configuració de Wagtail/Django addicionals ===="
  if [ -f tqcms/settings/base.py ]; then
    echo "---- tqcms/settings/base.py (1–180) ----"
    nl -ba tqcms/settings/base.py | sed -n '1,180p'
  fi
  if [ -f tqcms/settings/production.py ]; then
    echo "---- tqcms/settings/production.py (1–160) ----"
    nl -ba tqcms/settings/production.py | sed -n '1,160p'
  fi
  if [ -f tqcms/settings/dev.py ]; then
    echo "---- tqcms/settings/dev.py (1–160) ----"
    nl -ba tqcms/settings/dev.py | sed -n '1,160p'
  fi

  echo -e "\n==== 🧷 SnippetChooserBlock — on s’usa ===="
  $RG -e 'SnippetChooserBlock' . || echo "No s'usa SnippetChooserBlock (o no hi ha coincidències)."

  echo -e "\n==== 🧾 Llistat breu d’arxius CSS principals (sense contingut) ===="
  if [ -d static ]; then
    find static -type f -iname '*.css' -maxdepth 3 -printf '%p\n' 2>/dev/null || true
  else
    echo "No hi ha carpeta static/"
  fi

} > "$OUT"

echo "✅ Dossier regenerat: $OUT"
