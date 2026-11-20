"""120th Congress (from Jan 3, 2027): members-elect from Wikipedia, matched to the 119th data -> site/data120.json

Returning members keep their record and score. Newcomers have no voting record; they get Track Ukraine's
Instagram verdict when one of the collected cards is about them.
"""
import json, re, sys, time, urllib.parse, urllib.request
RAW = sys.argv[1] if len(sys.argv) > 1 else "raw"
SITE = sys.argv[2] if len(sys.argv) > 2 else "site"
UA = {"User-Agent": "congress-ukraine-map/1.0 (static research build)"}
def get(url):
    for i in range(6):
        try:
            time.sleep(1); return json.load(urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60))
        except urllib.error.HTTPError as e:
            if e.code != 429: raise
            time.sleep(10 * (i + 1))
def api(**p):
    p.update(format="json", formatversion=2, redirects=1)
    return get("https://en.wikipedia.org/w/api.php?" + urllib.parse.urlencode(p))

ABBR = {"Alabama":"AL","Alaska":"AK","Arizona":"AZ","Arkansas":"AR","California":"CA","Colorado":"CO","Connecticut":"CT","Delaware":"DE","Florida":"FL","Georgia":"GA","Hawaii":"HI","Idaho":"ID","Illinois":"IL","Indiana":"IN","Iowa":"IA","Kansas":"KS","Kentucky":"KY","Louisiana":"LA","Maine":"ME","Maryland":"MD","Massachusetts":"MA","Michigan":"MI","Minnesota":"MN","Mississippi":"MS","Missouri":"MO","Montana":"MT","Nebraska":"NE","Nevada":"NV","New Hampshire":"NH","New Jersey":"NJ","New Mexico":"NM","New York":"NY","North Carolina":"NC","North Dakota":"ND","Ohio":"OH","Oklahoma":"OK","Oregon":"OR","Pennsylvania":"PA","Rhode Island":"RI","South Carolina":"SC","South Dakota":"SD","Tennessee":"TN","Texas":"TX","Utah":"UT","Vermont":"VT","Virginia":"VA","Washington":"WA","West Virginia":"WV","Wisconsin":"WI","Wyoming":"WY"}
w = api(action="parse", page="120th United States Congress", prop="wikitext")["parse"]["wikitext"]
sen_part = w[w.index("=== Senate ===", w.index("== Members ==")):w.index("===Representatives===")]
rep_part = w[w.index("===Representatives==="):]
_nv = re.search(r"^=+\s*Non-voting", rep_part, re.M)
rep_part = rep_part[:_nv.start()] if _nv else rep_part
entries = []
def parse_line(line):
    m = re.search(r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]\s*\(([\w-]+)\)", line)
    if not m: return (None, None, None)
    party = {"DFL": "D", "D-NPL": "D"}.get(m.group(3), m.group(3)[0])
    return (m.group(1), m.group(2) or m.group(1), party)
state = None
for line in sen_part.splitlines():
    h = re.match(r"=+\s*\[\[List of United States senators from ([^|\]]+)", line)
    if h: state = ABBR.get(h.group(1)); continue
    if line.startswith(":") and state:
        cls = re.search(r"\}\}\s*(\d)\.", line)
        title, name, party = parse_line(line)
        if "outgoing" in line: note = "Elected governor; will resign, and the seat will be filled by appointment"
        else: note = None
        entries.append({"chamber": "Senate", "state": state, "district": None, "class": int(cls.group(1)) if cls else None, "note": note,
                        "title": title, "name": name, "party": party or "?"})
state = None
for line in rep_part.splitlines():
    h = re.match(r"=+\s*\[\[List of United States representatives from ([^|\]]+)", line)
    if h: state = ABBR.get(h.group(1)); continue
    if line.startswith(":") and state:
        d = re.search(r"\{\{ushr\|[^|]+\|(\w+)\|", line)
        title, name, party = parse_line(line)
        entries.append({"chamber": "House", "state": state, "district": None if not d or d.group(1) == "AL" else int(d.group(1)),
                        "title": title, "name": name, "party": party or "?"})
print("senate", sum(e["chamber"] == "Senate" for e in entries), "house", sum(e["chamber"] == "House" for e in entries))

# resolve redirects, bioguide IDs (returning/former members) and photos
titles = sorted({e["title"] for e in entries if e["title"]})
canon, thumb = {}, {}
for k in range(0, len(titles), 50):
    q = api(action="query", titles="|".join(titles[k:k + 50]), prop="pageimages", piprop="thumbnail", pithumbsize=200)["query"]
    norm = {n["from"]: n["to"] for n in q.get("normalized", [])}; red = {n["from"]: n["to"] for n in q.get("redirects", [])}
    for t in titles[k:k + 50]:
        t2 = norm.get(t, t); canon[t] = red.get(t2, t2)
    for p in q.get("pages", []):
        if "thumbnail" in p: thumb[p["title"]] = p["thumbnail"]["source"]
bio = {}
ct = sorted(set(canon.values()))
for k in range(0, len(ct), 150):
    vals = " ".join('"' + t.replace('"', '\\"') + '"@en' for t in ct[k:k + 150])
    sparql = f'SELECT ?t ?b WHERE {{ VALUES ?t {{ {vals} }} ?a schema:name ?t ; schema:isPartOf <https://en.wikipedia.org/> ; schema:about ?p . ?p wdt:P1157 ?b . }}'
    for row in get("https://query.wikidata.org/sparql?format=json&query=" + urllib.parse.quote(sparql))["results"]["bindings"]:
        bio[row["t"]["value"]] = row["b"]["value"]

d119 = json.load(open(f"{SITE}/data.json")); cur = {m["id"]: m for m in d119["members"]}
ig = json.load(open(f"{RAW}/instagram.json")) if __import__("os").path.exists(f"{RAW}/instagram.json") else []
verdicts = {}
for m in d119["members"]:
    for p in m.get("ig") or []: verdicts[p["url"]] = p.get("verdict")
# verdicts for posts not matched to a current member: recompute from build_data's classifier output if present
try:
    sys.path.insert(0, "scripts")
except Exception: pass
FULL = {v: k for k, v in ABBR.items()}
def ig_for(name, st, dist, chamber):
    out = []
    parts = name.replace(",", "").split(); first, last = parts[0].lower(), parts[-1].lower()
    for p in ig:
        c = p.get("caption") or ""; cl = c.lower()
        if last not in cl or first not in cl: continue
        dc = re.search(r"\[([A-Z]{2})-(\d{2})\]", c)
        if dc and not (chamber == "House" and dc.group(1) == st and int(dc.group(2)) == (dist or 0)): continue
        if not dc and FULL.get(st, "~") not in c and f"-{st})" not in c: continue
        out.append({"url": p["url"], "img": p.get("img"), "caption": c, "seen": p.get("firstSeen"), "verdict": p.get("verdict")})
    return out

members, slugs = [], set()
for e in entries:
    t = canon.get(e["title"]) if e["title"] else None
    bg = bio.get(t) if t else None
    if bg and bg in cur:
        m = dict(cur[bg]); m.update(party=e["party"] if e["party"] in "DRI" else m["party"], state=e["state"], chamber=e["chamber"],
                                     district=e["district"] if e["chamber"] == "House" else None, status="returning" if cur[bg]["chamber"] == e["chamber"] else "moved", note=e.get("note"))
        members.append(m); continue
    if not t:
        members.append({"id": f'tbd-{e["state"]}-{e["district"]}', "name": "Undecided", "first": "", "last": "Undecided", "party": "?", "state": e["state"],
                        "district": e["district"], "chamber": e["chamber"], "status": "tbd", "score": None, "label": "Race not called", "votes": [], "sponsor": [], "f": [], "n": 0})
        continue
    slug = "new-" + re.sub(r"[^a-z0-9]+", "-", t.lower()).strip("-")
    while slug in slugs: slug += "x"
    slugs.add(slug)
    igm = ig_for(e["name"], e["state"], e["district"], e["chamber"])
    parts = e["name"].split()
    members.append({"id": slug, "name": e["name"], "first": parts[0], "last": parts[-1], "party": e["party"], "state": e["state"],
                    "district": e["district"], "chamber": e["chamber"], "status": "former" if bg else "new", "bioguide": bg,
                    "score": None, "raw": None, "n": 0, "tier": "insufficient", "label": "New member — no record", "votes": [], "sponsor": [], "f": [],
                    "photo": thumb.get(t), "wiki": "https://en.wikipedia.org/wiki/" + urllib.parse.quote(t.replace(" ", "_")),
                    "ig": igm, "tu": next((x["verdict"] for x in igm if x["verdict"]), None), "comBills": []})
json.dump({"generatedAt": d119["generatedAt"], "source": "https://en.wikipedia.org/wiki/120th_United_States_Congress", "members": members},
          open(f"{SITE}/data120.json", "w"), separators=(",", ":"))
import collections
for ch in ("House", "Senate"):
    ms = [m for m in members if m["chamber"] == ch]
    print(ch, len(ms), collections.Counter(m["party"] for m in ms), collections.Counter(m["status"] for m in ms))
print("newcomers with TU card:", [(m["name"], m["tu"]) for m in members if m.get("status") in ("new", "former") and m.get("ig")])
