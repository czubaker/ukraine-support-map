"""Compute Track Ukraine scores the same way their widget does; write site/data.json."""
import json, sys
RAW = sys.argv[1] if len(sys.argv) > 1 else "raw"
OUT = sys.argv[2] if len(sys.argv) > 2 else "site/data.json"
bills = json.load(open(f"{RAW}/bills.json"))["bills"]
states = json.load(open(f"{RAW}/states.json"))
bundles = json.load(open(f"{RAW}/bundles.json"))
rosters = json.load(open(f"{RAW}/rosters.json"))
NONVOTING = {"DC", "AS", "GU", "MP", "PR", "VI"}
KA = {"sponsor-pro": 1, "voted-pro": 1, "unstated": 0, "voted-anti": -1, "sponsor-anti": -1}
OL = {"sponsor-pro": 1.5, "sponsor-anti": 1.5, "voted-pro": 1, "voted-anti": 1, "unstated": 0}
def bid(c, t, n): return f"{c}-{t.upper()}-{n}"
import os as _os
_cp = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "corrections.json")
corrections = json.load(open(_cp)) if _os.path.exists(_cp) else {}
if _os.path.exists(f"{RAW}/rosters_extra.json"): rosters.update(json.load(open(f"{RAW}/rosters_extra.json")))
for b in bills:
    c = corrections.get(bid(b["congress"], b["type"], b["number"]))
    if c: b["votes"] = c["votes"]; b["correction"] = c["note"]
curated = {bid(b["congress"], b["type"], b["number"]): b for b in bills}
def tier(n): return "insufficient" if n < 2 else "low" if n < 3 else "moderate" if n < 8 else "full"
def score(items, prior):
    d = u = n = 0
    for val, w in items:
        h, t = KA[val], OL[val]
        if h == 0 or t == 0 or w <= 0: continue
        d += h * t * w; u += t * w; n += 1
    raw = None if u == 0 else d / u
    tr = tier(n)
    if tr == "insufficient": return None, raw, n, tr
    s = raw
    if raw is not None and prior is not None and tr != "full":
        y = 1 / (1 + n / 4); s = (1 - y) * raw + y * prior
    return s, raw, n, tr
def label(s, low):
    if s is None: return "No record"
    if low: return "Limited record — some support" if s > .25 else "Limited record — some opposition" if s < -.25 else "Limited record"
    return ("Strong support" if s >= .75 else "Support" if s >= .35 else "Some support" if s >= .1 else "Mixed" if s > -.1
            else "Some opposition" if s > -.35 else "Opposed" if s > -.75 else "Strong opposition")
def cast_norm(c): return {"Yea": "Aye", "Aye": "Aye", "Nay": "Nay", "No": "Nay", "Present": "Present"}.get(c, "Not Voting")
def vote_val(direction, cast):
    if cast in ("Present", "Not Voting") or direction == "neutral": return "unstated"
    pro = direction == "pro"
    return ("voted-pro" if pro else "voted-anti") if cast == "Aye" else ("voted-anti" if pro else "voted-pro")
def sponsor_val(direction):
    if direction == "neutral": return "unstated"
    return "sponsor-pro" if direction == "pro-ukraine" else "sponsor-anti"
import re, os
def rollcall_html(u):
    if not u: return None
    m = re.match(r"https://clerk\.house\.gov/evs/(\d{4})/roll(\d+)\.xml", u)
    if m: return f"https://clerk.house.gov/Votes/{m.group(1)}{int(m.group(2)):03d}"
    return u[:-4] + ".htm" if u.endswith(".xml") else u
# Instagram rating cards from Track Ukraine's feed
ig = json.load(open(f"{RAW}/instagram.json")) if os.path.exists(f"{RAW}/instagram.json") else []
ORD = {"1st":1,"2nd":2,"3rd":3}
def ig_matches(m):
    out = []
    handle = ((m.get("socials") or {}).get("instagram") or "").lower()
    for p in ig:
        c = p.get("caption") or ""; cl = c.lower()
        if m["last"].lower() not in cl and not (handle and "@" + handle in cl): continue
        ok = (handle and "@" + handle in cl) or (m["first"].lower() in cl)
        dc = re.search(r"\[([A-Z]{2})-(\d{2})\]", c)
        if dc: ok = ok and dc.group(1) == m["state"] and m["chamber"] == "House" and int(dc.group(2)) == (m.get("district") or 0) or (ok and dc.group(1) == m["state"] and not m.get("district"))
        elif m["state"] not in c and (STATE_FULL.get(m["state"], "~") not in c) and not (handle and "@" + handle in cl): ok = False
        if ok: out.append({"url": p["url"], "img": p.get("img"), "caption": c, "seen": p.get("firstSeen"), "verdict": p.get("verdict")})
    return out
STATE_FULL = {"AL":"Alabama","AK":"Alaska","AZ":"Arizona","AR":"Arkansas","CA":"California","CO":"Colorado","CT":"Connecticut","DE":"Delaware","FL":"Florida","GA":"Georgia","HI":"Hawaii","ID":"Idaho","IL":"Illinois","IN":"Indiana","IA":"Iowa","KS":"Kansas","KY":"Kentucky","LA":"Louisiana","ME":"Maine","MD":"Maryland","MA":"Massachusetts","MI":"Michigan","MN":"Minnesota","MS":"Mississippi","MO":"Missouri","MT":"Montana","NE":"Nebraska","NV":"Nevada","NH":"New Hampshire","NJ":"New Jersey","NM":"New Mexico","NY":"New York","NC":"North Carolina","ND":"North Dakota","OH":"Ohio","OK":"Oklahoma","OR":"Oregon","PA":"Pennsylvania","RI":"Rhode Island","SC":"South Carolina","SD":"South Dakota","TN":"Tennessee","TX":"Texas","UT":"Utah","VT":"Vermont","VA":"Virginia","WA":"Washington","WV":"West Virginia","WI":"Wisconsin","WY":"Wyoming"}
bill_comments = {}
factions = json.load(open(f"{RAW}/factions.json")) if os.path.exists(f"{RAW}/factions.json") else {}
faction_of = {}
for k, v in factions.items():
    for i in v["members"]: faction_of.setdefault(i, []).append(k)
# Verdict = color of the card's header band (green supports / yellow unclear / red opposes / blue).
try:
    from PIL import Image
    import colorsys
except ImportError:
    Image = None
    print("Pillow missing: run with .venv/bin/python to read card colors", file=sys.stderr)
def card_verdict(url):
    if Image is None or "/p/" not in url: return None  # reels are video thumbnails, not rating cards
    path = f"{RAW}/igimg/{url.rstrip('/').split('/')[-1]}.jpg"
    if not os.path.exists(path): return None
    im = Image.open(path).convert("RGB").resize((100, 125))
    px = [im.getpixel((x, y)) for x in range(100) for y in range(2, 24)]
    cnt = {"red": 0, "yellow": 0, "green": 0, "blue": 0}
    for r, g, b in px:
        h, s_, v = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
        if s_ < .45 or v < .45: continue
        h *= 360
        k = "red" if h < 20 or h >= 330 else "yellow" if h < 70 else "green" if h < 170 else "blue" if h < 260 else None
        if k: cnt[k] += 1
    k = max(cnt, key=cnt.get)
    return k if cnt[k] / len(px) > .5 else None
for p in ig: p["verdict"] = card_verdict(p["url"])
# vote index for the front end
vote_list = []
for b in bills:
    for v in b.get("votes", []):
        vote_list.append((b, v))
vote_list.sort(key=lambda bv: bv[1]["date"], reverse=True)
votes_out = [{"bill": bid(b["congress"], b["type"], b["number"]), "label": b.get("label") or b.get("shortTitle") or b.get("title"),
              "chamber": v["chamber"], "date": v["date"][:10], "dir": v["direction"], "weight": v["weight"], "kind": v.get("kind"),
              "featured": bool(b.get("featured")), "law": bool(b.get("becameLaw")), "url": b.get("congressGovUrl"),
              "rc": rollcall_html(v.get("url")), "rcNo": v["rollCall"], "action": v.get("action"),
              "why": b.get("directionReason"), "fix": b.get("correction")} for b, v in vote_list]
members = []
for st, s in states.items():
    if not s: continue
    for m in s["house"] + s["senators"]:
        bnd = bundles.get(m["bioguideId"]) or {}
        mem = bnd.get("member") or {}
        prior = mem.get("partyPrior")
        items, bill_set, mv = [], set(), []
        for i, (b, v) in enumerate(vote_list):
            if v["chamber"] != m["chamber"]: continue
            r = rosters.get(f'{v["chamber"]}|{v["congress"]}|{v["session"]}|{v["rollCall"]}')
            if not r: continue
            if r.get("chamber", "").lower() == "house" or isinstance(r.get("casts"), dict):
                raw = r["casts"].get(m["bioguideId"])
            else:
                hit = [c for c in r["casts"] if c["lastName"] == m["last"] and c["state"] == m["state"]]
                raw = hit[0]["cast"] if hit else None
            if raw is None: continue
            cast = cast_norm(raw)
            val = vote_val(v["direction"], cast)
            items.append((val, v["weight"]))
            bill_set.add(bid(b["congress"], b["type"], b["number"]))
            mv.append([i, {"voted-pro": 1, "voted-anti": -1}.get(val, 0), cast[0]])
        sp = []
        for rel, w in (("sponsored", 1.0), ("cosponsored", 0.75)):
            for x in mem.get(rel) or []:
                k = bid(x["congress"], x["type"], x["number"])
                if k not in curated: continue
                val = sponsor_val(curated[k]["direction"])
                items.append((val, w)); bill_set.add(k)
                sp.append([k, rel[0], {"sponsor-pro": 1, "sponsor-anti": -1}.get(val, 0)])
        ncom = 0; com_bills = []
        for k in sorted(bill_set):
            cs = ((bnd.get("comments") or {}).get(k) or {}).get("comments", [])
            if cs:
                bill_comments[k] = [{"text": c.get("bodyMarkdown", ""), "dir": c.get("direction"), "w": c.get("weight"), "date": (c.get("createdAt") or "")[:10]} for c in cs]
                com_bills.append(k)
            for c in cs:
                if c.get("weight", 0) > 0 and c.get("direction") in (1, -1):
                    items.append(("voted-pro" if c["direction"] == 1 else "voted-anti", c["weight"])); ncom += 1
        for key in ("socialPosts", "quotes"):
            for c in (bnd.get(key) or []):
                if isinstance(c, dict) and c.get("weight", 0) > 0 and c.get("direction") in (1, -1):
                    items.append(("voted-pro" if c["direction"] == 1 else "voted-anti", c["weight"]))
        sc, raw, n, tr = score(items, prior)
        j = bnd.get("judgement")
        nonvoting = m["chamber"] == "House" and st in NONVOTING
        members.append({
            "id": m["bioguideId"], "name": m["officialName"], "first": m["first"], "last": m["last"],
            "party": m["party"], "state": st, "district": m.get("district"), "chamber": m["chamber"],
            "nonVoting": nonvoting, "since": m.get("yearEntered"), "photo": m.get("photoUrl"), "web": m.get("website"),
            "score": None if sc is None else round(sc, 3), "raw": None if raw is None else round(raw, 3),
            "n": n, "tier": tr, "label": label(sc, tr == "low" and n > 0), "prior": None if prior is None else round(prior, 3),
            "judgement": {"rating": j.get("rating"), "img": j.get("imageUrl")} if isinstance(j, dict) else None,
            "ig": (igm := ig_matches(m)), "tu": next((x["verdict"] for x in igm if x["verdict"]), None), "comBills": com_bills, "f": faction_of.get(m["bioguideId"], []),
            "votes": mv, "sponsor": sp, "comments": ncom,
        })
from datetime import datetime, timezone
bill_info = {k: {"label": b.get("label") or b.get("title"), "url": b.get("congressGovUrl"), "dir": b.get("direction")} for k, b in curated.items()}
json.dump({"generatedAt": datetime.now(timezone.utc).isoformat(timespec="minutes"), "votes": votes_out, "members": members,
           "bills": bill_info, "factionSrc": {k: v["url"] for k, v in factions.items()}, "comments": bill_comments, "igCount": len(ig)},
          open(OUT, "w"), separators=(",", ":"))
import collections
print({m["name"]: m["tu"] for m in members if m["ig"]}); print(len(members), "members;", sum(1 for m in members if m["ig"]), "with Instagram cards:", [m["name"] for m in members if m["ig"]])
for ch in ("House", "Senate"):
    print(ch, collections.Counter(x["label"] for x in members if x["chamber"] == ch).most_common())
