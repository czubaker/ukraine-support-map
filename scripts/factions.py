"""Faction/caucus membership from Wikipedia, matched to members via Wikidata bioguide IDs -> raw/factions.json"""
import json, sys, urllib.request, urllib.parse
RAW = sys.argv[1] if len(sys.argv) > 1 else "raw"
UA = {"User-Agent": "congress-ukraine-map/1.0 (static research build)"}
# key: (wikipedia page, section title to read, sub-sections included)
FACTIONS = {
  "dsa":   ("List of Democratic Socialists of America public officeholders", "Current (2)", "United States House of Representatives"),
  "squad": ("Squad (United States Congress)", "Current members"),
  "cpc":   ("Congressional Progressive Caucus", "Membership"),
  "newdem":("New Democrat Coalition", "Current members"),
  "bluedog":("Blue Dog Coalition", "Current members"),
  "psc":   ("Problem Solvers Caucus", "Current members"),
  "rgg":   ("Republican Governance Group", "Current members"),
  "msc":   ("Main Street Caucus", "Membership"),
  "rsc":   ("Republican Study Committee", "Current members"),
  "hfc":   ("Freedom Caucus", "Current members"),
}
import time
def get(url):
    for i in range(6):
        try:
            time.sleep(1.2)
            return json.load(urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60))
        except urllib.error.HTTPError as e:
            if e.code != 429: raise
            time.sleep(10 * (i + 1))
    raise RuntimeError("rate limited: " + url)
def api(**p):
    p.update(format="json", formatversion=2, redirects=1)
    return get("https://en.wikipedia.org/w/api.php?" + urllib.parse.urlencode(p))
def section_links(page, title, parent=None):
    secs = api(action="parse", page=page, prop="sections")["parse"]["sections"]
    lo = 0
    if parent:  # e.g. the first "Current (N)" under "United States House of Representatives"
        lo = next(i for i, s in enumerate(secs) if s["line"].strip().lower() == parent.lower())
    start = next((i for i, s in enumerate(secs) if i >= lo and (s["line"].strip().lower() == title.lower() or (title.lower().startswith("current (") and s["line"].lower().startswith("current (")))), None)
    if start is None: raise RuntimeError(f"section {title!r} not found on {page}")
    lvl = int(secs[start]["level"]); idx = [secs[start]["index"]]
    for s in secs[start + 1:]:
        if int(s["level"]) <= lvl: break
        # stop at "former"/"suggested"/"no longer" subsections
        if any(w in s["line"].lower() for w in ("former", "suggested", "no longer", "past", "previous", "not yet", "electoral results")): continue
        idx.append(s["index"])
    print("   sections read:", [s["line"] for s in secs if s["index"] in idx], file=sys.stderr)
    links = set()
    for i in idx:
        html = api(action="parse", page=page, prop="text", section=i)["parse"]["text"]
        # drop nested former-member subsections already excluded; gather article links
        import re
        for m in re.finditer(r'<a href="/wiki/([^"#?]+)"', html):
            links.add(urllib.parse.unquote(m.group(1)).replace("_", " "))
    return links
ids = sorted({m["bioguideId"] for s in json.load(open(f"{RAW}/states.json")).values() if s for m in s["house"] + s["senators"]})
title_to_id = {}
for k in range(0, len(ids), 200):
    vals = " ".join(f'"{i}"' for i in ids[k:k + 200])
    q = f'SELECT ?b ?t WHERE {{ VALUES ?b {{ {vals} }} ?p wdt:P1157 ?b . ?a schema:about ?p ; schema:isPartOf <https://en.wikipedia.org/> ; schema:name ?t . }}'
    for row in get("https://query.wikidata.org/sparql?format=json&query=" + urllib.parse.quote(q))["results"]["bindings"]:
        title_to_id[row["t"]["value"]] = row["b"]["value"]
print("wikidata titles", len(title_to_id), "of", len(ids))
# resolve redirects for linked titles
def resolve(titles):
    out = {}; titles = list(titles)
    for k in range(0, len(titles), 50):
        r = api(action="query", titles="|".join(titles[k:k + 50]))["query"]
        norm = {n["from"]: n["to"] for n in r.get("normalized", [])}
        red = {n["from"]: n["to"] for n in r.get("redirects", [])}
        for t in titles[k:k + 50]:
            t2 = norm.get(t, t); out[t] = red.get(t2, t2)
    return out
import os
prev = json.load(open(f"{RAW}/factions.json")) if os.path.exists(f"{RAW}/factions.json") else {}
result = dict(prev)  # a faction that fails to load keeps its previous member list
PARTY_OF = {"dsa": "D", "squad": "D", "cpc": "DI", "newdem": "D", "bluedog": "D", "rgg": "R", "msc": "R", "rsc": "R", "hfc": "R", "psc": "DRI"}
party = {m["bioguideId"]: m["party"] for s in json.load(open(f"{RAW}/states.json")).values() if s for m in s["house"] + s["senators"]}
for key, (page, sec, *par) in FACTIONS.items():
    try:
        links = section_links(page, sec, par[0] if par else None)
        res = resolve(links)
        members = sorted({title_to_id[res[t]] for t in links if res[t] in title_to_id and party.get(title_to_id[res[t]], "") in PARTY_OF[key]})
        result[key] = {"page": page, "url": "https://en.wikipedia.org/wiki/" + urllib.parse.quote(page.replace(" ", "_")), "members": members}
        print(f"{key:8} {len(members):4}  ({page} / {sec})")
    except Exception as e:
        print(key, "FAILED", e, file=sys.stderr)
json.dump(result, open(f"{RAW}/factions.json", "w"), indent=1)
