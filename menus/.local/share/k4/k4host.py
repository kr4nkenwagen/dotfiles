"""k4host.py: where k4's background scripts run. On the desktop cards go to k4's notification daemon
(k4 --notify-ctl). On the Pi (~/.config/k4/host says "pi", or K4_HOST=pi) there is no display: cards
wait in ~/.local/state/k4/outbox.jsonl until the desktop's `k4-pi pull` posts them, and secrets come
from k4-secret's file store instead of the keyring.
"""
import json, os, subprocess, time

HOME = os.path.expanduser("~")
OUTBOX = os.environ.get("K4_OUTBOX") or os.path.join(HOME, ".local/state/k4/outbox.jsonl")
# the phone's copy (k4-hub /api/cards): numbered, the last 200; the outbox above is the desktop's and is emptied by it
CARDS = os.environ.get("K4_CARDS") or os.path.join(HOME, ".local/state/k4/cards.jsonl")
CARDS_KEEP = 200


def pi_mode():
    if os.environ.get("K4_HOST"): return os.environ["K4_HOST"] == "pi"
    try:
        with open(os.path.join(HOME, ".config/k4/host")) as f: return f.read().strip() == "pi"
    except OSError: return False


def post(line):
    """A card (k4 --notify-ctl's post line); on the Pi it waits in the outbox. Returns the card's id
    ("" on the Pi or when k4 isn't there)."""
    if pi_mode():
        os.makedirs(os.path.dirname(OUTBOX), exist_ok=True)
        with open(OUTBOX, "a") as f: f.write(json.dumps({"at": time.time(), "line": line}, ensure_ascii=False) + "\n")
        card(line)
        return ""
    try: return subprocess.run(["k4", "--notify-ctl", line], capture_output=True, text=True, timeout=5).stdout.strip()
    except (OSError, subprocess.TimeoutExpired): return ""


def card(line):
    """The phone's copy of a card: the next number, kept with the last CARDS_KEEP (one writer at a time)."""
    import fcntl
    os.makedirs(os.path.dirname(CARDS), exist_ok=True)
    with open(CARDS + ".lock", "w") as lk:
        fcntl.flock(lk, fcntl.LOCK_EX)
        rows = cards()
        rows.append({"seq": (rows[-1]["seq"] if rows else 0) + 1, "at": time.time(), "line": line})
        with open(CARDS + ".new", "w") as f:
            for r in rows[-CARDS_KEEP:]: f.write(json.dumps(r, ensure_ascii=False) + "\n")
        os.replace(CARDS + ".new", CARDS)


def cards(since=0):
    """The kept cards after SINCE, oldest first."""
    out = []
    try:
        with open(CARDS) as f:
            for l in f:
                try: r = json.loads(l)
                except ValueError: continue
                if r.get("seq", 0) > since: out.append(r)
    except OSError: pass
    return out


def parse(line):
    """A post line (post ID APP TITLE BODY URGENCY PROGRESS TIMEOUT TAG ICON QUOTE ACTIONS CMD [IMAGE]) as
    the phone shows it: app, title, body, urgency, tag and the buttons' keys and labels."""
    f = line.split("\t") + [""] * 14
    acts = [a.split(":", 1) for a in f[11].split(",") if ":" in a]
    return {"app": f[2], "title": f[3], "body": f[4], "urgency": f[5], "tag": f[8], "actions": [{"key": k, "label": l} for k, l in acts]}
