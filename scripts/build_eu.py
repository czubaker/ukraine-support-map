"""European Parliament: score current MEPs on curated Ukraine votes (HowTheyVote.eu open data) -> site/eu.json

Same formula as the US page (Track Ukraine's): weighted share of pro- vs anti-Ukraine votes,
abstentions/absences ignored, short records pulled toward the political group's average.
"""
import csv, gzip, json, sys
from datetime import datetime, timezone
RAW = sys.argv[1] if len(sys.argv) > 1 else "raw/eu"
OUT = sys.argv[2] if len(sys.argv) > 2 else "site/eu.json"

# vote_id: (weight, direction, short label). direction "pro" = voting FOR helps Ukraine, "anti" = voting FOR hurts Ukraine.
import os
CFG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "eu_votes.json")
CFG = json.load(open(CFG_PATH))
VOTES = {k: (v["weight"], v["dir"], v["label"]) for k, v in CFG["votes"].items()}
REVIEWED = {k: v.get("reviewed", True) for k, v in CFG["votes"].items()}

GROUPS = {  # seating order left -> right
  "GUE_NGL": ("The Left", "LE"), "SD": ("S&D", "SD"), "GREEN_EFA": ("Greens/EFA", "GR"), "RENEW": ("Renew Europe", "RE"),
  "EPP": ("EPP", "EP"), "ECR": ("ECR", "EC"), "PFE": ("Patriots for Europe", "PF"), "ESN": ("Europe of Sovereign Nations", "ES"), "NI": ("Non-attached", "NI"),
}
def rd(name): return csv.DictReader(gzip.open(f"{RAW}/{name}.csv.gz", "rt", encoding="utf-8"))
countries = {r["code"]: (r["label"], r["iso_alpha_2"]) for r in rd("countries")}
parties = {r["id"]: (r["label"], r["short_label"]) for r in rd("national_parties")}
cur_group = {r["member_id"]: r["group_code"] for r in rd("group_memberships") if r["term"] == "10" and not r["end_date"].strip()}
cur_party = {r["member_id"]: r["national_party_id"] for r in rd("national_party_memberships") if not r["end_date"].strip()}
members = {r["id"]: r for r in rd("members") if r["id"] in cur_group}
import re as _re
geo_ids = {r["vote_id"] for r in rd("geo_area_votes") if r.get("geo_area_code") in ("UKR", "RUS")}
new_votes = []
votes_meta = {}
for r in rd("votes"):
    if r["id"] in VOTES: votes_meta[r["id"]] = r; continue
    if r["timestamp"] < "2024-07-16" or r["is_main"] != "True" or r["id"] in CFG["excluded"]: continue
    title = (r["display_title"] or "") + " " + (r["procedure_title"] or "")
    if r["id"] in geo_ids or _re.search(r"Ukrain|Russia|Belarus", title, _re.I):
        # rule-based guess, marked as not reviewed: rejection motions count in reverse
        rejection = _re.search(r"rejet|reject", (r["description"] or "") + " " + (r["amendment_subject"] or ""), _re.I)
        direction = "anti" if rejection else "pro"
        label = ("Motion to REJECT: " if rejection else "") + r["display_title"]
        VOTES[r["id"]] = (0.5, direction, label[:140]); REVIEWED[r["id"]] = False
        votes_meta[r["id"]] = r
        new_votes.append({"id": r["id"], "date": r["timestamp"][:10], "title": r["display_title"], "guess": direction,
                          "for": r["count_for"], "against": r["count_against"], "url": f"https://howtheyvote.eu/votes/{r['id']}"})
if new_votes:
    json.dump(new_votes, open(os.path.join(os.path.dirname(OUT) or ".", "eu_new_votes.json"), "w"), indent=1, ensure_ascii=False)
    print(f"NEW_EU_VOTES={len(new_votes)} (auto-classified, need review)")
missing = set(VOTES) - set(votes_meta)
if missing: sys.exit(f"votes not found: {missing}")
order = sorted(VOTES, key=lambda v: votes_meta[v]["timestamp"], reverse=True)
idx = {v: i for i, v in enumerate(order)}
pos = {m: {} for m in members}
for r in rd("member_votes"):
    if r["vote_id"] in VOTES and r["member_id"] in pos:
        pos[r["member_id"]][r["vote_id"]] = r["position"]

def ta_url(ref):  # P10_TA(2024)0003 -> official adopted text
    import re
    m = re.match(r"P(\d+)_TA\((\d{4})\)(\d{4})", ref or "")
    return f"https://www.europarl.europa.eu/doceo/document/TA-{m.group(1)}-{m.group(2)}-{m.group(3)}_EN.html" if m else None

def valence(direction, p):
    if p not in ("FOR", "AGAINST"): return 0
    return (1 if p == "FOR" else -1) * (1 if direction == "pro" else -1)

def raw_score(mid):
    d = u = n = 0
    for v, p in pos[mid].items():
        w, direction, _ = VOTES[v]; s = valence(direction, p)
        if s: d += s * w; u += w; n += 1
    return (d / u if u else None), n

raws = {m: raw_score(m) for m in members}
gp = {}
for m, (r, n) in raws.items():
    if r is not None: gp.setdefault(cur_group[m], []).append(r)
group_prior = {g: sum(v) / len(v) for g, v in gp.items()}

def tier(n): return "insufficient" if n < 2 else "low" if n < 3 else "moderate" if n < 8 else "full"
def label(s, low):
    if s is None: return "No record"
    if low: return "Limited record — some support" if s > .25 else "Limited record — some opposition" if s < -.25 else "Limited record"
    return ("Strong support" if s >= .75 else "Support" if s >= .35 else "Some support" if s >= .1 else "Mixed" if s > -.1
            else "Some opposition" if s > -.35 else "Opposed" if s > -.75 else "Strong opposition")

out_members = []
for mid, m in members.items():
    r, n = raws[mid]; g = cur_group[mid]; tr = tier(n); prior = group_prior.get(g)
    s = None if tr == "insufficient" else r
    if s is not None and prior is not None and tr != "full":
        y = 1 / (1 + n / 4); s = (1 - y) * r + y * prior
    code = {"FOR": "F", "AGAINST": "A", "ABSTENTION": "B", "DID_NOT_VOTE": "N"}
    np_id = cur_party.get(mid)
    out_members.append({
        "id": mid, "name": f'{m["first_name"]} {m["last_name"].title()}', "last": m["last_name"].title(), "country": m["country_code"],
        "group": g, "party": parties.get(np_id, ("", ""))[1] if np_id else "", "partyName": parties.get(np_id, ("", ""))[0] if np_id else "",
        "score": None if s is None else round(s, 3), "raw": None if r is None else round(r, 3), "n": n, "tier": tr,
        "label": label(s, tr == "low" and n > 0), "prior": None if prior is None else round(prior, 3),
        "votes": [[idx[v], valence(VOTES[v][1], p), code.get(p, "N")] for v, p in sorted(pos[mid].items(), key=lambda kv: idx[kv[0]])],
        "photo": f"https://www.europarl.europa.eu/mepphoto/{mid}.jpg", "web": f"https://www.europarl.europa.eu/meps/en/{mid}",
    })
votes_out = []
for v in order:
    r = votes_meta[v]; w, direction, short = VOTES[v]
    votes_out.append({"id": v, "label": short, "title": r["display_title"], "date": r["timestamp"][:10], "dir": direction, "weight": w,
                      "for": int(r["count_for"]), "against": int(r["count_against"]), "abst": int(r["count_abstention"]),
                      "htv": f"https://howtheyvote.eu/votes/{v}", "ta": ta_url(r["texts_adopted_reference"]), "ref": r["reference"],
                      "auto": not REVIEWED.get(v, True)})
json.dump({"generatedAt": datetime.now(timezone.utc).isoformat(timespec="minutes"),
           "dataAsOf": open(f"{RAW}/last_updated.txt").read().strip() if __import__("os").path.exists(f"{RAW}/last_updated.txt") else None,
           "groups": {k: {"name": v[0], "code": v[1], "prior": round(group_prior.get(k, 0), 3)} for k, v in GROUPS.items()},
           "countries": {k: {"name": v[0], "iso2": v[1]} for k, v in countries.items()},
           "votes": votes_out, "members": out_members}, open(OUT, "w"), separators=(",", ":"))
import collections
print(len(out_members), "MEPs")
for g in GROUPS:
    ms = [m for m in out_members if m["group"] == g]; sc = [m["score"] for m in ms if m["score"] is not None]
    print(f"{GROUPS[g][0]:28} {len(ms):4}  avg {sum(sc)/len(sc):+.2f}" if sc else g)
