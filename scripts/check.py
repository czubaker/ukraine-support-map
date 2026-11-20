"""Refuse to publish a data update that looks broken (sources down, page layout changed, formula blowup)."""
import json, sys
NEW, OLD = sys.argv[1], sys.argv[2]
errors = []
def load(d, f):
    try: return json.load(open(f"{d}/{f}"))
    except Exception: return None
def check(cond, msg):
    if not cond: errors.append(msg)

us, us_old = load(NEW, "data.json"), load(OLD, "data.json")
check(us is not None, "data.json missing")
if us:
    ms = us["members"]; house = [m for m in ms if m["chamber"] == "House" and not m.get("nonVoting")]; sen = [m for m in ms if m["chamber"] == "Senate"]
    check(len(house) >= 420, f"only {len(house)} House members"); check(len(sen) >= 98, f"only {len(sen)} senators")
    check(len(us["votes"]) >= 50, f"only {len(us['votes'])} tracked roll calls")
    scored = sum(m["score"] is not None for m in ms) / len(ms)
    check(scored >= .8, f"only {scored:.0%} of members have a score")
    if us_old:
        old = {m["id"]: m for m in us_old["members"]}
        diffs = [abs(m["score"] - old[m["id"]]["score"]) for m in ms if m["id"] in old and m["score"] is not None and old[m["id"]]["score"] is not None]
        if diffs: check(sum(diffs) / len(diffs) < .25, f"scores moved by {sum(diffs)/len(diffs):.2f} on average since the last update")
        def fc(d):
            c = {}
            for m in d["members"]:
                for k in m.get("f", []): c[k] = c.get(k, 0) + 1
            return c
        new_f, old_f = fc(us), fc(us_old)
        for k, n in old_f.items():
            if n >= 5: check(n * .5 <= new_f.get(k, 0) <= n * 2, f"faction {k}: {n} -> {new_f.get(k, 0)} members")
u120 = load(NEW, "data120.json")
check(u120 is not None and len(u120["members"]) == 535, "120th Congress roster is not 435 + 100 seats")
eu, eu_old = load(NEW, "eu.json"), load(OLD, "eu.json")
check(eu is not None, "eu.json missing")
if eu:
    check(len(eu["members"]) >= 700, f"only {len(eu['members'])} MEPs"); check(len(eu["votes"]) >= 30, f"only {len(eu['votes'])} EU votes")
    scored = sum(m["score"] is not None for m in eu["members"]) / len(eu["members"])
    check(scored >= .9, f"only {scored:.0%} of MEPs have a score")
if errors:
    print("UPDATE REJECTED, site keeps the previous data:"); [print(" -", e) for e in errors]; sys.exit(1)
print("All checks passed.")
