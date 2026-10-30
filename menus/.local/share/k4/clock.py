#!/usr/bin/env python3
"""k4's Clock (k4-clock is its front): world clocks, timers, alarms, a stopwatch.

State lives in ~/.local/state/k4/clock/state.json (K4_CLOCK_STATE: another folder). A running
timer and an alarm that is on each get a transient systemd user timer (k4-clock-*), so they ring
with no window open; `resync` makes them again (after a change, and at login). Ringing: a card
that stays (Stop, +1 min or Snooze), a sound that grows louder over 30 s (an alarm stops by
itself after 10 min), and the bar's clock in yellow or red (bar.tsv, read by k4 --bar).

  clock.py data                    the window's lines (k4 --clock, see src/clock.odin)
  clock.py act VERB …              timer add SECS [LABEL] | timer toggle|remove ID | timer plus ID ±SECS
                                   alarm add H M DAYS [LABEL] | alarm toggle|remove ID
                                   city add NAME | city remove NAME | watch toggle|lap|reset
                                   stop | snooze | more | undo | copy TEXT | event HH
  clock.py fire timer|alarm ID     a systemd timer went off
  clock.py note KEY ID             a card's button: stop, more, snooze, open (default)
  clock.py click left|right        the bar clock: stops or snoozes what rings, else what the click is for
  clock.py timer 10m tea | alarm 7:30 weekdays gym
  clock.py find | resync | sound

Tests: K4_CLOCK_FAKE=DIR (no systemd, sound or cards: they go to DIR/fake.log), K4_CLOCK_NOW.
"""
import datetime as dt, json, os, re, shutil, signal, subprocess, sys, time, zoneinfo

HOME = os.path.expanduser("~")
STATE = os.environ.get("K4_CLOCK_STATE") or os.path.join(HOME, ".local/state/k4/clock")
FAKE = os.environ.get("K4_CLOCK_FAKE")
FRONT = os.environ.get("K4_CLOCK_FRONT") or shutil.which("k4-clock") or "k4-clock"
SOUND = "/usr/share/sounds/freedesktop/stereo/alarm-clock-elapsed.oga"
SNOOZE = 9 * 60
ALARM_RINGS = 10 * 60    # an alarm stops by itself after this
TIMER_RINGS = 3 * 60     # a timer's sound stops; its card and the bar stay until stopped
DEFAULT_CITIES = ["London", "New York", "San Francisco", "Tokyo", "Sydney"]
# names people type for a zone that is called after another city
ALIASES = {"San Francisco": "America/Los_Angeles", "Seattle": "America/Los_Angeles", "Washington": "America/New_York",
           "Boston": "America/New_York", "Miami": "America/New_York", "Atlanta": "America/New_York", "Dallas": "America/Chicago",
           "Houston": "America/Chicago", "Beijing": "Asia/Shanghai", "Mumbai": "Asia/Kolkata", "Delhi": "Asia/Kolkata",
           "Bangalore": "Asia/Kolkata", "Osaka": "Asia/Tokyo", "Munich": "Europe/Berlin", "Frankfurt": "Europe/Berlin",
           "Hamburg": "Europe/Berlin", "Gothenburg": "Europe/Stockholm", "Malmö": "Europe/Stockholm", "Uppsala": "Europe/Stockholm",
           "Barcelona": "Europe/Madrid", "Milan": "Europe/Rome", "Geneva": "Europe/Zurich", "Montreal": "America/Toronto",
           "Melbourne": "Australia/Melbourne", "Auckland": "Pacific/Auckland", "Hong Kong": "Asia/Hong_Kong", "Seoul": "Asia/Seoul",
           "Rio de Janeiro": "America/Sao_Paulo", "Edinburgh": "Europe/London", "Manchester": "Europe/London"}
SHORT = {"United States": "USA", "United Kingdom (UK)": "United Kingdom", "Britain (UK)": "United Kingdom",
         "Korea (South)": "South Korea", "Russia": "Russia", "United Arab Emirates": "UAE"}
WD = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
MON = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def say(*a): print(*a, flush=True)
def field(s): return re.sub(r"[\t\n\r]+", " ", str(s or "")).strip()
def now(): return float(os.environ.get("K4_CLOCK_NOW") or time.time())
def local(t): return dt.datetime.fromtimestamp(t).astimezone()
def hm(t): return local(t).strftime("%H:%M")


def dur(s):
    s = max(0, int(round(s)))
    h, m, x = s // 3600, s // 60 % 60, s % 60
    return "%d:%02d:%02d" % (h, m, x) if h else "%d:%02d" % (m, x)


def in_words(s):
    s = max(0, int(s))
    d, h, m = s // 86400, s // 3600 % 24, s // 60 % 60
    if d: return "in %d d %d h" % (d, h)
    return "in " + ("%d h " % h if h else "") + "%d min" % m


def log(what):
    with open(os.path.join(FAKE, "fake.log"), "a") as f: f.write(what + "\n")


# ---------- the state ----------

def load():
    try:
        with open(os.path.join(STATE, "state.json")) as f: s = json.load(f)
    except (OSError, ValueError): s = {}
    s.setdefault("cities", [{"name": n} for n in DEFAULT_CITIES])
    s.setdefault("timers", []); s.setdefault("alarms", [])
    s.setdefault("watch", {"run": False, "t0": 0, "base": 0, "laps": []})
    s.setdefault("ringing", None); s.setdefault("undo", None); s.setdefault("next_id", 1)
    return s


def save(s):
    os.makedirs(STATE, exist_ok=True)
    p = os.path.join(STATE, "state.json")
    with open(p + ".tmp", "w") as f: json.dump(s, f, indent=1)
    os.replace(p + ".tmp", p)
    bar_file(s)


def new_id(s):
    i = s["next_id"]; s["next_id"] = i + 1
    return i


def find(lst, ident):
    for x in lst:
        if str(x["id"]) == str(ident): return x
    return None


# ---------- places ----------

def home_tz():
    tz = os.environ.get("TZ", "").lstrip(":")
    if not tz:
        try: tz = os.path.realpath("/etc/localtime").split("zoneinfo/", 1)[1]
        except IndexError: tz = "UTC"
    return tz


def countries():
    names, zones = {}, {}
    try:
        with open("/usr/share/zoneinfo/iso3166.tab") as f:
            for l in f:
                if l.startswith("#") or "\t" not in l: continue
                c, n = l.rstrip("\n").split("\t", 1); names[c] = SHORT.get(n, n)
        for tab in ("zone.tab", "zone1970.tab"):
            with open("/usr/share/zoneinfo/" + tab) as f:
                for l in f:
                    if l.startswith("#"): continue
                    p = l.rstrip("\n").split("\t")
                    if len(p) >= 3 and p[2] not in zones: zones[p[2]] = names.get(p[0].split(",")[0], "")
    except OSError: pass
    return zones


def places():
    """Every city k4 knows: {name: (tz, country)} from the zones, and the ALIASES."""
    zc = countries()
    out = {}
    for tz in sorted(zoneinfo.available_timezones()):
        if "/" not in tz or tz.startswith(("Etc/", "SystemV/", "US/", "Brazil/", "Canada/", "Mexico/", "Chile/")): continue
        out.setdefault(tz.rsplit("/", 1)[1].replace("_", " "), (tz, zc.get(tz, "")))
    for n, tz in ALIASES.items(): out[n] = (tz, zc.get(tz, ""))
    return out


def offset(tz, t):
    return int(dt.datetime.fromtimestamp(t, zoneinfo.ZoneInfo(tz)).utcoffset().total_seconds())


def abbr(tz, t):
    a = dt.datetime.fromtimestamp(t, zoneinfo.ZoneInfo(tz)).tzname() or ""
    return a if a.isalpha() else ""


def rel(sec):
    if sec == 0: return "same time"
    h = abs(sec) / 3600
    return "%s%s h" % ("+" if sec > 0 else "−", ("%g" % h))


def dst_note(tz, home, t):
    """"goes to −6 h on Sun 1 Nov" when the difference to home changes within two weeks."""
    d0 = offset(tz, t) - offset(home, t)
    for h in range(1, 14 * 24):
        x = t + h * 3600
        d = offset(tz, x) - offset(home, x)
        if d != d0:
            day = local(x)
            return "goes to %s on %s %d %s" % (rel(d), WD[day.weekday()], day.day, MON[day.month - 1])
    return ""


# ---------- alarms ----------

def alarm_next(a, t):
    """The next time an alarm rings (local time), its snooze first; 0 when off."""
    if not a.get("on"): return 0
    days = a.get("days") or "0000000"
    base = local(t).replace(second=0, microsecond=0)
    for d in range(0, 8):
        day = base + dt.timedelta(days=d)
        at = day.replace(hour=int(a["h"]), minute=int(a["m"]))
        at = dt.datetime(at.year, at.month, at.day, at.hour, at.minute).astimezone()   # (DST: the wall clock time)
        if at.timestamp() <= t: continue
        if "1" in days and days[at.weekday()] != "1": continue
        n = at.timestamp()
        break
    else: n = 0
    sn = a.get("snooze") or 0
    return min(n, sn) if sn > t else n


def rep_of(days):
    return {"1111111": "every day", "1111100": "weekdays", "0000011": "weekends", "0000000": "once"}.get(days, "some days")


# ---------- scheduling ----------

def units():
    if FAKE: return []
    r = subprocess.run(["systemctl", "--user", "list-units", "k4-clock-*", "--all", "--plain", "--no-legend"], capture_output=True, text=True)
    return [l.split()[0] for l in r.stdout.splitlines() if l.strip()]


def resync(s=None):
    """A systemd user timer for each running timer and each alarm that is on (they ring with no window)."""
    s = s or load()
    t = now()
    want = {}
    for x in s["timers"]:
        if x.get("end") and not x.get("done"): want["k4-clock-timer-%s" % x["id"]] = ("timer", x["id"], x["end"])
    for a in s["alarms"]:
        n = alarm_next(a, t)
        if n: want["k4-clock-alarm-%s" % a["id"]] = ("alarm", a["id"], n)
    if FAKE:
        with open(os.path.join(FAKE, "schedule"), "w") as f:
            for u, (k, i, at) in sorted(want.items()): f.write("%s %s\n" % (u, local(at).strftime("%a %H:%M:%S")))
        return
    have = set(u.rsplit(".", 1)[0] for u in units())
    for u in have: subprocess.run(["systemctl", "--user", "stop", u + ".timer", u + ".service"], capture_output=True)
    subprocess.run(["systemctl", "--user", "reset-failed", "k4-clock-*"], capture_output=True)
    for u, (k, i, at) in want.items():
        when = local(at).strftime("%Y-%m-%d %H:%M:%S")
        subprocess.run(["systemd-run", "--user", "--quiet", "--collect", "--unit=" + u, "--on-calendar=" + when,
                        "--timer-property=AccuracySec=1s", FRONT, "fire", k, str(i)], capture_output=True)


# ---------- ringing ----------

def post(title, body, acts, urgency, ident=0):
    if FAKE: log("post %s | %s | %s" % (title, body, acts)); return 0
    line = "\t".join(["post", str(ident), "Clock", field(title), field(body), urgency, "-1", "0", "RINGING", "", "", acts, FRONT + " note"])
    r = subprocess.run(["k4", "--notify-ctl", line], capture_output=True, text=True, timeout=5)
    try: return int(r.stdout.strip() or 0)
    except ValueError: return 0


def unpost(card):
    if FAKE: log("close card"); return
    if card: subprocess.run(["k4", "--notify-ctl", "close %d" % card], capture_output=True, timeout=5)


def sound_stop():
    p = os.path.join(STATE, "sound.pid")
    try:
        with open(p) as f: pid = int(f.read().strip())
        os.killpg(pid, signal.SIGTERM)
    except (OSError, ValueError): pass
    try: os.remove(p)
    except OSError: pass


def sound_start():
    if FAKE: log("sound"); return
    sound_stop()
    p = subprocess.Popen([FRONT, "sound"], start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    with open(os.path.join(STATE, "sound.pid"), "w") as f: f.write(str(p.pid))


def sound():
    """The ring: louder over 30 s, until what rings is stopped (an alarm: 10 min at most)."""
    s = load(); r = s["ringing"]
    if not r: return
    t0 = time.time()
    limit = ALARM_RINGS if r["kind"] == "alarm" else TIMER_RINGS
    play = shutil.which("pw-play") or shutil.which("paplay")
    while play and os.path.exists(SOUND):
        el = time.time() - t0
        if el > limit: break
        cur = load()["ringing"]
        if not cur or cur.get("since") != r.get("since"): return
        vol = min(1.0, 0.25 + el / 40)
        subprocess.run([play, "--volume=%.2f" % vol, SOUND], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(0.4)
    if r["kind"] == "alarm":   # (an alarm stops by itself)
        cur = load()
        if cur["ringing"] and cur["ringing"].get("since") == r.get("since"): stop(cur, quiet=True)


def fire(kind, ident):
    s = load(); t = now()
    if kind == "timer":
        x = find(s["timers"], ident)
        if not x or not x.get("end") or x.get("done") or x["end"] > t + 2: return resync(s)
        x["done"], x["left"], x["end"] = x["end"], 0, 0
        label = x.get("label") or "%s timer" % dur(x["total"])
        others = [y for y in s["timers"] if y is not x and y.get("end") and not y.get("done")]
        body = "%s timer · rang at %s." % (dur(x["total"]), hm(t))
        if others: body += " %s has %s left." % (others[0].get("label") or "Another timer", dur(others[0]["end"] - t))
        s["ringing"] = {"kind": "timer", "id": x["id"], "label": label, "since": t}
        s["ringing"]["card"] = post("%s · done" % label, body, "stop:Stop,more:+1 min,open:Open Clock", "warn")
    else:
        a = find(s["alarms"], ident)
        if not a or not a.get("on"): return resync(s)
        a["snooze"] = 0
        if (a.get("days") or "0000000") == "0000000": a["on"] = False   # (once: off once it rang)
        label = a.get("label") or "Alarm"
        sub = "%s · louder over 30 s, stops by itself after 10 min." % rep_of(a.get("days") or "0000000").capitalize()
        s["ringing"] = {"kind": "alarm", "id": a["id"], "label": label, "since": t, "at": "%02d:%02d" % (a["h"], a["m"])}
        s["ringing"]["card"] = post("%02d:%02d · %s" % (a["h"], a["m"], label), sub, "snooze:Snooze 9 min,stop:Stop", "wait")
    save(s); resync(s); sound_start()


def stop(s=None, quiet=False):
    s = s or load(); r = s["ringing"]
    if not r: return say("Nothing is ringing") if not quiet else None
    s["ringing"] = None
    if r["kind"] == "timer":
        s["timers"] = [x for x in s["timers"] if str(x["id"]) != str(r["id"])]
        msg = "“%s” cleared" % r["label"]
    else:
        nxt = sorted((alarm_next(a, now()), a) for a in s["alarms"] if alarm_next(a, now()))
        msg = "Alarm stopped" + (" · next: %s %s" % (hm(nxt[0][0]), nxt[0][1].get("label") or "") if nxt else "")
    save(s); resync(s); sound_stop(); unpost(r.get("card"))
    if not quiet: say(msg.strip())


def snooze():
    s = load(); r = s["ringing"]
    if not r or r["kind"] != "alarm": return say("No alarm is ringing")
    a = find(s["alarms"], r["id"])
    until = now() + SNOOZE
    if a: a["snooze"], a["on"] = until, True
    s["ringing"] = None
    save(s); resync(s); sound_stop(); unpost(r.get("card"))
    say("Snoozed until %s" % hm(until))


def more():
    """+1 min on the timer that is done."""
    s = load(); r = s["ringing"]
    if not r or r["kind"] != "timer": return say("No timer is done")
    x = find(s["timers"], r["id"])
    if x: x.update(total=60, end=now() + 60, left=0, done=0)
    s["ringing"] = None
    save(s); resync(s); sound_stop(); unpost(r.get("card"))
    say("+1 min")


# ---------- what you do ----------

def cap(s): return s[:1].upper() + s[1:] if s else s


def act(argv):
    s = load(); t = now()
    v, rest = (argv[0] if argv else ""), argv[1:]
    sub = rest[0] if rest else ""
    if v == "timer" and sub == "add":
        secs = int(float(rest[1])); label = cap(" ".join(rest[2:]).strip())
        if secs <= 0: return say("Type a length, like 10m")
        s["timers"].insert(0, {"id": new_id(s), "label": label, "total": secs, "end": t + secs, "left": 0, "done": 0})
        save(s); resync(s)
        say("Started %s%s · ends %s" % (dur(secs), " · " + label if label else "", hm(t + secs)))
    elif v == "timer" and sub in ("toggle", "remove", "plus"):
        x = find(s["timers"], rest[1] if len(rest) > 1 else "")
        if not x: return say("No such timer")
        if sub == "remove":
            s["timers"].remove(x); s["undo"] = {"kind": "timer", "item": x}
            if s["ringing"] and str(s["ringing"]["id"]) == str(x["id"]) and s["ringing"]["kind"] == "timer":
                unpost(s["ringing"].get("card")); s["ringing"] = None; sound_stop()
            save(s); resync(s); say("Timer removed · ^Z undo"); say("k4:tone yellow"); return
        if x.get("done"): return say("It is done · Esc stops it")
        if sub == "plus":
            d = int(rest[2]) if len(rest) > 2 else 60
            if x.get("end"): x["end"] = max(t + 1, x["end"] + d)
            else: x["left"] = max(1, x["left"] + d)
            if d > 0: x["total"] += d
            save(s); resync(s); say("%s1 min" % ("+" if d > 0 else "−")); return
        if x.get("end"): x["left"], x["end"] = max(1, x["end"] - t), 0; msg = "Paused · %s left" % dur(x["left"])
        else: x["end"], x["left"] = t + x["left"], 0; msg = "Running · ends %s" % hm(x["end"])
        save(s); resync(s); say(msg)
    elif v == "alarm" and sub == "add":
        h, m, days = int(rest[1]), int(rest[2]), rest[3] if len(rest) > 3 else "0000000"
        if not (0 <= h < 24 and 0 <= m < 60): return say("Type a time, like 7:30")
        a = {"id": new_id(s), "h": h, "m": m, "days": days, "on": True, "label": cap(" ".join(rest[4:]).strip()), "snooze": 0}
        s["alarms"].append(a); s["alarms"].sort(key=lambda x: x["h"] * 60 + x["m"])
        save(s); resync(s); say("Alarm set · %s" % in_words(alarm_next(a, t) - t))
    elif v == "alarm" and sub in ("toggle", "remove"):
        a = find(s["alarms"], rest[1] if len(rest) > 1 else "")
        if not a: return say("No such alarm")
        if sub == "remove":
            s["alarms"].remove(a); s["undo"] = {"kind": "alarm", "item": a}
            save(s); resync(s); say("Alarm deleted · ^Z undo"); say("k4:tone yellow"); return
        a["on"], a["snooze"] = not a.get("on"), 0
        save(s); resync(s)
        if a["on"]: say("On · rings %s" % in_words(alarm_next(a, t) - t))
        else: say("Off"); say("k4:tone yellow")
    elif v == "city" and sub == "add":
        name = " ".join(rest[1:]).strip()
        p = places(); hit = next((n for n in p if n.lower() == name.lower()), None) or next((n for n in sorted(p) if n.lower().startswith(name.lower())), None)
        if not hit: return say("No city called “%s”" % name)
        if any(c["name"] == hit for c in s["cities"]) or p[hit][0] == home_tz() and hit == home_name(): return say("%s is there already" % hit)
        s["cities"].append({"name": hit}); save(s); say("Added %s" % hit)
    elif v == "city" and sub == "remove":
        name = " ".join(rest[1:]).strip()
        n = len(s["cities"]); s["cities"] = [c for c in s["cities"] if c["name"] != name]
        if len(s["cities"]) == n: return say("%s can’t be removed" % name)
        s["undo"] = {"kind": "city", "item": {"name": name}}
        save(s); say("%s removed" % name); say("k4:tone yellow")
    elif v == "watch":
        w = s["watch"]
        el = w["base"] + (t - w["t0"] if w["run"] else 0)
        if sub == "toggle":
            if w["run"]: w.update(run=False, base=el); msg = "Stopped at %s" % sw_text(el)
            else: w.update(run=True, t0=t); msg = ""
        elif sub == "lap":
            if not w["run"]: return say("Start it first · Space")
            w["laps"].append(round(el - sum(w["laps"]), 2)); msg = "Lap %d" % len(w["laps"])
        else: w.update(run=False, t0=0, base=0, laps=[]); msg = "Reset"
        save(s)
        if msg: say(msg)
    elif v == "stop": stop(s)
    elif v == "snooze": snooze()
    elif v == "more": more()
    elif v == "undo":
        u = s["undo"]
        if not u: return say("Nothing to undo")
        {"timer": s["timers"], "alarm": s["alarms"], "city": s["cities"]}[u["kind"]].append(u["item"])
        s["alarms"].sort(key=lambda x: x["h"] * 60 + x["m"])
        s["undo"] = None; save(s); resync(s); say("Put back")
    elif v == "copy":
        text = " ".join(rest)
        if FAKE: log("copy " + text)
        else: subprocess.run(["wl-copy"], input=text, text=True)
        say("Copied “%s”" % text)
    elif v == "event":   # a calendar event at that hour today (or tomorrow when it has passed)
        h = int(sub or 0) % 24
        day = local(t).replace(hour=h, minute=0, second=0, microsecond=0)
        if day.timestamp() <= t: day += dt.timedelta(days=1)
        if FAKE: log("event %s" % day.strftime("%Y-%m-%d %H:%M"))
        else: subprocess.run(["k4-cal", "add", "primary", day.strftime("%Y-%m-%d"), day.strftime("%H:%M"), "New event"], capture_output=True, timeout=20)
        say("New event at %02d:00 · in Calendar" % h)
    else: say("k4-clock act: unknown %s" % v)


def parse_dur(q):
    """"10m", "1h30 bread", "90s eggs", "4:30", "25" (minutes) → (seconds, label) or None."""
    t = q.strip().lower()
    s, hit = 0.0, False
    for pat, mul in ((r"(\d+(?:\.\d+)?)\s*h(?:ours?)?(?![a-z])", 3600), (r"(\d+)\s*m(?:in(?:utes?)?)?(?![a-z])", 60), (r"(\d+)\s*s(?:ec(?:onds?)?)?(?![a-z])", 1)):
        m = re.search(pat, t)
        if m: s += float(m.group(1)) * mul; hit = True; t = t.replace(m.group(0), " ", 1)
    if hit and re.match(r"^\s*(\d+)\b", t) and s >= 3600 and s % 3600 == 0:   # "1h30": the minutes after the hours
        m = re.match(r"^\s*(\d+)\b", t); s += int(m.group(1)) * 60; t = t.replace(m.group(0), " ", 1)
    if not hit:
        m = re.match(r"^(\d+):(\d\d)\b", t) or re.match(r"^(\d+)\b", t)
        if m: s = int(m.group(1)) * 60 + (int(m.group(2)) if m.lastindex == 2 else 0); hit = True; t = t.replace(m.group(0), " ", 1)
    if not hit or s <= 0: return None
    return int(s), re.sub(r"\s+", " ", t.replace("timer", " ")).strip()


def parse_alarm(q):
    """"7:30", "6:45 weekdays gym", "9 weekends" → (h, m, days, label) or None."""
    t = q.strip().lower()
    m = re.match(r"^(\d{1,2})(?:[:.]?(\d{2}))?\b", t)
    if not m: return None
    h, mi = int(m.group(1)), int(m.group(2) or 0)
    if h > 23 or mi > 59: return None
    rest, days = t[m.end():], "0000000"
    for pat, d in ((r"weekdays?", "1111100"), (r"weekends?", "0000011"), (r"daily|every ?day", "1111111")):
        if re.search(pat, rest): days = d; rest = re.sub(pat, " ", rest, count=1); break
    return h, mi, days, re.sub(r"\s+", " ", rest).strip()


def quick(kind, text):
    if kind == "timer":
        p = parse_dur(text)
        if not p: return say("Type a length, like 10m")
        act(["timer", "add", str(p[0])] + ([p[1]] if p[1] else []))
    else:
        p = parse_alarm(text)
        if not p: return say("Type a time, like 7:30")
        act(["alarm", "add", str(p[0]), str(p[1]), p[2]] + ([p[3]] if p[3] else []))


def home_name():
    return home_tz().rsplit("/", 1)[-1].replace("_", " ")


def sw_text(el):
    m, x = int(el // 60), el % 60
    return "%02d:%02d:%02d.%02d" % (m // 60, m % 60, int(x), int((x % 1) * 100))


# ---------- what the window, the bar and the launcher read ----------

def data():
    s = load(); t = now(); home = home_tz()
    p = places()
    loc = local(t)
    say("N\t%.3f\t%s\t%s\t%s\t%d" % (t, home_name(), loc.strftime("%Z"), loc.strftime("%V"), offset(home, t)))
    zc = countries()
    hc = zc.get(home, "")
    say("C\t%s\t%s\t%d\t1\t\t%s" % (home_name(), hc, offset(home, t), home))
    for c in s["cities"]:
        if c["name"] not in p: continue
        tz, country = p[c["name"]]
        a = abbr(tz, t)
        lab = country + (" · " + a if a and country in ("USA", "Australia", "Canada", "Mexico", "Brazil") else "")
        say("C\t%s\t%s\t%d\t0\t%s\t%s" % (c["name"], lab, offset(tz, t), dst_note(tz, home, t), tz))
    have = {c["name"] for c in s["cities"]} | {home_name()}
    for n in sorted(p):
        if n not in have: say("Z\t%s\t%s\t%d" % (n, p[n][1], offset(p[n][0], t)))
    for x in s["timers"]:
        say("T\t%s\t%s\t%d\t%.1f\t%.1f\t%.1f" % (x["id"], field(x.get("label")), x["total"], x.get("end") or 0, x.get("left") or 0, x.get("done") or 0))
    for a in s["alarms"]:
        say("A\t%s\t%d\t%d\t%s\t%d\t%s\t%d" % (a["id"], a["h"], a["m"], a.get("days") or "0000000", 1 if a.get("on") else 0, field(a.get("label")), alarm_next(a, t)))
    w = s["watch"]
    say("W\t%d\t%.2f\t%.2f\t%s" % (1 if w["run"] else 0, w["t0"], w["base"], ",".join("%.2f" % l for l in w["laps"])))
    r = s["ringing"]
    if r: say("G\t%s\t%s\t%s\t%.1f\t%s" % (r["kind"], r["id"], field(r["label"]), r["since"], r.get("at", "")))
    if s["undo"]: say("U\t%s" % s["undo"]["kind"])
    say("R\t%s act" % FRONT)
    say("L\t%s data" % FRONT)


def bar_file(s):
    """What the bar's clock shows instead of the date (k4 --bar, clock flag timers=PATH)."""
    t = now(); lines = []
    r = s["ringing"]
    if r: lines.append("ring\t%s\t%s" % (r["kind"], field(r["label"])))
    run = sorted((x for x in s["timers"] if x.get("end") and not x.get("done")), key=lambda x: x["end"])
    if run: lines.append("timer\t%d\t%s\t%d" % (run[0]["end"], field(run[0].get("label")), len(run) - 1))
    w = s["watch"]
    if w["run"]: lines.append("watch\t%.2f\t%.2f" % (w["t0"], w["base"]))
    nxt = sorted(alarm_next(a, t) for a in s["alarms"] if alarm_next(a, t))
    if nxt: lines.append("alarm\t%d\t%s" % (nxt[0], hm(nxt[0])))
    p = os.path.join(STATE, "bar.tsv")
    with open(p + ".tmp", "w") as f: f.write("\n".join(lines) + ("\n" if lines else ""))
    os.replace(p + ".tmp", p)


def find_rows():
    """The launcher's rows (k4's A records): a city's time (↵ adds it to Clock), and the Clock's tabs."""
    import base64, shlex
    b64 = lambda x: base64.b64encode(x.encode()).decode()
    def row(label, action, meta, flags):
        print("A\t%s\t%s\t%s\t\t%s" % (b64("k4-clock run " + b64(action)), field(label), field(meta), flags))
    t = now(); home = home_tz(); ho = offset(home, t)
    today = local(t).date()
    me = shlex.quote(FRONT)
    for n, (tz, country) in sorted(places().items()):
        lt = dt.datetime.fromtimestamp(t, zoneinfo.ZoneInfo(tz))
        day = "today" if lt.date() == today else ("tomorrow" if lt.date() > today else "yesterday")
        row("%s · %s" % (n, lt.strftime("%H:%M")), "%s act city add %s" % (me, shlex.quote(n)), "%s · %s · ↵ adds it to Clock" % (rel(offset(tz, t) - ho), day),
            "search;words;min=3;rank=60;tag=Clock;icon=󰥔" + (";find=" + country.replace(";", ",") if country else ""))
    for label, tab, meta, find in (("Open Clock", "", "world, timers, alarms, stopwatch · right click the bar clock", "clock"),
                                   ("Clock › Timers", "timers", "“timer 10m tea” starts one from here", "timer"),
                                   ("Clock › Alarms", "alarms", "“alarm 7:30” sets one from here", "alarm"),
                                   ("Clock › Stopwatch", "watch", "Space starts it", "stopwatch")):
        row(label, "bg %s window %s" % (me, tab), meta, "search;words;min=3;rank=%d;tag=Clock;icon=󰥔;find=%s" % (80 if not tab else 70, find))
    sys.stdout.flush()


def main(argv):
    cmd = argv[1] if len(argv) > 1 else ""
    if cmd == "data": data()
    elif cmd == "act": act(argv[2:])
    elif cmd == "fire": fire(argv[2], argv[3])
    elif cmd == "note":
        k = argv[2] if len(argv) > 2 else ""
        if k == "stop": stop()
        elif k == "more": more()
        elif k == "snooze": snooze()
        else: subprocess.Popen(["setsid", "-f", FRONT, "window"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    elif cmd == "ringing":
        r = load()["ringing"]; say(r["kind"] if r else "")
    elif cmd in ("timer", "alarm"): quick(cmd, " ".join(argv[2:]))
    elif cmd == "find": find_rows()
    elif cmd == "resync": s = load(); save(s); resync(s)
    elif cmd == "sound": sound()
    else: say(__doc__.strip()); return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
