#!/bin/sh
# Daily job on this Mac (started by launchd): rebuild data, check it, deploy, save to GitHub, notify.
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"
export VERCEL_ORG_ID=team_EQtsA129Us9dOHQwj6hJadHJ VERCEL_PROJECT_ID=prj_zwQ5Ex4WZnOoVSGJghtgJiJGHVJE
cd "$(dirname "$0")/.." || exit 1
mkdir -p logs
find logs -name 'update-*.log' -mtime +30 -delete 2>/dev/null
LOG="logs/update-$(date +%F).log"
notify() { osascript -e "display notification \"$1\" with title \"Ukraine Support Map\"" >/dev/null 2>&1; }
{
  echo "=== $(date)"
  git pull -q --rebase --autostash || echo "WARNING: git pull failed, continuing with local copy"
  [ -x .venv/bin/python ] || { python3 -m venv .venv && .venv/bin/pip install -q pillow; }
  if PYTHON=.venv/bin/python sh scripts/update_all.sh; then
    if npx -y vercel@latest deploy site --prod --yes; then
      git add site/data.json site/data120.json site/eu.json raw/instagram.json raw/igimg raw/factions.json
      git diff --cached --quiet || { git commit -q -m "Data update $(date +%F)" && git push -q || echo "WARNING: git push failed"; }
      if [ -f build/eu_new_votes.json ]; then sh scripts/eu_review_issue.sh; notify "Site updated. New EU votes need review (see GitHub issue)."; else notify "Site updated."; fi
      echo "=== OK"
    else
      notify "Data rebuilt but the Vercel deploy failed. See logs/."; echo "=== DEPLOY FAILED"; exit 1
    fi
  else
    notify "Update rejected or failed; the site keeps the previous data. See logs/."; echo "=== UPDATE FAILED"; exit 1
  fi
} >> "$LOG" 2>&1
