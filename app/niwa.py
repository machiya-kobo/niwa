"""Niwa (庭): the private digital garden grown from the vault, on the web, gemini and gopher.
Part of Machiya (machiya-kobo/machiya).

Standalone: Niwa keeps its own read-write clone of the vault (ssh deploy key), commits only the garden's fields
and events as `garden` (vaultkit.GitSync: batched, rebased, pushed), and keeps its link-rot table in NIWA_DB.
Optional: Konbini (column badges, "in bloom", the board half of the stream), Kura (owner links to every note),
Hister (private link copies, the stream's reading line).

Listeners: web (NIWA_PORT; owner gate on Tailscale-User-Login, or Machiya's identity file and its grants), gemini 1965,
gopher 7070. /api/status is open (monitoring).
"""
import ipaddress
import json
import os
import re
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, quote, unquote, urlsplit

# Native installs (BSD, no container): settings may come from an env file (--env-file PATH or
# NIWA_ENV_FILE; the real environment wins). Loaded before anything reads a setting (vaultkit.shell does on import).
from vaultkit import envfile
ENV_FILE = envfile.load_for("niwa")

import feed  # noqa: E402
import gmodern  # noqa: E402
import links as linkrot  # noqa: E402
import shell  # noqa: E402
import smallweb  # noqa: E402
import stream  # noqa: E402
from garden import Garden  # noqa: E402
from hister import Hister  # noqa: E402
from konbini import Konbini  # noqa: E402
from state import EVENTS_DIR, State  # noqa: E402
from vaultkit import GitSync  # noqa: E402
from vaultkit import borrow as vk_borrow  # noqa: E402
from vaultkit import changelog  # noqa: E402
from vaultkit import verify as vk_verify  # noqa: E402
from vaultkit import EditError  # noqa: E402
from vaultkit import identity  # noqa: E402
from vaultkit import read_secret  # noqa: E402
from vaultkit import signin  # noqa: E402
from writer import Writer, WriteError  # noqa: E402

VERSION = "0.4.8"
PORT = int(os.environ.get("NIWA_PORT", "8080"))
USERS = set(filter(None, (u.strip() for u in os.environ.get("NIWA_USERS", "").split(","))))


def auth_mode(value, identity_file=""):
    """NIWA_AUTH: "tailscale" (the default: Tailscale-User-Login must be in NIWA_USERS, or in the identity file),
    "open" (no identity check, for localhost or a trusted LAN), or with an identity file "header" (a trusted proxy's
    login header, NIWA_AUTH_HEADER). Anything else refuses to start rather than guess."""
    value = (value or "tailscale").strip().lower()
    allowed = ("tailscale", "open", "header") if identity_file else ("tailscale", "open")
    if value not in allowed:
        raise SystemExit("niwa: NIWA_AUTH must be %s, not %r" % (" or ".join(allowed), value))
    return value


def archive_mode(value):
    """NIWA_ARCHIVE: "wayback" asks the Wayback Machine for snapshots (it sends each link's URL to archive.org); "none"
    (the default) never contacts it. Links are still checked for life, and snapshots already recorded still show.
    Any other value counts as none, with a warning."""
    value = (value or "").strip().lower()
    if value not in ("", "none", "wayback"):
        print("niwa: WARNING: NIWA_ARCHIVE=%r is neither wayback nor none; treating it as none" % value, flush=True)
    return "wayback" if value == "wayback" else "none"


def flag(value):
    """A yes/no setting: 1, on or true is yes; anything else, or unset, is no."""
    return (value or "").strip().lower() in ("1", "on", "true")


def host_name(value):
    """A host as Host or a setting may write it, reduced to its name: lowercase, no port, no brackets around an IPv6
    address, no trailing dot. "" when it isn't one."""
    try:
        return (urlsplit("//" + (value or "").strip()).hostname or "").rstrip(".")
    except ValueError:
        return ""


def public_url(value):
    """NIWA_PUBLIC_URL: Niwa's web address, an origin only (http(s), a host, maybe a port) with no path, like
    https://niwa.example. It says whether the web is served over https (the session cookie's Secure, and which pages
    the sign-in takes as same-origin) and is the origin the sign-in accepts. "" when unset; anything else refuses to
    start."""
    value = (value or "").strip().rstrip("/")
    if not value:
        return ""
    u = urlsplit(value)
    try:
        u.port                                                     # a malformed port raises
        ok = u.scheme in ("http", "https") and bool(u.hostname) and not (u.path or u.query or u.fragment)
    except ValueError:
        ok = False
    if not ok or "@" in u.netloc:
        raise SystemExit("niwa: NIWA_PUBLIC_URL must be an origin with no path, like https://niwa.example, not %r"
                         % value)
    return value


def allowed_hosts(host, setting, public=""):
    """The names NIWA_AUTH=open serves: localhost, NIWA_HOST, NIWA_PUBLIC_URL's host and NIWA_ALLOWED_HOSTS
    (comma-separated)."""
    names = {"localhost", host_name(host), (urlsplit(public).hostname or "").rstrip(".") if public else ""}
    return names - {""} | {host_name(h) for h in (setting or "").split(",")} - {""}


def host_allowed(host_header, allowed):
    """NIWA_AUTH=open's guard against DNS rebinding: a page on another site whose name is pointed at this machine
    arrives with that site's name in Host (and Origin), so only an IP literal, localhost or a listed name is served."""
    host = host_name(host_header)
    if not host:
        return False
    try:
        ipaddress.ip_address(host)
        return True
    except ValueError:
        return host in allowed


CREDENTIALS_RE = re.compile(r"(\w+://)[^/?#\s]*@")     # to the last @ of the authority: a password may hold one


def redact(text):
    """A URL's user:password@ (an https remote with a token) never reaches a log line or /api/status."""
    return CREDENTIALS_RE.sub(r"\1***@", text) if isinstance(text, str) else text


MAX_BODY = 1 << 20     # form posts and suggestions are small
MAX_DRAIN = 16 << 20   # an oversized body is read and dropped up to this, so its 413 isn't lost to a reset
AUTH = auth_mode(os.environ.get("NIWA_AUTH"), os.environ.get("MACHIYA_IDENTITY_FILE", "").strip())
# The address every listener binds (web, gemini, gopher). A native install behind `tailscale serve` binds 127.0.0.1:
# on a public bind the Tailscale-User-Login header could be sent by anyone who reaches the port.
BIND = os.environ.get("NIWA_BIND", "0.0.0.0").strip() or "0.0.0.0"
# Niwa's web address (an origin). Served over plain http (http://...), the session cookie isn't Secure and the sign-in
# accepts only this origin; unset means https, as before.
PUBLIC_URL = public_url(os.environ.get("NIWA_PUBLIC_URL"))
SECURE = urlsplit(PUBLIC_URL).scheme != "http"            # unset or https: Secure cookies, https pages only
try:        # Machiya's identity file (MACHIYA_IDENTITY_FILE); None without one: the NIWA_USERS gate, as before
    IDENTITY = identity.load_for("niwa", os.environ, bind=BIND, secure=SECURE)
except identity.IdentityError as err:
    raise SystemExit("niwa: identity: %s" % err)
NO_STORE = ("Cache-Control", "no-store")
REPO_URL = os.environ.get("NIWA_REPO_URL", "").strip()
REPO = os.environ.get("NIWA_REPO_DIR", "/data/repo")
SUBDIR = os.environ.get("NIWA_REPO_SUBDIR", "").strip("/")      # "" = the notes are at the repo root
# In the Machiya stack, borrow the stack's vault copy (vault-mirror) objects instead of keeping a second history, and
# optionally check out only what Niwa reads and writes. Empty = standalone: a full clone of our own.
REFERENCE = os.environ.get("NIWA_REPO_REFERENCE", "").strip()
SPARSE = [p.strip().strip("/") for p in os.environ.get("NIWA_REPO_SPARSE", "").split(",") if p.strip().strip("/")]
POLL = max(10, int(os.environ.get("NIWA_POLL", "60")))
DB = os.environ.get("NIWA_DB", "/data/niwa.sqlite3")
HOST = os.environ.get("NIWA_HOST", "").strip()           # the name in the gemini cert and gopher menus; "" = localhost, no footer links
# NIWA_AUTH=open serves only these names in Host (plus any IP literal): localhost, NIWA_HOST, NIWA_PUBLIC_URL's host and
# NIWA_ALLOWED_HOSTS.
ALLOWED_HOSTS = allowed_hosts(HOST, os.environ.get("NIWA_ALLOWED_HOSTS"), PUBLIC_URL)
SMALLWEB_HOST = HOST or "localhost"
PRIVATE = tuple(p.strip().strip("/") + "/" for p in os.environ.get("NIWA_PRIVATE_FOLDERS", "").split(",") if p.strip().strip("/"))
AUTHOR = (os.environ.get("NIWA_GIT_NAME", "garden"), os.environ.get("NIWA_GIT_EMAIL", "garden@niwa"))
DATA_DIR = os.path.dirname(DB) or "."
# Per-user preferences (GET/PUT /api/prefs, with an identity file): their own SQLite file next to NIWA_DB, made (0600)
# on first use.
PREFS_DB = os.path.join(DATA_DIR, "prefs.sqlite3")
# The origins the sign-in, sign-out and a prefs PUT made with a cookie accept as same-origin: NIWA_PUBLIC_URL. Without
# it the request's own Host counts, over https only; over plain http the sign-in then always refuses (vaultkit.signin).
ORIGINS = (PUBLIC_URL,) if PUBLIC_URL else ()
# Before the gate (they are how you get past it), each with vaultkit.signin's body limit.
SHARED_UI = ("/static/machiya.css", "/static/machiya.js", "/static/machiya-sw.js")   # vaultkit's, before the gate
SIGNIN_LIMITS = {"/signin": signin.MAX_FORM, "/signout": signin.MAX_FORM, "/api/pair": signin.MAX_PAIR}
_prefs, _prefs_lock = None, threading.Lock()


def prefs_store():
    """vaultkit.signin.Prefs on PREFS_DB, opened once."""
    global _prefs
    with _prefs_lock:
        if _prefs is None:
            _prefs = signin.Prefs(PREFS_DB)
        return _prefs


IMAGE_TYPES = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".gif": "image/gif",
               ".webp": "image/webp", ".svg": "image/svg+xml"}
STATIC_TYPES = {"niwa.css": "text/css", "niwa.js": "text/javascript", "mermaid.min.js": "text/javascript",
                "machiya.css": "text/css", "machiya.js": "text/javascript",       # machiya.*: the vendored shared UI
                "machiya-sw.js": "text/javascript"}
NO_STORE_DIRS = ("Archive/",)          # never kept on a device: their pages are Cache-Control: no-store

shell.GARDEN_HOST = HOST
def server_url(api, public):
    """The address Niwa's server calls Konbini on: NIWA_KONBINI_API_URL, else the public address (NIWA_KONBINI_URL,
    the one browsers follow). In a container stack they differ (http://konbini:8081 inside, http://localhost:8081 out)."""
    return (api or "").strip().rstrip("/") or (public or "").strip().rstrip("/")


def port_setting(value, default):
    """A TCP port from a setting; unset or empty gives the default, anything else that is not 1 to 65535 refuses to start."""
    value = (value or "").strip()
    if not value:
        return default
    if not value.isdigit() or not 0 < int(value) < 65536:
        raise SystemExit("niwa: %r is not a port (1 to 65535)" % value)
    return int(value)


GOPHER_PUBLIC_PORT = port_setting(os.environ.get("NIWA_GOPHER_PUBLIC_PORT"), 70)    # what the gopher menus advertise
shell.BOARD_URL = os.environ.get("NIWA_KONBINI_URL", "").rstrip("/")
shell.KURA_URL = os.environ.get("NIWA_KURA_URL", "").rstrip("/")


def clone_once():
    """The first clone (ssh or https or file). After that GitSync pulls, rebases and pushes."""
    if os.path.isdir(os.path.join(REPO, ".git")) or not REPO_URL:
        return
    os.makedirs(REPO, exist_ok=True)
    print("niwa: cloning %s%s" % (redact(REPO_URL), (" (objects from %s)" % REFERENCE) if REFERENCE else ""), flush=True)
    ref = ["--reference", REFERENCE] if REFERENCE else []
    subprocess.run(["git", "clone", "-q", *ref, "--", REPO_URL, REPO], check=True, timeout=3600)


def borrow_reference():
    """Share the reference's objects (idempotent: the first run repacks our store down to our own commits) and apply
    NIWA_REPO_SPARSE. The reference is mounted read-only at the same absolute path on the host and in here."""
    if not REFERENCE:
        if SPARSE:
            print("niwa: NIWA_REPO_SPARSE is used only with NIWA_REPO_REFERENCE; full checkout", flush=True)
        return None
    had = vk_borrow(REPO, REFERENCE, SPARSE)
    print("niwa: objects from %s (%s)%s" % (REFERENCE, "already shared" if had else "adopted, repacked",
                                            ("; sparse checkout: " + ", ".join(SPARSE)) if SPARSE else ""), flush=True)
    return had


clone_once()
borrow_reference()
state = State(DB, REPO)
garden = Garden(REPO, SUBDIR, state, private=PRIVATE)
def konbini_token(path):
    """NIWA_KONBINI_TOKEN_FILE: Niwa's service token for Konbini (a Machiya identity token), sent as Authorization on
    every call. "" when unset; a set file that holds no token refuses to start rather than call Konbini without it."""
    path = (path or "").strip()
    if not path:
        return ""
    token = read_secret(path)
    if not token:
        raise SystemExit("niwa: NIWA_KONBINI_TOKEN_FILE: no token in %s" % path)
    return token


garden.konbini = Konbini(server_url(os.environ.get("NIWA_KONBINI_API_URL"), shell.BOARD_URL),
                         login=os.environ.get("NIWA_KONBINI_TEST_LOGIN", ""),
                         token=konbini_token(os.environ.get("NIWA_KONBINI_TOKEN_FILE")))
hister = Hister(os.environ["NIWA_HISTER_URL"], os.environ.get("NIWA_HISTER_PUBLIC", "")) \
    if os.environ.get("NIWA_HISTER_URL") else None
garden.hister = hister
ARCHIVE = archive_mode(os.environ.get("NIWA_ARCHIVE"))
HISTER_SAVE = flag(os.environ.get("NIWA_HISTER_SAVE"))      # off: Hister is only looked up, Niwa never indexes into it
backends = [linkrot.WaybackBackend()] if ARCHIVE == "wayback" else []
cold = linkrot.ColdArchive(os.environ["NIWA_COLD_MAP"]) if os.environ.get("NIWA_COLD_MAP") else None
links = linkrot.Links(state, garden, backends, enabled=ARCHIVE == "wayback", cold=cold,
                      hister=linkrot.HisterBackend(hister) if hister else None, hister_save=HISTER_SAVE)
garden.links = links


def on_pull(head):
    garden.revision = head


sync = GitSync(REPO, AUTHOR, [SUBDIR or ".", EVENTS_DIR], events_dir=EVENTS_DIR, label="garden",
               pull_every=POLL, on_pull=on_pull)
garden.revision = sync.head()
writer = Writer(sync, garden, state)


APP_DIR = os.path.dirname(os.path.abspath(__file__))
# GET /api/changelog serves Niwa's own CHANGELOG.md, which lives in app/ so the image carries it.
CHANGELOG_FILE = os.path.join(APP_DIR, "CHANGELOG.md")


def make_handler(listener):
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.0"  # no keep-alive, no chunked encoding
        server_version = "niwa/" + VERSION
        timeout = 30                   # a client that stops sending lets its thread go
        _who = None                    # the identity file's answer, worked out once per request (who())

        def log_message(self, fmt, *args):
            if self.path in ("/api/status", "/api/changelog"):
                return
            sys.stderr.write("%s %s %s\n" % (listener, self.login(), fmt % args))

        def login(self):
            """Who is asking, for the log: the principal and how it was proven, or the Tailscale login. Never a
            token."""
            if IDENTITY is not None:
                who = self._who
                return "%s(%s)" % (who.principal.name, who.principal.via) if who else "-"
            headers = getattr(self, "headers", None)       # a request too broken to parse has none
            return headers.get("Tailscale-User-Login", "-") if headers is not None else "-"

        def who(self):
            """The identity file's answer for this request (vaultkit.identity), worked out once."""
            if self._who is None:
                self._who = IDENTITY.resolve(self.headers, self.client_address[0] if self.client_address else "")
            return self._who

        def host_ok(self):
            """NIWA_AUTH=open's Host allow-list (DNS rebinding); every request in the other modes."""
            return AUTH != "open" or host_allowed(self.headers.get("Host"), ALLOWED_HOSTS)

        def allowed(self):
            if not self.host_ok():
                return False
            if IDENTITY is not None:
                who = self.who()
                return bool(who) and who.principal.can("niwa", "read")
            if AUTH == "open":
                return True
            return "*" in USERS or self.headers.get("Tailscale-User-Login", "") in USERS

        def may(self, action):
            """A grant beyond read: "suggest" (POST /api/suggest) or "publish" (publish, dismiss, the garden fields).
            Decided by the identity file, never by a header the caller writes. Without one, everyone the gate admits
            may, as before (the owner powers still need a same-origin form post, and writer.py the "web" label)."""
            if IDENTITY is None:
                return self.allowed()
            who = self.who()
            return self.allowed() and who.principal.can("niwa", action)

        def owner(self):
            """The full /api/status (where Konbini and Hister are, what they answered): the owner only. Without an
            identity file, everyone the gate admits is the owner, as before."""
            if IDENTITY is not None:
                return self.host_ok() and bool(self.who()) and self.who().principal.owner
            return self.allowed()

        def refuse(self):
            if not self.host_ok():
                return self.send(403, "forbidden: NIWA_AUTH=open serves localhost, IP addresses, NIWA_HOST, "
                                      "NIWA_PUBLIC_URL and NIWA_ALLOWED_HOSTS, not %r\n" % self.headers.get("Host", ""), "text/plain")
            if IDENTITY is not None:
                who = self.who()
                status = who.status if not who else 403
                if status == 401 and self.browser_page():     # vaultkit's 401 page: the plain header, the way in
                    page = signin.needed(shell.ROOM, self.path, shell.prefs(self.headers.get("Cookie")),
                                         signin=IDENTITY.signin)
                    return self.reply(401, list(signin.PAGE_HEADERS), page.encode())
                body = (who.error if not who else "not allowed in niwa") + "\n"
                return self.send(status, body, "text/plain", headers=[NO_STORE])
            return self.send(403, "forbidden\n", "text/plain")

        def browser_page(self):
            """A browser asking for a page (not an API, not a write): it gets the sign-in link with its 401."""
            path = urlsplit(self.path).path
            return self.command in ("GET", "HEAD") and not path.startswith("/api/") \
                and "text/html" in (self.headers.get("Accept") or "")

        def signed_in(self):
            """The principal's name when it came with the built-in sign-in's session cookie, else "" (Settings shows
            a sign-out button only then)."""
            if IDENTITY is None or not self.who():
                return ""
            return self.who().principal.name if self.who().principal.via == "session" else ""

        def reply(self, status, headers, body):
            """A vaultkit.signin answer: (status, [(header, value)], bytes)."""
            self.send_response(status)
            for k, v in headers:
                self.send_header(k, v)
            if any(k.lower() == "content-type" and v.startswith("text/html") for k, v in headers):
                for k, v in shell.house.security_headers():     # the sign-in pages: Niwa's CSP on top of theirs
                    self.send_header(k, v)
            self.send_header("Content-Length", str(len(body)))
            if status == 413:
                self.close_connection = True
                self.send_header("Connection", "close")
            for c in (self._who.cookies if self._who is not None else ()):
                self.send_header("Set-Cookie", c)          # a renewed session, or a bad one cleared
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(body)

        def signin_body(self, limit):
            """The body for a sign-in, pairing or prefs request (vaultkit.signin.read_body, at most `limit`); None
            when it's too large, chunked or short, after reading and dropping what can be read so the 413 isn't lost
            to a reset (as body() does)."""
            data = signin.read_body(self.headers, self.rfile, limit)
            if data is None:
                raw = (self.headers.get("Content-Length") or "").strip()
                if raw.isdigit() and not self.headers.get("Transfer-Encoding"):
                    self.drain(int(raw))
            return data

        def too_large(self, api):
            self.close_connection = True
            if api:
                return self.send_json(413, {"error": "request body too large"})
            return self.send(413, "request body too large\n", "text/plain", headers=[NO_STORE])

        def actor(self):
            if IDENTITY is not None:  # the principal's name ("local" in open mode, as before)
                return self.who().principal.name
            if AUTH == "open":        # nothing vouches for the header without Tailscale: never let it name the actor
                return "local"
            return self.headers.get("Tailscale-User-Login", "")

        def agent(self):
            return (self.headers.get("X-Agent") or "web")[:80]

        def principal(self):
            """Whose preferences these are, once the gate admitted the request: the identity file's principal, or
            without one identity.ambient (the Tailscale login, or open mode's owner). None otherwise."""
            if not self.allowed():
                return None
            if IDENTITY is not None:
                return self.who().principal
            return identity.ambient(AUTH, self.headers)

        def ctx(self):
            """Theme and text size (machiya.js writes the cookies), /api/prefs when the request has a principal (the
            page then syncs them with the server), and the signed-in name for the header's person button."""
            ctx = shell.prefs(self.headers.get("Cookie"))
            ctx.prefs_url = "/api/prefs" if self.principal() is not None else ""
            ctx.who = self.signed_in()
            return ctx

        def origins(self):
            """Where a cookie- or login-borne prefs PUT may come from: NIWA_PUBLIC_URL; else, in open mode with no
            identity file, this request's own Host, which host_ok() already checked (an IP literal, localhost or a
            listed name, never a name a stranger's page pointed here), so the settings page works over plain http on
            localhost."""
            if ORIGINS or IDENTITY is not None or AUTH != "open":
                return ORIGINS
            host = (self.headers.get("Host") or "").strip().lower()
            return ("http://" + host, "https://" + host) if host and host_allowed(host, ALLOWED_HOSTS) else ()

        def prefs(self, method, body=b""):
            """GET/PUT /api/prefs as this request's principal (after the gate)."""
            origins = self.origins()
            if IDENTITY is not None:
                secure = IDENTITY.secure
            else:                   # the open-mode Host origin may be plain http (localhost); else NIWA_PUBLIC_URL's
                secure = SECURE and origins == ORIGINS
            return self.reply(*signin.handle_prefs(prefs_store(), self.principal(), method, self.headers, body,
                                                   secure=secure, origins=origins))

        def send(self, status, body, ctype="text/html", headers=()):
            if isinstance(body, str):
                data = body.encode("utf-8")
                ctype += "; charset=utf-8"
            else:
                data = body
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            if status == 413:
                self.send_header("Connection", "close")
            if ctype.startswith("text/html"):           # every page: the CSP (no inline script), nosniff, Referrer
                for k, v in shell.house.security_headers():
                    self.send_header(k, v)
            for k, v in headers:
                self.send_header(k, v)
            for c in (self._who.cookies if self._who is not None else ()):
                self.send_header("Set-Cookie", c)          # a renewed session, or a bad one cleared
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(data)

        def send_json(self, status, obj):
            self.send(status, json.dumps(obj, indent=1, default=str), "application/json")

        def do_HEAD(self):
            self.do_GET()

        def do_PUT(self):
            """PUT /api/prefs only, after the gate (the niwa read grant, or the old gate without an identity file)."""
            path = unquote(urlsplit(self.path).path)
            if path != "/api/prefs":
                return self.send_error(501, "Unsupported method ('PUT')")
            if not self.allowed():
                return self.refuse()
            body = self.signin_body(signin.MAX_PREFS)
            if body is None:
                return self.too_large(True)
            return self.prefs("PUT", body)

        # -- reads ---------------------------------------------------------------------------------------------

        def do_GET(self):
            url = urlsplit(self.path)
            path, query = unquote(url.path), parse_qs(url.query)
            if path == "/api/status":
                return self.send_json(200, status(owner=self.owner()))
            if path == "/api/changelog":        # open like /api/status: the landing page's "recent deploys"
                code, body, headers = changelog.handle(CHANGELOG_FILE, self.headers)
                return self.reply(code, headers, body)
            if path == "/signin" and IDENTITY is not None:      # before the gate: the way past it
                if not self.host_ok():
                    return self.refuse()
                return self.reply(*signin.handle_get(IDENTITY, self.headers, url.query))
            if IDENTITY is not None and IDENTITY.signin and self.host_ok() \
                    and (path in SHARED_UI or path.startswith("/static/icons/")):
                return self.static(path[8:], query)      # the sign-in page's stylesheet and icons: vendored, no notes
            if not self.allowed():
                return self.refuse()
            if path == "/api/prefs":        # the principal's own preferences (identity.ambient without a file)
                return self.prefs("GET")
            if path == "/api/offline":      # the notes the service worker keeps for good (frontmatter offline: true)
                return self.send_json(200, {"urls": ["/n/" + quote(n.slug) for n in garden.published()
                                                     if n.fm.get("offline") is True and not n.rel.startswith(NO_STORE_DIRS)]})
            if path == "/api/suggestions":  # open suggestions, newest first (so an agent doesn't repeat one)
                try:
                    days = min(max(int((query.get("days") or ["60"])[0]), 1), 365)
                except ValueError:
                    return self.send_json(400, {"error": "days must be an integer"})
                found = sorted(garden.suggestions(days=days).items(), key=lambda kv: (kv[1]["date"], kv[0]), reverse=True)
                return self.send_json(200, {"suggestions": [{"path": rel, "reason": s["reason"], "agent": s["who"],
                                                             "date": s["date"]} for rel, s in found], "days": days})
            ctx = self.ctx()
            if path == "/manifest.webmanifest":
                return self.send(200, json.dumps(shell.manifest(shell.ROOM, ctx.theme, self.headers, getattr(ctx, "palette", None)), indent=1),
                                 "application/manifest+json", headers=[("Cache-Control", "no-cache"),
                                                                       ("Vary", shell.house.MANIFEST_VARY)])
            if path == "/sw.js":
                return self.send(200, shell.service_worker(shell.ROOM), "text/javascript",
                                 headers=[("Cache-Control", "no-cache")])
            if path == "/offline":
                return self.send(200, shell.offline(shell.prefs(self.headers.get("Cookie")), shell.ROOM))   # nobody's
            if path.startswith("/static/"):
                return self.static(path[8:], query)
            if path == shell.FEED:          # published notes only, behind the same gate as the garden's pages
                base = PUBLIC_URL or "https://%s" % (self.headers.get("Host") or "localhost")
                return self.send(200, feed.rss(base, "Niwa", gmodern.INTRO, feed.notes(garden, NO_STORE_DIRS)),
                                 "application/rss+xml", headers=[("Cache-Control", "max-age=300")])
            if path == "/settings":
                return self.send(200, shell.settings(ctx, VERSION, footer_status()["text"],
                                                     vk_verify.version().split(" - ")[0], self.signed_in()),
                                 headers=[NO_STORE])
            if path == "/theme":            # the no-JavaScript fallback for /settings' Theme
                theme = (query.get("set") or ["system"])[0]
                theme = {"auto": "system"}.get(theme, theme)
                theme = theme if theme in ("night", "day", "system") else "system"
                back = urlsplit(self.headers.get("Referer") or "").path
                if not back.startswith("/") or back[1:2] in ("/", "\\"):     # //host and /\host leave the site
                    back = "/"
                return self.send(302, "", "text/plain", headers=[
                    ("Location", back), ("Set-Cookie", "theme=%s; path=/; max-age=31536000" % theme)])
            self.garden_get(path, "", query, ctx)

        def static(self, name, query):
            if name.startswith("icons/"):
                icon = name[6:]
                old = shell.OLD_ICON_PREFIX
                if icon.startswith((old + "-", old + ".")) and shell.ROOM + icon[len(old):] in shell.ICONS:
                    return self.send(301, "", "text/plain", headers=[      # the icon's old name (before 0.4.0)
                        ("Location", "/static/icons/" + shell.ROOM + icon[len(old):]),
                        ("Cache-Control", "public, max-age=604800")])
                if icon in shell.ICONS:
                    with open(os.path.join(shell.ICON_DIR, icon), "rb") as f:
                        return self.send(200, f.read(), "image/svg+xml" if icon.endswith(".svg") else "image/png",
                                         headers=[("Cache-Control", "public, max-age=604800")])
            elif name in STATIC_TYPES:
                cache = "public, max-age=31536000, immutable" if query.get("v") else "max-age=300"
                with open(shell.static_path(name), "rb") as f:
                    return self.send(200, f.read(), STATIC_TYPES[name], headers=[("Cache-Control", cache)])
            self.send(404, "not found\n", "text/plain")

        def garden_get(self, gpath, base, query, ctx):
            cards = garden.konbini.cards_by_path()
            if gpath == "/":
                self.send(200, gmodern.home(ctx, base, garden, cards, (query.get("type") or [""])[0]))
            elif gpath == "/random":
                n = garden.random_note()
                self.send(302, "", "text/plain", headers=[("Location", "%s/n/%s" % (base, quote(n.slug)) if n else base + "/")])
            elif gpath.startswith("/n/"):
                n = garden.get(gpath[3:])
                if n and (query.get("preview") or [""])[0] == "1":
                    self.send_json(200, garden.preview(n))
                elif n:         # Archive/ and an unpublished note (the owner's preview) never stay on a device
                    private = n.rel.startswith(NO_STORE_DIRS) or not n.published
                    self.send(200, gmodern.note(ctx, base, garden, n, cards),
                              headers=[("Cache-Control", "no-store")] if private else ())
                else:
                    self.send(404, shell.not_found(ctx, gpath))
            elif gpath.startswith("/t/"):
                self.send(200, gmodern.tag_page(ctx, base, garden, gpath[3:], cards))
            elif gpath == "/search":
                self.send(200, gmodern.search_page(ctx, base, garden, (query.get("q") or [""])[0]))
            elif gpath == "/tags":
                self.send(200, gmodern.tags_page(ctx, base, garden))
            elif gpath == "/stream":
                reading = hister.saved_between if hister else None  # owner-only (never gemini or gopher)
                self.send(200, gmodern.stream(ctx, base, garden, stream.build(garden, links=links, reading=reading)),
                          headers=[NO_STORE])           # the board and Hister: the owner's, never on a device
            elif gpath == "/queue":
                self.send(200, gmodern.queue(ctx, base, garden, cards), headers=[NO_STORE])   # unpublished notes
            elif gpath.startswith("/a/"):
                full = garden.asset_path(gpath[3:])
                ctype = IMAGE_TYPES.get(os.path.splitext(gpath)[1].lower())
                if full and ctype:
                    private = gpath[3:].startswith(NO_STORE_DIRS)      # Archive/ attachments never stay on a device
                    with open(full, "rb") as f:
                        self.send(200, f.read(), ctype,
                                  headers=[("Cache-Control", "no-store" if private else "max-age=86400")])
                else:
                    self.send(404, "not found\n", "text/plain")
            else:
                self.send(404, shell.not_found(ctx, gpath))

        # -- writes --------------------------------------------------------------------------------------------

        def body(self):
            try:
                length = int(self.headers.get("Content-Length") or 0)
            except ValueError:
                raise WriteError(400, "invalid Content-Length")
            if length < 0:
                raise WriteError(400, "invalid Content-Length")
            if length > MAX_BODY:
                self.drain(length)
                raise WriteError(413, "request body too large")
            raw = self.rfile.read(length) if length else b""
            if "json" in (self.headers.get("Content-Type") or ""):
                try:
                    return json.loads(raw or b"{}")
                except ValueError:
                    raise WriteError(400, "invalid JSON")
            form = parse_qs(raw.decode("utf-8", "replace"), keep_blank_values=True)
            return {k: v[-1] for k, v in form.items()}

        def content_length(self):
            """Content-Length as a number for drain(); 0 when absent or unreadable."""
            raw = (self.headers.get("Content-Length") or "").strip()
            return int(raw) if raw.isdigit() else 0

        def drain(self, length):
            """Read and drop an unwanted body: closing with it unread resets the connection, and a client still
            sending sees the reset instead of the answer. Past MAX_DRAIN the client gets the reset."""
            left = min(length, MAX_DRAIN)
            try:
                while left > 0:
                    chunk = self.rfile.read(min(left, 65536))
                    if not chunk:
                        break
                    left -= len(chunk)
            except OSError:                # stalled (the 30 s timeout) or gone: answer what we can
                pass

        def same_origin(self):
            host = self.headers.get("Host", "")
            ref = self.headers.get("Origin") or self.headers.get("Referer") or ""
            return bool(host) and urlsplit(ref).netloc == host

        def do_POST(self):
            path = unquote(urlsplit(self.path).path)
            api = path.startswith("/api/")
            if path in SIGNIN_LIMITS and IDENTITY is not None:  # before the gate: sign-in, sign-out, pairing
                if not self.host_ok():
                    return self.refuse()
                body = self.signin_body(SIGNIN_LIMITS[path])
                if body is None:
                    return self.too_large(api)
                client = self.client_address[0] if self.client_address else ""
                if path == "/signin":
                    return self.reply(*signin.handle_post(IDENTITY, self.headers, body, client, ORIGINS))
                if path == "/signout":
                    return self.reply(*signin.handle_signout(IDENTITY, self.headers, ORIGINS))
                return self.reply(*signin.handle_pair(IDENTITY, self.headers, body, client))
            if not self.allowed():
                return self.refuse()
            if path in SIGNIN_LIMITS:       # no identity file: no such routes
                self.drain(self.content_length())
                return self.send_json(404, {"error": "not found"}) if api else \
                    self.send(404, "not found\n", "text/plain")
            base = ""
            try:
                data = self.body()
                if not api and not self.same_origin():
                    raise WriteError(403, "cross-site form post refused")
                if IDENTITY is not None and self.who().principal.via == "session" and not self.same_origin():
                    raise WriteError(403, "cross-site post refused")       # a cookie rides along on any site's post
                actor, agent = self.actor(), self.agent()
                if api and agent == "web" and not self.same_origin():
                    agent = "api"
                # The label the events record: "web" for the owner's form posts, as before; with an identity file
                # X-Agent still names the session that did it, and the power to do it comes from the grant (power).
                label = agent if IDENTITY is not None else "web" if not api else agent
                power = self.may("publish") if IDENTITY is not None else None
                if path in ("/dismiss", "/publish", "/meta") and power is False:
                    raise WriteError(403, "only the owner tends the garden (niwa publish)")
                if path in ("/api/suggest", "/api/garden/suggest"):
                    if not self.may("suggest"):
                        raise WriteError(403, "not allowed to suggest (niwa suggest)")
                    target = str(data.get("path") or data.get("note") or data.get("slug") or "").strip()
                    n = garden.get(target[:-3] if target.endswith(".md") else target)
                    if not n:
                        card = next((c for c in garden.konbini.cards_by_path().values() if c.get("slug") == target), None)
                        n = garden.get(card["path"][:-3]) if card else None
                    if not n:
                        raise WriteError(404, "no such note or card")
                    if n.published:
                        raise WriteError(409, "already in the garden")
                    self.send_json(201, writer.suggest(n.rel, data.get("reason", ""), actor, agent))
                elif path == "/dismiss":
                    rel = data.get("rel", "")
                    n = garden.get(rel[:-3] if rel.endswith(".md") else rel)
                    if not n:
                        raise WriteError(404, "no such note")
                    writer.dismiss(n.rel, actor, label, power)
                    self.send(302, "", "text/plain", headers=[("Location", base + "/queue")])
                elif path == "/publish":
                    rel = data.get("rel", "")
                    n = garden.get(rel[:-3] if rel.endswith(".md") else rel)
                    if not n:
                        raise WriteError(404, "no such note")
                    on = data.get("on") == "1"
                    if on and data.get("confirm") != "1":
                        checks = [c for c in garden.check(n) if c[0] in ("error", "warn")]
                        if checks:
                            ctx = self.ctx()
                            return self.send(200, gmodern.note(ctx, base, garden, n, garden.konbini.cards_by_path(),
                                                               garden.check(n)))
                    writer.set_publish(n.rel, on, actor, label, power)
                    self.send(302, "", "text/plain", headers=[("Location", "%s/n/%s" % (base, quote(n.slug)))])
                elif path == "/meta":
                    rel = data.get("rel", "")
                    n = garden.get(rel[:-3] if rel.endswith(".md") else rel)
                    if not n:
                        raise WriteError(404, "no such note")
                    writer.set_garden_meta(n.rel, {"growth": data.get("growth", ""), "confidence": data.get("confidence", ""),
                                                   "garden_pin": data.get("garden_pin", "")}, actor, label, power)
                    self.send(302, "", "text/plain", headers=[("Location", "%s/n/%s" % (base, quote(n.slug)))])
                else:
                    raise WriteError(405, "no such write endpoint")
            except EditError as e:         # WriteError, and vaultkit's own (no frontmatter, invalid YAML)
                if api:
                    self.send_json(e.status, dict(error=e.message, **e.extra))
                else:
                    ctx = self.ctx()
                    self.send(e.status, shell.message(ctx, "Not Saved", e.message))

    return Handler


def footer_status():
    """The footer's status line: the synced commit, when, and how much is in the garden."""
    head, when = (sync.head() or "")[:7], ""
    if sync.last_pull:
        mins = int((time.time() - sync.last_pull) // 60)
        when = " just now" if mins < 1 else " %d min ago" % mins if mins < 120 else " %d h ago" % (mins // 60)
    stale = not sync.last_pull or time.time() - sync.last_pull > max(600, 5 * POLL)
    text = "synced %s%s · %d published" % (head or "?", when, len(garden.published()))
    if sync.error:
        text += " · " + sync.error
    return {"text": text, "state": "stale" if (stale or sync.error) else "ok"}


shell.STATUS = footer_status


def status(owner=False):
    """Open for monitoring. Only the owner sees where Konbini and Hister are and what they answered."""
    garden.index()
    sync_status = dict(sync.status(), error=redact(sync.status().get("error")))
    if owner:
        konbini = garden.konbini.status()
        hister_status = dict(hister.status(), error=hister.error or None) if hister else "off"
    else:
        konbini = {"on": garden.konbini.enabled(), "ok": not garden.konbini.error}
        hister_status = {"on": True, "ok": not hister.error} if hister else "off"
    return {"version": VERSION, "vaultkit": vk_verify.version().split(" - ")[0], "head": sync.head(),
            "notes": len(garden.notes), "published": len(garden.published()), "sync": sync_status,
            "konbini": konbini, "hister": hister_status, "links": links.last_run, "ready": bool(garden.revision),
            "error": redact(sync.error) or None, "auth": AUTH}


def serve(port, listener):
    server = ThreadingHTTPServer((BIND, port), make_handler(listener))
    server.daemon_threads = True
    server.serve_forever()


def main():
    for p in vk_verify.check():
        print("niwa: vaultkit drift: %s" % p, flush=True)
    garden.index()
    if IDENTITY is not None:
        users = "from %s (NIWA_AUTH=%s)" % (IDENTITY.path, AUTH)
    else:
        users = "anyone (NIWA_AUTH=open)" if AUTH == "open" else ",".join(sorted(USERS)) or "NOBODY (set NIWA_USERS)"
    print("niwa %s (vaultkit %s): %d notes, %d published; repo %s, subdir %r; konbini %s%s; hister %s; users %s" % (
        VERSION, vk_verify.version().split(" - ")[0], len(garden.notes), len(garden.published()), REPO, SUBDIR,
        shell.BOARD_URL or "off", " (service token)" if garden.konbini.token else "", "on" if hister else "off",
        users), flush=True)
    print("niwa: link archive %s; hister save %s" % (ARCHIVE, "on" if HISTER_SAVE else "off"), flush=True)
    print("niwa: listening on %s: web %d, gemini 1965, gopher 7070%s" % (
        BIND, PORT, ("; settings from " + ENV_FILE) if ENV_FILE else ""), flush=True)
    if AUTH == "open":
        print("niwa: WARNING: NIWA_AUTH=open: no identity check. Anyone who can reach %s:%d can read every note, "
              "publish and change the garden. Use it only on localhost or a trusted LAN." % (BIND, PORT), flush=True)
    if not HOST:
        print("niwa: WARNING: NIWA_HOST is not set: the gemini certificate and the gopher menus name localhost, and the "
              "footer has no Gemini or Gopher links. Set NIWA_HOST to the name people use to reach this machine.", flush=True)
    threading.Thread(target=sync.worker, daemon=True).start()
    threading.Thread(target=links.worker, daemon=True).start()
    smallweb.start(garden, None, DATA_DIR, SMALLWEB_HOST, BIND, GOPHER_PUBLIC_PORT)
    serve(PORT, "tailnet")


if __name__ == "__main__":
    main()
