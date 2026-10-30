"""google.py: k4's Google sign-in, shared by k4-cal (Calendar) and k4-mail (Gmail).

One OAuth client of your own (~/.config/k4/google-client.json, a "Desktop app" client from the
Google Cloud Console), one refresh token per service in the Secret Service keyring (secret-tool),
the short-lived access token cached in $XDG_RUNTIME_DIR. Sign-in uses the browser with a loopback
redirect and PKCE.
"""
import base64, hashlib, http.server, json, os, secrets, subprocess, time
import urllib.error, urllib.parse, urllib.request

HOME = os.path.expanduser("~")
CLIENT = os.path.join(HOME, ".config/k4/google-client.json")
RUN = os.environ.get("XDG_RUNTIME_DIR") or "/tmp"


def _pi():
    import sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import k4host
    return k4host.pi_mode()


def client():
    with open(CLIENT) as f: c = json.load(f)
    return c.get("installed") or c.get("web") or c


def have_client():
    """The OAuth client: ~/.config/k4/google-client.json, else the newest client_secret*.json
    in Downloads (what the Cloud Console saves), copied there."""
    if os.path.exists(CLIENT): return True
    dl = os.path.join(HOME, "Downloads")
    try: found = [os.path.join(dl, n) for n in os.listdir(dl) if n.startswith("client_secret") and n.endswith(".json")]
    except OSError: found = []
    for f in sorted(found, key=os.path.getmtime, reverse=True):
        try:
            with open(f) as fh: c = json.load(fh)
        except (OSError, ValueError): continue
        if "client_id" in (c.get("installed") or c.get("web") or c):
            os.makedirs(os.path.dirname(CLIENT), exist_ok=True)
            fd = os.open(CLIENT, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(fd, "w") as out: json.dump(c, out)
            return True
    return False


def open_url(url):
    subprocess.Popen(["xdg-open", url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)


def _write_private(path, data):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f: json.dump(data, f)


class Account:
    """One service's sign-in: its scope, its keyring entry, its access-token cache, its API root.
    test_token: a callable returning a refresh token in tests (then the keyring is not asked)."""

    def __init__(self, name, scope, secret, cache, base, test_token=None):
        self.name, self.scope, self.secret, self.cache, self.base = name, scope, secret, cache, base
        self.test_token = test_token

    def refresh_token(self):
        if self.test_token: return self.test_token()
        try:
            r = subprocess.run(self._lookup(), capture_output=True, text=True, timeout=10)
            return r.stdout.strip() or None
        except (OSError, subprocess.SubprocessError): return None

    def access_token(self):
        try:
            with open(self.cache) as f: t = json.load(f)
            if t.get("expires", 0) > time.time() + 60: return t["token"]
        except (OSError, ValueError, KeyError): pass
        rt = self.refresh_token()
        if not rt: raise PermissionError("not connected")
        c = client()
        body = urllib.parse.urlencode({"client_id": c["client_id"], "client_secret": c.get("client_secret", ""),
                                       "refresh_token": rt, "grant_type": "refresh_token"}).encode()
        try:
            with urllib.request.urlopen(c.get("token_uri", "https://oauth2.googleapis.com/token"), body, timeout=15) as r:
                j = json.load(r)
        except urllib.error.HTTPError as e:
            if e.code in (400, 401): raise PermissionError("sign in again")  # revoked or expired grant
            raise
        _write_private(self.cache, {"token": j["access_token"], "expires": time.time() + j.get("expires_in", 3600)})
        return j["access_token"]

    def request(self, method, url, body=None, query=None, raw=None, ctype=None):
        """The API's answer as JSON (raw: bytes sent as they are, with ctype)."""
        if query: url += "?" + urllib.parse.urlencode(query, doseq=True)
        data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
        req = urllib.request.Request(url if url.startswith("http") else self.base + url, data=data, method=method)
        req.add_header("Authorization", "Bearer " + self.access_token())
        if data: req.add_header("Content-Type", ctype or "application/json")
        with urllib.request.urlopen(req, timeout=30) as r:
            out = r.read()
        return json.loads(out) if out else {}

    def sign_in(self):
        """The browser's consent page; True once the refresh token is in the keyring.
        Returns (ok, message)."""
        c = client()
        verifier = base64.urlsafe_b64encode(secrets.token_bytes(48)).rstrip(b"=").decode()
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
        state = secrets.token_urlsafe(16)
        got, name = {}, self.name

        class H(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                p = urllib.parse.urlparse(self.path)
                got.update({k: v[0] for k, v in urllib.parse.parse_qs(p.query).items()})
                ok = got.get("state") == state and "code" in got
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(("<p style='font:16px monospace'>%s</p>" % ("k4 is connected to %s. You can close this tab." % name if ok else "Sign-in did not finish. Try again from k4.")).encode())

            def log_message(self, *a): pass

        srv = http.server.HTTPServer(("127.0.0.1", 0), H)
        srv.timeout = 300
        redirect = "http://127.0.0.1:%d" % srv.server_address[1]
        open_url(c.get("auth_uri", "https://accounts.google.com/o/oauth2/auth") + "?" + urllib.parse.urlencode({
            "client_id": c["client_id"], "redirect_uri": redirect, "response_type": "code", "scope": self.scope,
            "access_type": "offline", "prompt": "consent", "state": state,
            "code_challenge": challenge, "code_challenge_method": "S256"}))
        srv.handle_request()
        srv.server_close()
        if got.get("state") != state or "code" not in got:
            return False, "the sign-in was cancelled or timed out"
        body = urllib.parse.urlencode({"code": got["code"], "client_id": c["client_id"], "client_secret": c.get("client_secret", ""),
                                       "redirect_uri": redirect, "grant_type": "authorization_code", "code_verifier": verifier}).encode()
        with urllib.request.urlopen(c.get("token_uri", "https://oauth2.googleapis.com/token"), body, timeout=20) as r:
            j = json.load(r)
        if "refresh_token" not in j:
            return False, "Google sent no refresh token"
        subprocess.run(self._store(), input=j["refresh_token"], text=True, check=True)
        _write_private(self.cache, {"token": j["access_token"], "expires": time.time() + j.get("expires_in", 3600)})
        return True, ""

    # the keyring (secret-tool), or on the Pi k4-secret's file store (kind google, named like the keyring item)
    def _lookup(self): return ["k4-secret", "lookup", "google", self.secret[-1]] if _pi() else ["secret-tool", "lookup", *self.secret]
    def _store(self): return ["k4-secret", "store", "google", self.secret[-1]] if _pi() else ["secret-tool", "store", "--label=k4 " + self.name, *self.secret]

    def sign_out(self):
        subprocess.run(["k4-secret", "clear", "google", self.secret[-1]] if _pi() else ["secret-tool", "clear", *self.secret], capture_output=True)
        try: os.remove(self.cache)
        except OSError: pass
