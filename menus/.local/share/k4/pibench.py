#!/usr/bin/env python3
"""pibench.py: which local model should the event finder use on this machine (k4-pi bench runs it on
the Pi). Each model reads the two invented test prompts from k4's tests/events (made by k4-pi bench),
with thinking on and off; it is scored on what the finder needs and timed.

  pibench.py DIR MODEL[,MODEL…]   DIR holds p1.txt (a first run) and p2.txt (a run where the invoice is paid)

Scores (7 points): the dentist on Thu 5 Nov 14:30, the bike ride Sat 31 Oct 10:00, the raid Fri 30 Oct
20:00, the invoice as a todo due Tue 10 Nov, the logs as a todo, nothing invented from the newsletter,
and in p2 the paid invoice ticked off (T3). The best is the most points, then the fastest.
"""
import json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import events as E


def score(p1, p2):
    ev, td = p1.get("events", []), p1.get("todos", [])
    has = lambda d, s: any(x.get("date") == d and (x.get("start") or "") == s for x in ev)
    pts = [has("2026-11-05", "14:30"), has("2026-10-31", "10:00"), has("2026-10-30", "20:00"),
           any(x.get("due") == "2026-11-10" for x in td), any("log" in str(x.get("title", "")).lower() for x in td),
           not any(x.get("item") == 2 for x in ev + td),
           any(str(x.get("todo", "")).upper() == "T3" for x in p2.get("done", []))]
    return sum(pts), "".join("✓" if p else "·" for p in pts)


def main():
    d, models = sys.argv[1], sys.argv[2].split(",")
    p1, p2 = (open(os.path.join(d, f)).read() for f in ("p1.txt", "p2.txt"))
    rows = []
    for m in models:
        for think in {"on": (True,), "off": (False,)}.get(os.environ.get("K4_BENCH_THINK", ""), (True, False)):
            E.MODEL, E.THINK = m, think
            t = time.time(); a1 = E.ask(p1) or {}; t1 = time.time() - t
            t = time.time(); a2 = E.ask(p2) or {}; t2 = time.time() - t
            pts, marks = score(a1, a2)
            rows.append((pts, -(t1 + t2), m, think))
            print("%-18s think %-3s  %d/7 %s  first run %4.0f s · next run %4.0f s" % (m, "on" if think else "off", pts, marks, t1, t2), flush=True)
    best = max(rows)
    print("best\t%s\t%s" % (best[2], "1" if best[3] else "0"))


if __name__ == "__main__":
    main()
