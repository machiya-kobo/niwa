"""Hister: a self-hosted search engine and page archive, reached over HTTP (optional).

Niwa uses it for two things: link rot shows the owner's private copy of an
external link (links.HisterBackend; indexing a link that Hister lacks only
happens with NIWA_HISTER_SAVE on), and the owner's stream says how many pages
were saved each week and lists a few of them.

Every call sends `Origin: hister://` (without it Hister answers 500/403).
With NIWA_HISTER_TOKEN_FILE set, every call also sends the owner's Hister token
as `X-Access-Token`, and the `hister` command-line tool gets it as
HISTER__APP__ACCESS_TOKEN in its own environment (never argv). The token is
never logged, and never kept in an error message. Unset: nothing is sent, and
whatever network rule guards the Hister server is the gate. API calls go to
NIWA_HISTER_URL; links shown in the browser use NIWA_HISTER_PUBLIC.

Privacy: everything from here is owner-only. Search results, copies and
private_url must never reach gemini or gopher."""
import datetime
import json
import os
import subprocess
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

from vaultkit import read_secret

CACHE_SECONDS = 600
# The label Machiya's rooms put on the pages they save into Hister. The saved-pages count leaves these out, and
# index() uses it unless a caller passes another.
ROOM_LABEL = "konbini"
TOKEN_ENV = "HISTER__APP__ACCESS_TOKEN"     # how the hister CLI takes its token


def ts_date(value):
    try:
        return datetime.datetime.fromtimestamp(int(value), datetime.timezone.utc).date().isoformat()
    except (TypeError, ValueError, OverflowError, OSError):
        return ""


def domain_of(url):
    host = urllib.parse.urlsplit(url).netloc.lower()
    return host[4:] if host.startswith("www.") else host


class Hister:
    def __init__(self, api, public, cli="hister", token_file=""):
        self.api = api.rstrip("/")
        self.public = (public or api).rstrip("/")
        self.cli = cli
        self.token_file = (token_file or "").strip()
        self._token = ("", None)        # (token, the file's mtime) as last read
        self.lock = threading.Lock()
        self.cache = {}
        self.error = ""
        self.last_ok = ""

    # -- the owner's token -------------------------------------------------------

    def token(self):
        """The Hister token in token_file, read again when the file changes (a rotation needs no restart); "" when
        no file is set or it can't be read."""
        if not self.token_file:
            return ""
        try:
            mtime = os.stat(self.token_file).st_mtime_ns
        except OSError:
            return ""
        if self._token[1] != mtime:
            self._token = (read_secret(self.token_file), mtime)
        return self._token[0]

    @property
    def error(self):
        return self._error

    @error.setter
    def error(self, text):
        """The last failure, for /api/status: with the token taken out of it, whatever produced the text."""
        token = self.token()
        self._error = text.replace(token, "***") if token and text else text

    # -- transport ---------------------------------------------------------------

    def call(self, method, path, body=None, timeout=10):
        """(status, parsed JSON or text); status 0 when Hister can't be reached."""
        data = json.dumps(body).encode() if body is not None else None
        headers = {"Origin": "hister://", "Accept": "application/json", "Content-Type": "application/json"}
        token = self.token()
        if token:
            headers["X-Access-Token"] = token
        req = urllib.request.Request(self.api + path, data=data, method=method, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                raw, status = r.read(), r.status
        except urllib.error.HTTPError as e:
            raw, status = e.read(), e.code
        except (urllib.error.URLError, OSError, ValueError) as e:
            self.error = "hister unreachable: %s" % e
            return 0, None
        self.last_ok = datetime.datetime.now().isoformat(timespec="seconds")
        if status < 500:
            self.error = ""
        try:
            return status, json.loads(raw or b"null")
        except ValueError:
            return status, raw.decode("utf-8", "replace")

    # -- search ------------------------------------------------------------------

    def search(self, q, timeout=4):
        """Documents matching a Hister query (first page, up to 100), cached briefly."""
        now = time.time()
        with self.lock:
            hit = self.cache.get(q)
            if hit and now - hit[0] < CACHE_SECONDS:
                return hit[1], hit[2]
        status, data = self.call("GET", "/search?q=" + urllib.parse.quote(q), timeout=timeout)
        if status != 200 or not isinstance(data, dict):
            return [], 0
        docs, total = data.get("documents") or [], data.get("total") or 0
        with self.lock:
            if len(self.cache) > 500:
                self.cache.clear()
            self.cache[q] = (now, docs, total)
        return docs, total

    def find(self, url):
        """The document Hister holds for a URL (or its normalised form), or None."""
        from urlnorm import norm
        for u in dict.fromkeys((url, norm(url))):
            status, data = self.call("GET", "/search?q=" + urllib.parse.quote('url:"%s"' % u.replace('"', "%22")))
            if status == 200 and isinstance(data, dict):
                for d in data.get("documents") or []:
                    if d.get("url") in (url, u):
                        return d
        return None

    def preview_url(self, url):
        return "%s/preview?id=%s" % (self.public, urllib.parse.quote(url, safe=""))

    def search_url(self, q):
        return "%s/?q=%s" % (self.public, urllib.parse.quote(q))

    # -- writes ------------------------------------------------------------------

    def add(self, doc):
        """POST a whole document. True when Hister stored it."""
        status, data = self.call("POST", "/api/add", doc, timeout=30)
        if status not in (200, 201):
            self.error = "add %s: HTTP %s %s" % (doc.get("url", "")[:80], status, str(data or "")[:80])
            return False
        return True

    def delete(self, url):
        status, data = self.call("POST", "/api/delete", {"query": 'url:"%s"' % url.replace('"', "%22")}, timeout=30)
        return (data or {}).get("deleted", 0) if status == 200 and isinstance(data, dict) else 0

    def index(self, url, label=ROOM_LABEL):
        """Fetch and store a page with the hister CLI (/api/add alone doesn't fetch).
        Callers check find() first: --force on an existing document would
        replace its metadata (imported tags and the archive link)."""
        try:
            token = self.token()
            env = {**os.environ, TOKEN_ENV: token} if token else None      # in the child's environment only, never argv
            r = subprocess.run([self.cli, "-u", self.api, "index", "--label", label, url],
                               capture_output=True, text=True, timeout=120, env=env)
        except (subprocess.SubprocessError, OSError) as e:
            self.error = "hister index failed: %s" % e
            return False
        if r.returncode != 0:
            self.error = "hister index %s: %s" % (url[:80], (r.stderr or r.stdout).strip()[:120])
            return False
        return True

    # -- the stream's saved-pages line ----------------------------------------------------------

    def saved_between(self, start, end):
        """Pages added to Hister in [start, end): count plus the biggest groups
        (imported folder label, else domain). Vault notes and the pages Machiya's
        rooms saved themselves (ROOM_LABEL) don't count."""
        q = "added:>=%s added:<%s -label:vault -label:%s" % (start.isoformat(), end.isoformat(), ROOM_LABEL)
        docs, total = self.search(q)
        groups = {}
        for d in docs:
            key = d.get("label") or domain_of(d.get("url") or "")
            if key:
                groups[key] = groups.get(key, 0) + 1
        top = sorted(groups.items(), key=lambda kv: (-kv[1], kv[0].lower()))[:4]
        return {"total": total, "top": top, "search": self.search_url("added:>=%s added:<%s" % (start.isoformat(), end.isoformat()))}

    def status(self):
        return {"api": self.api, "error": self.error, "last_ok": self.last_ok}
