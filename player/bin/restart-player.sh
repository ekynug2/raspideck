#!/usr/bin/env bash
# RaspiDeck restricted sudo wrapper script for restarting player service
set -e

ACTION="${1:-restart}"

if [ "$ACTION" = "restart" ]; then
    echo "[restart-player] Restarting raspideck service..."
    systemctl restart raspideck.service
elif [ "$ACTION" = "status" ]; then
    systemctl status raspideck.service --no-pager
else
    echo "Unknown action: $ACTION" >&2
    exit 1
fi
