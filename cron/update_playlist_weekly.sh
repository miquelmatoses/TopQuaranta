#!/bin/bash

LOCKFILE="/tmp/update_playlist_weekly.lock"

if [ -e "$LOCKFILE" ]; then
    echo "⏳ Encara s'està executant, ixint..."
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

# 🌀 PAS 1: Actualitza la playlist setmanal (Spotify)
timeout 300 venv/bin/python3 scripts/update_playlist_weekly.py

# 🖼️ PAS 2: Genera totes les imatges
timeout 600 venv/bin/python3 scripts/generate_images.py

# 📝 PAS 3: Genera tots els posts d’Instagram
timeout 300 venv/bin/python3 scripts/generate_instagram_post.py

# 📢 PAS 4: Envia per Telegram el post del rànquing general
timeout 120 venv/bin/python3 scripts/send_telegram_post.py general
