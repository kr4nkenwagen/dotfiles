"""k4host.py: where k4's background scripts run. On the desktop cards go to k4's notification daemon
(k4 --notify-ctl). On the Pi (~/.config/k4/host says "pi", or K4_HOST=pi) there is no display: cards
wait in ~/.local/state/k4/outbox.jsonl until the desktop's `k4-pi pull` posts them, and secrets come
from k4-secret's file store instead of the keyring.
"""
import json, os, subprocess, time

HOME = os.path.expanduser("~")
OUTBOX = os.environ.get("K4_OUTBOX") or os.path.join(HOME, ".local/state/k4/outbox.jsonl")


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
        return ""
    try: return subprocess.run(["k4", "--notify-ctl", line], capture_output=True, text=True, timeout=5).stdout.strip()
    except (OSError, subprocess.TimeoutExpired): return ""
