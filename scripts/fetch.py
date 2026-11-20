"""Snapshot Track Ukraine tracker data (vote.cogs.it.com) into raw/."""
import json, os, sys, time, urllib.request, concurrent.futures as cf
BASE = "https://vote.cogs.it.com/api"
OUT = sys.argv[1] if len(sys.argv) > 1 else "raw"
HDR = {"Origin": "https://trackukraine.com", "Referer": "https://trackukraine.com/pages/search", "User-Agent": "Mozilla/5.0"}
STATES = "AL AK AZ AR CA CO CT DE FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY DC AS GU MP PR VI".split()
def get(path):
    for i in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(BASE + path, headers=HDR), timeout=30) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 404: return None
            time.sleep(2 * (i + 1))
        except Exception:
            time.sleep(2 * (i + 1))
    print("FAILED", path, file=sys.stderr); return None
os.makedirs(OUT, exist_ok=True)
bills = get("/bills")
json.dump(bills, open(f"{OUT}/bills.json", "w"))
with cf.ThreadPoolExecutor(4) as ex:
    states = dict(zip(STATES, ex.map(lambda s: get(f"/state-members/{s}"), STATES)))
json.dump(states, open(f"{OUT}/states.json", "w"))
ids = sorted({m["bioguideId"] for s in states.values() if s for m in s["house"] + s["senators"]})
print("members", len(ids))
with cf.ThreadPoolExecutor(4) as ex:
    bundles = dict(zip(ids, ex.map(lambda i: get(f"/rep-bundle/{i}"), ids)))
json.dump(bundles, open(f"{OUT}/bundles.json", "w"))
votes = sorted({(v["chamber"], v["congress"], v["session"], v["rollCall"]) for b in bills["bills"] for v in b.get("votes", [])})
print("rollcalls", len(votes))
def roster(v):
    c, g, s, r = v
    return f"{c}|{g}|{s}|{r}", get(f"/roll-call-rosters/{'house' if c == 'House' else 'senate'}/{g}/{s}/{r}")
with cf.ThreadPoolExecutor(4) as ex:
    rosters = dict(ex.map(roster, votes))
json.dump(rosters, open(f"{OUT}/rosters.json", "w"))
print("done", sum(1 for x in bundles.values() if x), "bundles,", sum(1 for x in rosters.values() if x), "rosters")

# --- Track Ukraine's Instagram feed (homepage shows the latest 25); accumulate across runs ---
import re, html as _html
try:
    req = urllib.request.Request("https://trackukraine.com/", headers={"User-Agent": "Mozilla/5.0", "Accept-Encoding": "identity"})
    page = urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "replace")
    path = f"{OUT}/instagram.json"
    known = {p["url"]: p for p in (json.load(open(path)) if os.path.exists(path) else [])}
    seen = time.strftime("%Y-%m-%d")
    for m in re.finditer(r'href="(https://www\.instagram\.com/(?:p|reel)/[^"]+)".*?<img\s+src="([^"]+)"\s+alt="(.*?)"', page, re.S):
        url, img, alt = m.group(1), m.group(2), _html.unescape(m.group(3))
        known.setdefault(url, {"url": url, "firstSeen": seen})
        known[url].update(img=img, caption=alt)
    json.dump(sorted(known.values(), key=lambda p: p["firstSeen"], reverse=True), open(path, "w"), indent=1)
    print("instagram posts", len(known))
except Exception as e:
    print("instagram feed failed:", e, file=sys.stderr)

# --- download card images so build_data can read the verdict color ---
try:
    os.makedirs(f"{OUT}/igimg", exist_ok=True)
    for p in json.load(open(f"{OUT}/instagram.json")):
        code = p["url"].rstrip("/").split("/")[-1]
        dest = f"{OUT}/igimg/{code}.jpg"
        if os.path.exists(dest) or not p.get("img"): continue
        r = urllib.request.Request(p["img"], headers={"User-Agent": "Mozilla/5.0", "Referer": "https://trackukraine.com/"})
        open(dest, "wb").write(urllib.request.urlopen(r, timeout=30).read())
except Exception as e:
    print("card image download failed:", e, file=sys.stderr)

# --- rosters for corrected votes, straight from the House Clerk ---
try:
    import re as _re
    corr = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "corrections.json")))
    extra = {}
    for c in corr.values():
        for v in c["votes"]:
            if v["chamber"] != "House": continue
            x = urllib.request.urlopen(urllib.request.Request(v["url"], headers={"User-Agent": "Mozilla/5.0"}), timeout=30).read().decode()
            casts = dict(_re.findall(r'name-id="(\w+)"[^>]*>[^<]*</legislator>\s*<vote>([^<]+)</vote>', x))
            extra[f'House|{v["congress"]}|{v["session"]}|{v["rollCall"]}'] = {"chamber": "house", "casts": casts}
    json.dump(extra, open(f"{OUT}/rosters_extra.json", "w"))
    print("corrected rosters", len(extra))
except Exception as e:
    print("corrected rosters failed:", e, file=sys.stderr)
