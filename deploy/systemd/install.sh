#!/usr/bin/env bash
# One-shot systemd installer for a bare-metal Linux box.
# Usage: sudo bash deploy/systemd/install.sh [INSTALL_DIR]
set -euo pipefail

DIR="${1:-/opt/fare-alert}"
if [[ "$EUID" -ne 0 ]]; then
  echo "run as root: sudo bash $0" >&2
  exit 1
fi

echo "install dir: $DIR"
mkdir -p "$DIR"
cp -r ./*.py ./core ./webui ./web ./tools ./requirements.txt "$DIR/" \
  2>/dev/null || true

if [[ ! -d "$DIR/.venv" ]]; then
  python3 -m venv "$DIR/.venv"
fi
"$DIR/.venv/bin/pip" install --upgrade pip >/dev/null
"$DIR/.venv/bin/pip" install -r "$DIR/requirements.txt"

if [[ ! -f "$DIR/config.json" ]]; then
  cp "$DIR/config.example.json" "$DIR/config.json" 2>/dev/null || true
fi

sed "s#/opt/fare-alert#$DIR#g" deploy/systemd/fare-alert.service \
  > /etc/systemd/system/fare-alert.service
systemctl daemon-reload
systemctl enable --now fare-alert
echo "fare-alert enabled and started -> http://127.0.0.1:8765"
echo "logs: journalctl -u fare-alert -f"
