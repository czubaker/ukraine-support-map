#!/bin/sh
# Rebuild every data file into build/, check it, and only then copy it into site/.
# Used by the GitHub Actions workflow and by ./update.sh locally.
set -e
cd "$(dirname "$0")/.."
PY="${PYTHON:-python3}"
rm -rf build && mkdir -p build raw

echo "== US: Track Ukraine tracker, Instagram cards, corrected roll calls"
$PY -I scripts/fetch.py raw
echo "== US: caucus lists (Wikipedia)"
$PY -I scripts/factions.py raw || echo "WARNING: faction refresh failed, keeping previous lists"
echo "== US: 119th Congress scores"
$PY -I scripts/build_data.py raw build/data.json
echo "== US: 120th Congress roster (Wikipedia)"
$PY -I scripts/build_120.py raw build || { echo "WARNING: 120th roster refresh failed, keeping previous"; cp site/data120.json build/; }
echo "== EU: HowTheyVote.eu"
sh scripts/fetch_eu.sh
$PY -I scripts/build_eu.py raw/eu build/eu.json

echo "== Sanity checks"
$PY -I scripts/check.py build site
cp build/data.json build/data120.json build/eu.json site/
echo "== Done"
