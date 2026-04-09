#!/bin/bash

LOCKFILE="/tmp/update_playlist_daily.lock"

# Evita execucions duplicades
if [ -e "$LOCKFILE" ]; then
    echo "⏳ Encara s'està executant, ixint..."
    exit 0
fi
touch "$LOCKFILE"
trap "rm -f $LOCKFILE" EXIT

# Exportar PATH per a cron
export PATH="/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin"

cd /root/TopQuaranta
set -a
. .env
set +a
source venv/bin/activate

# 🧠 Temps màxim de cada script: 3-5 minuts
timeout 180 /root/TopQuaranta/venv/bin/python3 scripts/bot_exclusions.py
timeout 300 /root/TopQuaranta/venv/bin/python3 scripts/update_playlist_daily.py
