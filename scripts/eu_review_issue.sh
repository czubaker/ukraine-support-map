#!/bin/sh
# Open (or refresh) a GitHub issue listing EU votes that were auto-classified and need review.
[ -f build/eu_new_votes.json ] || exit 0
python3 - <<'PY' > build/eu_issue.md
import json
votes = json.load(open("build/eu_new_votes.json"))
print("New Ukraine/Russia votes in the European Parliament were added to MEP scores **automatically**, with a guessed direction and weight 0.5. Please review them.\n")
print("For each vote: move it into `votes` (set `dir`, `weight`, `label`, `\"reviewed\": true`) or into `excluded` in `scripts/eu_votes.json`.\n")
for v in votes:
    print(f"- [{v['title']}]({v['url']}) ({v['date']}, {v['for']} for / {v['against']} against), guessed: voting FOR = **{v['guess']}-Ukraine**")
PY
gh label create eu-review --color FBCA04 --description "EU votes to review" 2>/dev/null || true
n=$(gh issue list --label eu-review --state open --json number --jq '.[0].number')
if [ -n "$n" ]; then gh issue edit "$n" --body-file build/eu_issue.md; else gh issue create --title "Review new European Parliament votes" --label eu-review --body-file build/eu_issue.md; fi
