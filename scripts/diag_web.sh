#!/usr/bin/env bash
# Diagnòstic silenciat: només mostra problemes
# Projecte: TopQuaranta (Wagtail/Django + Gunicorn + Caddy)

set +euo pipefail

PROJECT_ROOT="/root/TopQuaranta"
WEB_DIR="$PROJECT_ROOT/web_cms"
VENV_DIR="$PROJECT_ROOT/venv"
DJANGO_SETTINGS_MODULE="tqcms.settings.production"
LOOPBACK_URL="http://127.0.0.1:8081/"
SITE_HTTP="http://topquaranta.cat/"
SITE_HTTPS="https://www.topquaranta.cat/"
OK=1

say_issue(){ OK=0; printf "\n🔴 %s\n" "$1"; }
say_warn(){ OK=0; printf "\n🟠 %s\n" "$1"; }
say_info(){ printf "\nℹ️  %s\n" "$1"; }

# 0) Context mínim
date -Is >/dev/null || true

# 1) Serveis (systemd)
if ! systemctl is-active --quiet topquaranta_web.service; then
  say_issue "Gunicorn (topquaranta_web.service) no està actiu."
  systemctl --no-pager --full status topquaranta_web.service | tail -n 60
fi
if systemctl is-failed --quiet topquaranta_web.service; then
  say_issue "Gunicorn està en estat FAILED."
  systemctl --no-pager --full status topquaranta_web.service | tail -n 80
fi
if ! systemctl is-active --quiet caddy.service; then
  say_issue "Caddy (reverse proxy) no està actiu."
  systemctl --no-pager --full status caddy.service | tail -n 60
fi

# 2) Ports en escolta
if ! ss -ltn | grep -q ":8081 "; then
  say_issue "No hi ha cap procés escoltant en 127.0.0.1:8081 (Gunicorn?)."
  ss -ltn | sed -n '1,120p'
fi

# 3) Proves HTTP bàsiques (només es mostra si hi ha problema)
http_check(){
  local url="$1" label="$2"
  local code
  code=$(curl -sS -o /dev/null -w "%{http_code}" "$url" 2>/dev/null)
  if [[ -z "$code" || "$code" -lt 200 || "$code" -ge 400 ]]; then
    say_issue "HTTP KO a $label ($url) → codi $code"
    curl -sS -I "$url" || true
  fi
}
http_check "$LOOPBACK_URL" "Gunicorn loopback"
http_check "$SITE_HTTP" "Domini HTTP"
http_check "$SITE_HTTPS" "Domini HTTPS"

# 4) venv + Django checks (només es mostren si hi ha problema)
if [ -d "$VENV_DIR" ]; then
  # shellcheck disable=SC1090
  source "$VENV_DIR/bin/activate" 2>/dev/null
else
  say_issue "No s'ha trobat el venv a $VENV_DIR"
fi

if [ -d "$WEB_DIR" ]; then
  cd "$WEB_DIR" || true
  export DJANGO_SETTINGS_MODULE="$DJANGO_SETTINGS_MODULE"

  # 4.1) django check
  DJ_CHECK=$(python manage.py check 2>&1)
  if ! echo "$DJ_CHECK" | grep -q "System check identified no issues"; then
    say_issue "Django check mostra avisos o errors:"
    echo "$DJ_CHECK" | sed -n '1,200p'
  fi

  # 4.2) django check --deploy
  DJ_DEP=$(python manage.py check --deploy 2>&1)
  if ! echo "$DJ_DEP" | grep -q "no issues"; then
    say_warn "check --deploy amb recomanacions:"
    echo "$DJ_DEP" | sed -n '1,200p'
  fi

  # 4.3) Import WSGI
  python - <<'PY' 2>/tmp/_wsgi_err.txt
import importlib
import sys
try:
    importlib.import_module("tqcms.wsgi").application
    sys.exit(0)
except Exception as e:
    sys.exit(1)
PY
  if [ $? -ne 0 ]; then
    say_issue "Error important importat WSGI (tqcms.wsgi)."
    sed -n '1,200p' /tmp/_wsgi_err.txt
  fi

  # 4.4) DB SELECT 1
  python - <<'PY' 2>/tmp/_db_err.txt
from django.db import connections
from django.db.utils import OperationalError
try:
    with connections['default'].cursor() as c:
        c.execute("SELECT 1;")
    raise SystemExit(0)
except OperationalError as e:
    print(e)
    raise SystemExit(2)
except Exception as e:
    print(e)
    raise SystemExit(1)
PY
  rc=$?
  if [ $rc -ne 0 ]; then
    say_issue "Connexió a la base de dades ha fallat (SELECT 1)."
    sed -n '1,120p' /tmp/_db_err.txt
  fi

  # 4.5) Migracions pendents
  python manage.py showmigrations --plan 2>/dev/null | grep -q "^\[ \]" 
  if [ $? -eq 0 ]; then
    say_warn "Hi ha migracions pendents:"
    python manage.py showmigrations --plan | sed -n '1,200p'
  fi

  # 4.6) STATIC/MEDIA existència
  python - <<'PY' >/tmp/_paths.txt 2>/dev/null
from django.conf import settings
import os
print("STATIC_ROOT", settings.STATIC_ROOT, os.path.isdir(settings.STATIC_ROOT))
print("MEDIA_ROOT", settings.MEDIA_ROOT, os.path.isdir(settings.MEDIA_ROOT))
PY
  if ! grep -q "STATIC_ROOT .* True" /tmp/_paths.txt; then
    say_warn "STATIC_ROOT inexistent o sense permisos:"
    cat /tmp/_paths.txt | sed -n '1,1p'
  fi
  if ! grep -q "MEDIA_ROOT .* True" /tmp/_paths.txt; then
    say_warn "MEDIA_ROOT inexistent o sense permisos:"
    cat /tmp/_paths.txt | sed -n '2,2p'
  fi
else
  say_issue "Directori web no trobat: $WEB_DIR"
fi

# 5) Logs recents filtrats
#   Mostrem només línies crítiques/tracebacks últims 5 minuts
J_GUNI=$(journalctl -u topquaranta_web.service --since "5 min ago" --no-pager 2>/dev/null | egrep -i "ERROR|CRITICAL|Tra\
ceback|Internal Server Error")
if [ -n "$J_GUNI" ]; then
  say_issue "Errors recents a Gunicorn (últimes 2h):"
  echo "$J_GUNI" | tail -n 120
fi

J_CADDY=$(journalctl -u caddy --since "5 min ago" --no-pager 2>/dev/null | egrep -i "ERROR|CRITICAL|panic|tls:|proxy|ups\
tream|502|503|504")
if [ -n "$J_CADDY" ]; then
  say_issue "Errors recents a Caddy (últimes 2h):"
  echo "$J_CADDY" | tail -n 120
fi

# 6) Espai disc baix (<10% lliure)
if df -P / | awk 'NR==2 { if ($5+0 >= 90) exit 0; else exit 1 }'; then
  say_warn "Poc espai en / (>=90% ús):"
  df -h /
fi

# 7) Resum
if [ $OK -eq 1 ]; then
  echo "✅ Tot correcte: no s'han detectat problemes en aquest diagnòstic."
fi
