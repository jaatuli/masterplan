#!/bin/bash
# Sync project files to Home Assistant /config/eink/
# Requires SSH access to your HA host (e.g. homeassistant.local or IP)
HA_HOST="${HA_HOST:-homeassistant.local}"
HA_USER="${HA_USER:-root}"

rsync -av \
  --exclude venv \
  --exclude cache \
  --exclude output \
  --exclude .git \
  --exclude __pycache__ \
  --exclude ha \
  --exclude esphome \
  "$(dirname "$0")/" "${HA_USER}@${HA_HOST}:/config/eink/"
