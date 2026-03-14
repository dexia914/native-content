#!/usr/bin/env bash
set -euo pipefail

if [[ "${EUID}" -ne 0 ]]; then
  SUDO="sudo"
else
  SUDO=""
fi

if [[ ! -d ".venv" ]]; then
  python3 -m venv .venv
fi

$SUDO apt-get update
$SUDO apt-get install -y \
  python3-venv \
  python3-pip \
  libasound2t64 \
  libatk-bridge2.0-0 \
  libatk1.0-0 \
  libcups2 \
  libdbus-1-3 \
  libdrm2 \
  libgbm1 \
  libglib2.0-0 \
  libgtk-3-0 \
  libnspr4 \
  libnss3 \
  libpango-1.0-0 \
  libx11-6 \
  libx11-xcb1 \
  libxcb1 \
  libxcomposite1 \
  libxdamage1 \
  libxext6 \
  libxfixes3 \
  libxkbcommon0 \
  libxrandr2 \
  fonts-noto-cjk \
  fonts-wqy-zenhei

. .venv/bin/activate
python -m pip install --upgrade pip setuptools wheel
python -m pip install -e .
python -m playwright install chromium

echo "Ubuntu bootstrap completed."
echo "If Chinese text still renders incorrectly, set FONT_PATH in .env explicitly."
