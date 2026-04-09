#!/bin/bash

TERRITORI="albums"
LOCKFILE="/tmp/send_telegram_post_${TERRITORI}.lock"

if [ -e "$LOCKFILE" ]; then
    echo "⏳ Encara s'està executant per al territori $TERRITORI, ixint..."
    exit 0
fi
touch "$LOCKFILE"
trap "rm -f $LOCKFILE" EXIT

export PATH="/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin"
cd /root/TopQuaranta
set -a
. .env
set +a
source venv/bin/activate

timeout 180 venv/bin/python3 scripts/generate_new_albums.py
timeout 120 venv/bin/python3 scripts/send_telegram_post.py "$TERRITORI"
