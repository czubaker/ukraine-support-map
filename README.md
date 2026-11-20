# Ukraine Support Map

Live: https://congress-ukraine-map.vercel.app

Every member of the US Congress and the European Parliament, colored by their record on Ukraine.

## How it updates

`.github/workflows/update.yml` runs every day at 06:17 UTC (and on demand from the Actions tab):

1. `scripts/update_all.sh` rebuilds everything into `build/`:
   - **US scores:** Track Ukraine's tracker API (their bill list, vote directions and weights; same formula as their widget), plus one correction in `scripts/corrections.json`.
   - **Track Ukraine verdicts:** the Instagram feed on trackukraine.com; card colors are read from the images and collected in `raw/instagram.json` over time.
   - **Factions** and the **120th Congress** roster: Wikipedia, matched to members by bioguide ID via Wikidata.
   - **European Parliament:** HowTheyVote.eu open data, votes listed in `scripts/eu_votes.json`.
2. `scripts/check.py` rejects the update if anything looks broken (missing members, factions collapsing, scores jumping); the site then keeps the previous data and the workflow fails, which emails the repo owner.
3. Data is committed back to the repo and deployed to Vercel (needs the `VERCEL_TOKEN` secret).

## Reviewing new EU votes

New Ukraine/Russia votes are counted automatically with a guessed direction (weight 0.5, marked "not reviewed" on the site), and an issue labeled `eu-review` lists them. To review, edit `scripts/eu_votes.json`: move each vote into `votes` with `dir` (`pro` = voting FOR helps Ukraine), `weight`, `label`, `"reviewed": true`, or into `excluded`.

## Local run

```
./update.sh      # rebuild + deploy from this machine
```
