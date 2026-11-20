#!/bin/sh
# Local manual refresh + deploy (the GitHub Actions workflow does the same every day).
set -e
cd "$(dirname "$0")"
[ -x .venv/bin/python ] || { python3 -m venv .venv && .venv/bin/pip install -q pillow; }
PYTHON=.venv/bin/python sh scripts/update_all.sh
cd site && npx -y vercel@latest deploy --prod --yes --scope czubakers-projects
