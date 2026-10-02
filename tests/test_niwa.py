"""Niwa's tests: the garden served standalone, the owner gate, and the write path (form post -> frontmatter edit ->
garden event -> batch commit by `garden` -> push) against a real bare remote. The clone runs the way it does in the
Machiya stack: an existing full clone that adopts a reference mirror's objects (borrow) with a sparse checkout, so
every write test also proves commit, rebase and push over borrowed objects and a cone checkout.

Run in the image (the host lacks markdown/pyyaml):
  docker build -t niwa-test app && docker run --rm --user 1000:1000 -v "$PWD":/n -w /n --entrypoint python3 niwa-test -m unittest discover -s tests
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
TMP = tempfile.mkdtemp()
NOTES = {
    "Garden.md": "---\ntitle: Garden\npublish: true\n---\nWelcome to the garden.\n",
    "MOC/Crafts.md": "---\ntags: [type/moc]\npublish: true\noffline: true\n---\nA map: [[Lantern]] and [[Paper lanterns]].\n",
    "Archive/Old map.md": "---\npublish: true\noffline: true\n---\nAn archived map.\n",
    "Projects/Lantern.md": "---\ntitle: Lantern\ndate: 2026-09-01\ntags: [type/project, topic/retro]\nproject: lantern\n"
                           "board: wip\nsummary: A tiny example project\n---\n# Lantern\n\nSee https://example.com/a for more.\n",
    "Notes/Paper lanterns.md": "---\ntitle: Paper lanterns\ntags: [topic/retro]\n---\nBamboo frames.\n",
}


def git(cwd, *args):
    return subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *args], cwd=cwd, check=True,
                          capture_output=True, text=True).stdout


src = os.path.join(TMP, "src")
for rel, text in NOTES.items():
    p = os.path.join(src, "personal", rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w") as f:
        f.write(text)
os.makedirs(os.path.join(src, ".board", "events"))
with open(os.path.join(src, ".board", "events", "2026-09.jsonl"), "w") as f:     # pre-split history
    f.write(json.dumps({"ts": "2026-09-20T10:00:00Z", "card": "x", "type": "suggest", "actor": "a", "agent": "agent-a",
                        "path": "Notes/Paper lanterns.md", "body": "nice"}) + "\n")
    f.write(json.dumps({"ts": "2026-09-20T10:00:00Z", "card": "x", "type": "move", "actor": "a"}) + "\n")
for rel in ("Archive/old.png", "Notes/lantern.png"):                                # attachments
    with open(os.path.join(src, "personal", rel), "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n")
os.makedirs(os.path.join(src, "scripts"))                                        # outside the sparse cone
with open(os.path.join(src, "scripts", "tool.sh"), "w") as f:
    f.write("echo hi\n")
git(src, "init", "-q", "-b", "main")
git(src, "add", "-A")
git(src, "commit", "-q", "-m", "init")
REMOTE = os.path.join(TMP, "remote.git")
git(TMP, "clone", "-q", "--bare", src, REMOTE)
MIRROR = os.path.join(TMP, "mirror")                 # the stack's vault copy (vault-mirror), read-only for Niwa
git(TMP, "clone", "-q", REMOTE, MIRROR)
CLONE = os.path.join(TMP, "clone")
git(TMP, "clone", "-q", "file://" + REMOTE, CLONE)   # Niwa's own full clone from before the stack shared a copy

os.environ.pop("MACHIYA_ROOMS", None)
os.environ.update(NIWA_REPO_URL="file://" + REMOTE, NIWA_REPO_DIR=CLONE, NIWA_REPO_REFERENCE=MIRROR, NIWA_REPO_SUBDIR="personal",
                  NIWA_REPO_SPARSE="personal, .garden,.board/",
                  NIWA_DB=os.path.join(TMP, "data", "niwa.sqlite3"), NIWA_USERS="owner@test", NIWA_ARCHIVE="none",
                  NIWA_PORT="0", NIWA_KONBINI_URL="", NIWA_HOST="niwa.test")
sys.path.insert(0, os.path.join(HERE, "..", "app"))

import niwa        # noqa: E402

SERVER = niwa.ThreadingHTTPServer(("127.0.0.1", 0), niwa.make_handler("tailnet"))
threading.Thread(target=SERVER.serve_forever, daemon=True).start()
BASE = "http://127.0.0.1:%d" % SERVER.server_address[1]
HOST = "127.0.0.1:%d" % SERVER.server_address[1]


def req(path, data=None, user="owner@test", origin=True, json_body=None, agent=None):
    headers = {"User-Agent": "Mozilla/5.0 Firefox/130"}
    if user:
        headers["Tailscale-User-Login"] = user
    if origin:
        headers["Origin"] = "http://" + HOST
    if agent:
        headers["X-Agent"] = agent
    body = None
    if json_body is not None:
        body, headers["Content-Type"] = json.dumps(json_body).encode(), "application/json"
    elif data is not None:
        body = urllib.parse.urlencode(data).encode()
    r = urllib.request.Request(BASE + path, data=body, headers=headers)

    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *a, **k):
            return None
    try:
        with urllib.request.build_opener(NoRedirect).open(r, timeout=20) as resp:
            return resp.status, resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")


def raw(method, path, headers=(), body=b""):
    """A request with exactly these headers (urllib fixes Host and Content-Length): (status, headers, body)."""
    import socket
    head = "".join("%s: %s\r\n" % kv for kv in headers)
    with socket.create_connection(("127.0.0.1", SERVER.server_address[1]), timeout=10) as c:
        c.sendall(("%s %s HTTP/1.0\r\n%s\r\n" % (method, path, head)).encode() + body)
        data = b""
        while True:
            chunk = c.recv(65536)
            if not chunk:
                break
            data += chunk
    top, _, rest = data.partition(b"\r\n\r\n")
    lines = top.decode("latin-1").split("\r\n")
    return int(lines[0].split()[1]), dict(l.split(": ", 1) for l in lines[1:] if ": " in l), rest.decode("utf-8", "replace")


def write_note(rel, text):
    """A note added to the clone for one test (the caller removes it)."""
    path = os.path.join(niwa.garden.root, rel)
    with open(path, "w") as f:
        f.write(text)
    niwa.garden.revision += "x"
    return path


def remote_file(rel):
    return subprocess.run(["git", "--git-dir", REMOTE, "show", "HEAD:" + rel], capture_output=True, text=True).stdout


class ReadTest(unittest.TestCase):
    def test_pages_standalone(self):
        for p in ("/", "/n/MOC/Crafts", "/tags", "/t/topic/retro", "/stream", "/queue", "/api/status",
                  "/manifest.webmanifest", "/sw.js", "/offline", "/static/niwa.css", "/static/icons/garden.svg",
                  "/settings", "/static/machiya.css", "/static/machiya.js"):
            self.assertEqual(req(p)[0], 200, p)
        self.assertEqual(req("/n/Notes/Paper%20lanterns")[0], 200)    # unpublished notes are readable by the owner

    def test_owner_gate(self):
        self.assertEqual(req("/", user=None)[0], 403)
        self.assertEqual(req("/", user="guest@test")[0], 403)
        self.assertEqual(req("/api/status", user=None)[0], 200)

    def test_borrowed_objects_and_sparse_checkout(self):
        with open(os.path.join(CLONE, ".git", "objects", "info", "alternates")) as f:
            self.assertIn(os.path.join(MIRROR, ".git", "objects"), f.read())
        counts = dict(l.split(": ") for l in git(CLONE, "count-objects", "-v").splitlines())
        self.assertEqual(counts["in-pack"], "0")        # the history is on disk once, in the mirror
        self.assertTrue(os.path.exists(os.path.join(CLONE, "personal", "Garden.md")))
        self.assertTrue(os.path.exists(os.path.join(CLONE, ".board", "events", "2026-09.jsonl")))
        self.assertFalse(os.path.exists(os.path.join(CLONE, "scripts")))
        self.assertEqual(sorted(git(CLONE, "sparse-checkout", "list").split()), [".board", ".garden", "personal"])
        self.assertTrue(niwa.borrow_reference())         # idempotent: a restart finds it already in place

    def test_sister_links_only_when_set(self):
        _, body = req("/n/MOC/Crafts")
        self.assertNotIn('data-room="konbini"', body)    # no MACHIYA_ROOMS, no Konbini or Kura URL: no sister rooms
        self.assertNotIn("View in Kura", body)
        self.assertIn('<b class="here">Garden</b>', req("/")[1])   # Title Case nav, like the tab bar
        niwa.shell.BOARD_URL, niwa.shell.KURA_URL = "https://konbini.test", "https://kura.test"
        try:                                            # standing alone, the switcher falls back to Niwa's own settings
            _, body = req("/n/MOC/Crafts")
            self.assertIn('<a href="https://konbini.test/" data-room="konbini">', body)
            self.assertIn('<a href="https://kura.test/" data-room="kura">', body)
            self.assertIn('<a class="thing is-note" href="https://kura.test/n/MOC/Crafts">View in Kura</a>', body)
        finally:
            niwa.shell.BOARD_URL = niwa.shell.KURA_URL = ""
        os.environ["MACHIYA_ROOMS"] = "shiori=https://shiori.test,kura=https://kura.stack"
        try:                                            # in the stack, MACHIYA_ROOMS wins
            _, body = req("/")
            self.assertIn('<a href="https://shiori.test/" data-room="shiori">', body)
            self.assertIn('<a href="https://kura.stack/" data-room="kura">', body)
        finally:
            del os.environ["MACHIYA_ROOMS"]

    def test_settings_and_theme(self):
        _, body = req("/settings")
        for want in ("<h2>Appearance</h2>", "<h2>Garden</h2>", 'data-set="linkPreviews"', "<h2>About</h2>", 'data-set="theme"'):
            self.assertIn(want, body)
        self.assertIn('class="iconbtn gear" href="/settings"', req("/")[1])
        status, _ = req("/theme?set=auto")
        self.assertEqual(status, 302)

    def test_empty_states(self):
        self.assertIn('<div class="empty"><h2>No Published Notes</h2>', req("/t/topic/nothing")[1])
        self.assertIn('<div class="empty"><h2>No Published Logs</h2>', req("/?type=log")[1])

    def test_room_search(self):
        self.assertIn('placeholder="Search the Garden"', req("/")[1])          # in the header on every page
        _, body = req("/search?q=MAP+lantern")                                  # every word, any case, [[links]] as words
        self.assertIn('href="/n/MOC/Crafts"', body)
        self.assertIn("<mark>map</mark>", body)
        _, body = req("/search?q=bamboo")                                       # unpublished notes are never found
        self.assertIn("<h2>No Matches</h2>", body)
        self.assertNotIn("Paper lanterns", body)
        self.assertNotIn("Search everything in Shiori", body)                  # no Shiori address: no handoff
        os.environ["MACHIYA_ROOMS"] = "shiori=https://shiori.test"
        try:
            self.assertIn('href="https://shiori.test/#/search?q=bamboo"', req("/search?q=bamboo")[1])
        finally:
            del os.environ["MACHIYA_ROOMS"]
        self.assertIn("<h2>Search the Garden</h2>", req("/search")[1])

    def test_service_worker_is_the_shared_core(self):
        _, sw = req("/sw.js")
        self.assertTrue(sw.startswith('importScripts("/static/machiya-sw.js?v='))
        cfg = json.loads(sw.split("machiyaSW(", 1)[1].rsplit(");", 1)[0])
        self.assertEqual((cfg["notes"], cfg["pins"], cfg["offline"]), ({"match": "^/n/", "limit": 200}, "/api/offline", "/offline"))
        self.assertIn("/offline", cfg["precache"])
        code, core = req(sw.split('"', 2)[1])
        self.assertEqual(code, 200)
        install = core.split('addEventListener("install"', 1)[1].split("});", 1)[0]
        self.assertNotIn("self.skipWaiting", install)                           # waits for the toast
        self.assertIn('type === "SKIP_WAITING") self.skipWaiting()', core)

    def test_offline_reading(self):
        self.assertEqual(json.loads(req("/api/offline")[1]), {"urls": ["/n/MOC/Crafts"]})   # Archive/ never
        self.assertIn('<meta name="machiya-offline" content="pin">', req("/n/MOC/Crafts")[1])
        self.assertNotIn("machiya-offline", req("/n/Garden")[1])
        r = urllib.request.urlopen(urllib.request.Request(BASE + "/n/Archive/Old%20map",
                                                          headers={"Tailscale-User-Login": "owner@test"}))
        self.assertEqual(r.headers.get("Cache-Control"), "no-store")
        self.assertIn("Clear Offline Copies", req("/settings")[1])
        for path, want in (("/a/Archive/old.png", "no-store"), ("/a/Notes/lantern.png", "max-age=86400")):
            r = urllib.request.urlopen(urllib.request.Request(BASE + path, headers={"Tailscale-User-Login": "owner@test"}))
            self.assertEqual(r.headers.get("Cache-Control"), want, path)            # attachments too

    def test_history_suggestion_in_queue(self):
        _, body = req("/queue")
        self.assertIn("Paper lanterns", body)


class AuthTest(unittest.TestCase):
    def test_auth_modes(self):
        self.assertEqual(niwa.auth_mode(None), "tailscale")          # the default: the Tailscale-User-Login allow-list
        self.assertEqual(niwa.auth_mode(" Open "), "open")
        with self.assertRaises(SystemExit):
            niwa.auth_mode("none")                                    # a typo never opens the garden
        self.assertEqual(niwa.BIND, "0.0.0.0")
        self.assertEqual(json.loads(req("/api/status")[1])["auth"], "tailscale")

    def test_open_mode_skips_the_allow_list_only(self):
        niwa.AUTH = "open"
        try:
            self.assertEqual(req("/", user=None)[0], 200)
            self.assertEqual(req("/queue", user="guest@test")[0], 200)
            status, _ = req("/dismiss", {"rel": "Notes/Nothing.md"}, user=None, origin=False)
            self.assertEqual(status, 403)                             # cross-site form posts are still refused
            status, body = req("/api/suggest", json_body={"path": "Notes/Paper lanterns.md", "reason": "x"},
                               user="mallory@test", agent="bot")
            self.assertIn(status, (201, 409))
            if status == 201:
                self.assertEqual(json.loads(body).get("actor"), "local")   # the header never names the actor
        finally:
            niwa.AUTH = "tailscale"
        self.assertEqual(req("/", user=None)[0], 403)


class ReleaseDefaultsTest(unittest.TestCase):
    """The generic defaults of a public install (no owner-specific host, User-Agent or folder names)."""
    APP = os.path.join(HERE, "..", "app")

    def links_in(self, **env):
        out = subprocess.run([sys.executable, "-c", "import links; print(links.UA); print(links.SKIP_HOSTS)"], cwd=self.APP,
                             env={**{k: v for k, v in os.environ.items() if not k.startswith("NIWA_")}, **env},
                             capture_output=True, text=True, check=True).stdout.splitlines()
        return out[0], out[1]

    def test_link_checker_user_agent(self):
        self.assertEqual(self.links_in()[0], "niwa-links/1")                          # nothing about the owner
        self.assertEqual(self.links_in(NIWA_LINKS_USER_AGENT=" bot/2 (+https://example.org) ")[0], "bot/2 (+https://example.org)")

    def test_skip_hosts_are_generic_and_extendable(self):
        _, hosts = self.links_in()
        self.assertEqual(hosts, "('localhost', 'ts.net')")
        _, hosts = self.links_in(NIWA_SKIP_HOSTS=" Intranet.Example , .wiki.test.")
        self.assertEqual(hosts, "('localhost', 'ts.net', 'intranet.example', 'wiki.test')")

    def stream_in(self, **env):
        out = subprocess.run([sys.executable, "-c", "import stream; print(stream.TZ); print(sorted(stream.IGNORED_AUTHORS))"],
                             cwd=self.APP, env={**{k: v for k, v in os.environ.items() if k not in ("TZ",) and not k.startswith("NIWA_")}, **env},
                             capture_output=True, text=True, check=True).stdout.splitlines()
        return out[0], out[1]

    def test_stream_time_zone_defaults_to_utc(self):
        self.assertEqual(self.stream_in()[0], "UTC")
        self.assertEqual(self.stream_in(TZ="Europe/Berlin")[0], "Europe/Berlin")

    def test_stream_ignored_authors(self):
        self.assertEqual(self.stream_in()[1], "['garden']")                                  # only Niwa's own writes
        self.assertEqual(self.stream_in(NIWA_IGNORE_AUTHORS=" bot-a , bot-b ,")[1], "['bot-a', 'bot-b', 'garden']")
        self.assertEqual(self.stream_in(NIWA_GIT_NAME="tender", NIWA_IGNORE_AUTHORS="bot-a")[1], "['bot-a', 'tender']")

    def test_version_is_reported_and_in_the_changelog(self):
        self.assertEqual(json.loads(req("/api/status")[1])["version"], niwa.VERSION)
        with open(os.path.join(HERE, "..", "CHANGELOG.md")) as f:
            self.assertIn("\n## %s\n" % niwa.VERSION, f.read())

    def test_gemini_and_gopher_stream_never_carry_the_board_or_unpublished_notes(self):
        import datetime
        import smallweb
        from konbini import Konbini

        today = datetime.date.today().isoformat()

        class FakeBoard(Konbini):
            def get(self, path):
                if path.startswith("/api/digest"):
                    return {"now": {"wip": [{"slug": "hush", "title": "Hush Card", "next": "call the hush contact"}],
                                    "blocked": [{"slug": "hush2", "title": "Hush Blocked", "blocked_by": "waiting on hush"}]},
                            "entries": [{"kind": "project", "date": today, "slug": "hush", "title": "Hush Card",
                                         "path": "Notes/Paper lanterns.md", "moves": ["wip"], "top": ["hush milestone"],
                                         "more": 0, "next": "hush next step", "board": "wip", "done": False, "started": True,
                                         "rows_n": 1}]}
                if path.startswith("/api/cards"):
                    return {"cards": [{"path": "Notes/Paper lanterns.md", "slug": "hush"}]}
                return None

        old_board = niwa.garden.konbini
        try:
            niwa.garden.konbini = FakeBoard("http://board.test")
            self.assertEqual(req("/api/suggest", json_body={"path": "Notes/Paper lanterns.md", "reason": "x"},
                                 origin=False, agent="agent-a")[0], 201)       # an unpublished note, now in the stream's events
            owner = json.dumps(niwa.stream.build(niwa.garden), default=str)
            self.assertIn("Hush Card", owner)                                    # the owner's stream keeps the board
            self.assertIn("call the hush contact", owner)
            self.assertIn("Paper lanterns", owner)
            lines = smallweb.stream_lines(niwa.garden, None)
            text = "\n".join(t for t, _ in lines)
            for private in ("Hush", "hush", "Paper lanterns", "next:"):
                self.assertNotIn(private, text)                                 # gemini and gopher: no board, no unpublished title
            public = niwa.stream.build(niwa.garden, public=True)
            self.assertEqual(public["now"], {"wip": [], "blocked": []})
        finally:
            niwa.garden.konbini = old_board

    def test_gopher_listener_rebinds_right_after_a_connection(self):
        import socket
        import socketserver
        import smallweb

        class Hello(socketserver.BaseRequestHandler):
            def handle(self):
                self.request.sendall(b"hello\r\n")                              # the server closes first: TIME_WAIT on its side

        first = smallweb.GopherServer(("127.0.0.1", 0), Hello)
        port = first.server_address[1]
        threading.Thread(target=first.handle_request, daemon=True).start()
        with socket.create_connection(("127.0.0.1", port), timeout=5) as c:
            self.assertEqual(c.recv(20), b"hello\r\n")
        time.sleep(0.2)
        first.server_close()
        second = smallweb.GopherServer(("127.0.0.1", port), Hello)                # a restart: must not fail with EADDRINUSE
        second.server_close()

    def test_gopher_public_port_and_konbini_api_url_settings(self):
        import socket
        import smallweb
        self.assertEqual(niwa.port_setting(None, 70), 70)
        self.assertEqual(niwa.port_setting(" ", 70), 70)
        self.assertEqual(niwa.port_setting(" 7070 ", 70), 7070)
        for bad in ("0", "65536", "x", "-1", "70.5"):
            with self.assertRaises(SystemExit):
                niwa.port_setting(bad, 70)
        self.assertEqual(niwa.GOPHER_PUBLIC_PORT, 70)                               # the default is unchanged
        self.assertEqual(niwa.server_url("", "http://localhost:8081/"), "http://localhost:8081")
        self.assertEqual(niwa.server_url(" http://konbini:8081/ ", "http://localhost:8081"), "http://konbini:8081")
        self.assertEqual(niwa.server_url(None, None), "")
        server = smallweb.GopherServer(("127.0.0.1", 0), smallweb.gopher_handler(niwa.garden, None, "garden.test", 7071))
        threading.Thread(target=server.handle_request, daemon=True).start()
        with socket.create_connection(("127.0.0.1", server.server_address[1]), timeout=5) as c:
            c.sendall(b"\r\n")
            data = b""
            while True:
                chunk = c.recv(4096)
                if not chunk:
                    break
                data += chunk
        server.server_close()
        self.assertIn(b"\tgarden.test\t7071\r\n", data)                              # the menus advertise the given port
        self.assertNotIn(b"\tgarden.test\t70\r\n", data)

    def test_gemini_certificate_without_an_openssl_config(self):
        import smallweb
        tmp = tempfile.mkdtemp()
        try:
            bindir = os.path.join(tmp, "bin")
            os.makedirs(bindir)
            fake = os.path.join(bindir, "openssl")             # fails like a system without openssl.cnf, unless told not to read it
            with open(fake, "w") as f:
                f.write('#!/bin/sh\n[ "$OPENSSL_CONF" = /dev/null ] || { echo "Can\'t open openssl.cnf" >&2; exit 1; }\n'
                        'while [ $# -gt 0 ]; do case "$1" in -keyout) k=$2;; -out) c=$2;; esac; shift; done\n'
                        'echo key > "$k"; echo cert > "$c"\n')
            os.chmod(fake, 0o755)
            old_path = os.environ["PATH"]
            os.environ["PATH"] = bindir + os.pathsep + old_path
            try:
                crt, key = smallweb.ensure_cert(tmp, "garden.test")
            finally:
                os.environ["PATH"] = old_path
            self.assertTrue(os.path.exists(crt) and os.path.exists(key))
            self.assertEqual(oct(os.stat(key).st_mode & 0o777), "0o600")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_landing_intro_is_a_plain_text_setting(self):
        out = subprocess.run([sys.executable, "-c", "import gmodern; print(gmodern.INTRO)"], cwd=self.APP, capture_output=True, text=True,
                             check=True, env={**{k: v for k, v in os.environ.items() if not k.startswith("NIWA_")}, "NIWA_INTRO": " My <b>notes</b> & more "})
        self.assertEqual(out.stdout.strip(), "My <b>notes</b> & more")
        self.assertEqual(niwa.gmodern.INTRO, "Notes from the vault, shared as they grow.")      # the suite sets no NIWA_INTRO
        old_intro, old_text = niwa.garden.intro, niwa.gmodern.INTRO
        try:
            niwa.garden.intro = lambda base: ""                                                 # no published Garden.md
            niwa.gmodern.INTRO = "My <b>notes</b> & more"
            body = req("/")[1]
            self.assertIn("My &lt;b&gt;notes&lt;/b&gt; &amp; more", body)
            self.assertNotIn("<b>notes</b>", body)
        finally:
            niwa.garden.intro, niwa.gmodern.INTRO = old_intro, old_text

    def test_only_ip_literals_match_private_ranges(self):
        import links
        for url in ("https://100.example.com/x", "https://10.example.org/", "https://192.168.example.net/", "https://93.184.216.34/",
                    "https://notts.net.example.com/", "https://example.com:8443/a"):
            self.assertTrue(links.is_external(url), url)
        for url in ("http://10.0.0.5/x", "http://192.168.1.20:8080/", "http://100.64.1.2/", "http://127.0.0.1/", "http://172.16.0.9/",
                    "https://laptop.example.ts.net/", "https://ts.net/", "http://localhost:3000/", "https://web.archive.org/web/1/x",
                    "https://archive.org/", "http://konbini/", "http://[::1]:80/"):
            self.assertFalse(links.is_external(url), url)

    def test_hister_leaves_out_internal_hosts(self):
        import links
        self.assertTrue(links.is_internal("laptop.tail1234.ts.net"))
        self.assertTrue(links.is_internal("10.1.2.3"))
        self.assertFalse(links.is_internal("100.example.com"))
        self.assertFalse(links.is_internal("web.archive.org"))       # archive hosts are skipped for link checks only

    def test_footer_links_only_with_a_host(self):
        old = niwa.shell.GARDEN_HOST
        try:
            niwa.shell.GARDEN_HOST = ""
            foot = niwa.shell.footer()
            self.assertNotIn("gemini://", foot)
            self.assertNotIn("gopher://", foot)
            niwa.shell.GARDEN_HOST = "garden.example"
            self.assertIn('href="gemini://garden.example/"', niwa.shell.footer())
        finally:
            niwa.shell.GARDEN_HOST = old

    def test_private_folders(self):
        note = niwa.garden.get("Notes/Paper lanterns")
        niwa.garden.private = ()
        try:
            self.assertFalse(any(sev == "error" for sev, _ in niwa.garden.check(note)))
            self.assertIn("Paper lanterns", req("/queue")[1])
            niwa.garden.private = ("Notes/",)
            found = niwa.garden.check(note)
            self.assertIn(("error", "Notes/ notes are private and shouldn't be published"), found)
            queue = req("/queue")[1]
            self.assertNotIn("Paper lanterns", queue)
            self.assertIn("Private notes (Notes/) are left out.", queue)
            niwa.garden.private = ()
            self.assertNotIn("left out", req("/queue")[1])
        finally:
            niwa.garden.private = ()


class ArchiveAndHisterSaveTest(unittest.TestCase):
    """Niwa never contacts archive.org, and never indexes into Hister, unless the settings say so."""

    def test_archive_mode(self):
        for value, want in ((None, "none"), ("", "none"), ("none", "none"), ("wayback", "wayback"), (" Wayback ", "wayback"),
                            ("archive.org", "none")):
            self.assertEqual(niwa.archive_mode(value), want, value)
        self.assertEqual(niwa.ARCHIVE, "none")                       # the suite runs with NIWA_ARCHIVE=none
        self.assertEqual(niwa.links.backends, [])

    def test_flag(self):
        for value in ("1", "on", "True", " ON "):
            self.assertTrue(niwa.flag(value), value)
        for value in (None, "", "0", "off", "false", "yes"):
            self.assertFalse(niwa.flag(value), value)
        self.assertFalse(niwa.HISTER_SAVE)

    def test_hister_is_only_looked_up_unless_save_is_on(self):
        import links

        class Store:
            def __init__(self):
                self.sets = []

            def link_set(self, url, **fields):
                self.sets.append((url, fields))

        class FakeHister:
            def __init__(self):
                self.saved = []

            def lookup(self, url):
                return ("http://hister/preview?id=1", "2026-09-01") if "known" in url else None

            def save(self, url):
                self.saved.append(url)
                return ("http://hister/preview?id=2", "2026-09-30")

        def run(save, url):
            store, fake = Store(), FakeHister()
            got = links.Links(store, None, hister=fake, hister_save=save).private_copy({"url": url, "status": "live"})
            return got, fake.saved, store.sets[0][1]

        got, saved, fields = run(False, "https://new.example/a")
        self.assertEqual((got, saved), (None, []))                    # off: no index call, no copy
        self.assertNotIn("private_url", fields)
        got, saved, fields = run(False, "https://known.example/a")    # a copy Hister already has still shows
        self.assertEqual((got, saved, fields["private_backend"]), ("http://hister/preview?id=1", [], "hister"))
        got, saved, _ = run(True, "https://new.example/a")            # on: the link is indexed
        self.assertEqual((got, saved), ("http://hister/preview?id=2", ["https://new.example/a"]))
        self.assertFalse(links.Links(Store(), None).hister_save)      # the default is off


class EnvFileTest(unittest.TestCase):
    def test_settings_from_an_env_file(self):
        """A native install: rc.d passes --env-file and nothing else; the file sets the port,
        the bind address and the rest."""
        d = tempfile.mkdtemp()
        port = 18000 + os.getpid() % 1000
        with open(os.path.join(d, "niwa.env"), "w") as f:
            f.write("# niwa on a BSD\nNIWA_BIND=127.0.0.1\nNIWA_PORT=%d\nNIWA_AUTH=open\nNIWA_ARCHIVE=none\n"
                    "NIWA_REPO_URL=file://%s\nNIWA_REPO_DIR=%s/repo\nNIWA_DB=%s/niwa.sqlite3  # data\n" % (port, REMOTE, d, d))
        env = {"PATH": os.environ["PATH"], "HOME": d}                   # a clean environment, as under rc.d
        p = subprocess.Popen([sys.executable, "-u", os.path.join(HERE, "..", "app", "niwa.py"), "--env-file",
                              os.path.join(d, "niwa.env")], env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        try:
            status = None
            for _ in range(100):
                try:
                    with urllib.request.urlopen("http://127.0.0.1:%d/api/status" % port, timeout=1) as r:
                        status = json.loads(r.read())
                    break
                except OSError:
                    time.sleep(0.2)
            self.assertIsNotNone(status, "niwa didn't answer on the env file's port")
            self.assertEqual(status["auth"], "open")
            with urllib.request.urlopen("http://127.0.0.1:%d/" % port, timeout=5) as r:   # open: no header needed
                self.assertEqual(r.status, 200)
        finally:
            p.terminate()
            out = p.communicate(timeout=10)[0].decode()
            shutil.rmtree(d, ignore_errors=True)
        self.assertIn("listening on 127.0.0.1: web %d" % port, out)
        self.assertIn("settings from " + os.path.join(d, "niwa.env"), out)


class HardeningTest(unittest.TestCase):
    def test_public_stream_never_names_a_login(self):
        import smallweb
        path = write_note("Notes/Sown.md", "---\ntitle: Sown\npublish: true\n---\nSown.\n")
        try:
            niwa.state.add_event("suggest", "owner@test", "api", path="Notes/Sown.md")  # no X-Agent: only the login
            text = "\n".join(t for t, _ in smallweb.stream_lines(niwa.garden, None))
            self.assertIn("suggested: Sown", text)
            self.assertNotIn("owner@test", text)                                     # gemini and gopher: never a login
            self.assertIn("owner@test", json.dumps(niwa.stream.build(niwa.garden), default=str))   # the owner's page may
        finally:
            os.remove(path)
            niwa.garden.revision += "x"

    def test_gemini_and_gopher_serve_only_images_published_notes_show(self):
        import socket
        import smallweb
        server = smallweb.GopherServer(("127.0.0.1", 0), smallweb.gopher_handler(niwa.garden, None, "garden.test", 70))
        threading.Thread(target=server.serve_forever, daemon=True).start()

        def gopher(selector):
            with socket.create_connection(server.server_address, timeout=5) as c:
                c.sendall(selector.encode() + b"\r\n")
                return c.recv(64)

        try:
            self.assertIsNotNone(niwa.garden.asset_path("Archive/old.png"))           # the owner's web pages still have it
            for rel in ("Archive/old.png", "Notes/lantern.png"):                       # in the vault, in no published note
                self.assertIsNone(niwa.garden.public_asset_path(rel))
                self.assertNotIn(b"PNG", gopher("/a/" + rel))
            path = write_note("Notes/Lit.md", "---\npublish: true\n---\n![[lantern.png]]\n")
            try:
                self.assertTrue(niwa.garden.public_asset_path("Notes/lantern.png"))
                self.assertIn(b"PNG", gopher("/a/Notes/lantern.png"))
                self.assertNotIn(b"PNG", gopher("/a/Archive/old.png"))
            finally:
                os.remove(path)
                niwa.garden.revision += "x"
        finally:
            server.shutdown()
            server.server_close()

    def test_a_silent_gemini_client_holds_up_nobody(self):
        import socket
        import ssl
        import smallweb
        tmp = tempfile.mkdtemp()
        try:
            crt, key = smallweb.ensure_cert(tmp, "garden.test")
            ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            ctx.load_cert_chain(crt, key)
            server = smallweb.TLSServer(("127.0.0.1", 0), smallweb.GeminiHandler, ctx)
            smallweb.GeminiHandler.garden = niwa.garden
            threading.Thread(target=server.serve_forever, daemon=True).start()
            client = ssl.create_default_context()
            client.check_hostname, client.verify_mode = False, ssl.CERT_NONE
            with socket.create_connection(server.server_address):                    # connects and never says hello
                time.sleep(0.2)
                with client.wrap_socket(socket.create_connection(server.server_address, timeout=5)) as c:
                    c.sendall(b"gemini://garden.test/\r\n")
                    self.assertTrue(c.recv(64).startswith(b"20 "))
            server.shutdown()
            server.server_close()
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
        import smallweb as sw
        self.assertEqual(sw.GeminiHandler.timeout, 30)                                 # every listener lets a stalled client go
        self.assertEqual(sw.gopher_handler(niwa.garden, None, "h", 70).timeout, 30)
        self.assertEqual(niwa.make_handler("tailnet").timeout, 30)

    def test_open_mode_serves_only_known_host_names(self):
        allowed = {"localhost", "niwa.test"}
        for host in ("127.0.0.1:8080", "[::1]:8080", "192.168.1.5", "localhost:8080", "niwa.test", "NIWA.test:80"):
            self.assertTrue(niwa.host_allowed(host, allowed), host)
        for host in ("evil.test", "evil.test:8080", "localhost.evil.test", "", None, "[::1"):
            self.assertFalse(niwa.host_allowed(host, allowed), host)
        self.assertEqual(niwa.ALLOWED_HOSTS, {"localhost", "niwa.test"})               # NIWA_HOST is one of them
        port = SERVER.server_address[1]
        niwa.AUTH = "open"
        try:
            self.assertEqual(raw("GET", "/", [("Host", "localhost:%d" % port)])[0], 200)
            status, _, body = raw("GET", "/", [("Host", "evil.test:%d" % port)])         # a rebound name: refused
            self.assertEqual(status, 403)
            self.assertIn("NIWA_ALLOWED_HOSTS", body)
            form = b"rel=Notes%2FPaper+lanterns.md&on=1&confirm=1"
            status, _, _ = raw("POST", "/publish", [("Host", "evil.test:%d" % port), ("Origin", "http://evil.test:%d" % port),
                                                    ("Content-Length", str(len(form)))], form)
            self.assertEqual(status, 403)
        finally:
            niwa.AUTH = "tailscale"

    def test_bad_request_bodies_get_an_answer(self):
        path = write_note("Notes/Bare.md", "No frontmatter here.\n")
        try:
            status, body = req("/publish", {"rel": "Notes/Bare.md", "on": "1", "confirm": "1"})
            self.assertEqual(status, 422)                                                # vaultkit's EditError, not a dropped connection
            self.assertIn("no frontmatter", body)
        finally:
            os.remove(path)
            niwa.garden.revision += "x"
        owner = [("Tailscale-User-Login", "owner@test"), ("Content-Type", "application/json")]
        self.assertEqual(raw("POST", "/api/suggest", owner + [("Content-Length", "x")])[0], 400)
        self.assertEqual(raw("POST", "/api/suggest", owner + [("Content-Length", "-1")])[0], 400)
        big = b"x" * (2 << 20)
        self.assertEqual(raw("POST", "/api/suggest", owner + [("Content-Length", str(len(big)))], big)[0], 413)

    def test_an_oversized_body_gets_its_413(self):
        import socket
        body = b"x" * (12 << 20)         # over MAX_BODY: unread, closing would reset the connection before the 413
        head = ("POST /api/suggest HTTP/1.0\r\nTailscale-User-Login: owner@test\r\nContent-Type: application/json\r\n"
                "Content-Length: %d\r\n\r\n" % len(body)).encode()
        with socket.create_connection(("127.0.0.1", SERVER.server_address[1]), timeout=10) as c:
            sent = []

            def upload():
                try:
                    c.sendall(head + body)
                    sent.append(True)
                except OSError:          # reset: the server closed with the body unread
                    sent.append(False)
            sender = threading.Thread(target=upload)
            sender.start()
            sender.join(10)
            data = b""
            while True:
                chunk = c.recv(65536)    # ConnectionResetError here without the drain
                if not chunk:
                    break
                data += chunk
        self.assertEqual(sent, [True])
        self.assertTrue(data.startswith(b"HTTP/1.0 413"), data[:40])
        self.assertIn(b"Connection: close", data)

    def test_theme_goes_back_only_within_the_site(self):
        user = ("Tailscale-User-Login", "owner@test")
        for referer, back in (("http://h/tags", "/tags"), ("http://evil.test//evil.test/x", "/"),
                              ("http://evil.test/\\evil.test/x", "/"), ("", "/")):
            status, headers, _ = raw("GET", "/theme?set=day", [user, ("Referer", referer)])
            self.assertEqual((status, headers.get("Location")), (302, back), referer)

    def test_status_keeps_addresses_and_credentials_to_the_owner(self):
        from konbini import Konbini
        self.assertEqual(niwa.redact("fatal: https://user:tok@git.test/v.git and git@git.test:v.git"),
                         "fatal: https://***@git.test/v.git and git@git.test:v.git")
        self.assertEqual(niwa.redact("https://u:p@ss@git.test/v.git"), "https://***@git.test/v.git")  # @ in the password
        self.assertEqual(niwa.redact("https://git.test/a@b and https://git.test?x=a@b"),
                         "https://git.test/a@b and https://git.test?x=a@b")                     # no userinfo: untouched
        old_board, old_error = niwa.garden.konbini, niwa.sync.error
        try:
            niwa.garden.konbini = Konbini("http://konbini.internal:8081")
            niwa.sync.error = "push failed: https://user:tok@git.test/v.git"
            anyone = json.loads(req("/api/status", user=None)[1])
            self.assertNotIn("konbini.internal", json.dumps(anyone))
            self.assertEqual(anyone["konbini"], {"on": True, "ok": True})
            self.assertEqual(anyone["hister"], "off")
            owner = json.loads(req("/api/status")[1])
            self.assertEqual(owner["konbini"]["url"], "http://konbini.internal:8081")
            for data in (anyone, owner):
                self.assertNotIn("tok", json.dumps(data))
                self.assertIn("https://***@git.test", data["error"])
        finally:
            niwa.garden.konbini, niwa.sync.error = old_board, old_error

    def test_links_follow_the_published_notes(self):
        import types
        import links as linkrot
        from state import State
        tmp = tempfile.mkdtemp()
        try:
            note = types.SimpleNamespace(rel="A.md", published=True,
                                         text="https://a.example/x?p=1&q=2 and https://b.example/y")
            garden = types.SimpleNamespace(index=lambda: None, notes={"A.md": note})
            store = State(os.path.join(tmp, "db.sqlite3"), tmp)
            links = linkrot.Links(store, garden)
            self.assertEqual(links.collect(), 2)
            store.link_set("https://a.example/x?p=1&q=2", status="dead",
                           archive_url='https://web.archive.org/web/1/x"onmouseover="x', archived_at="2026-01-01")
            html = links.annotate('<a href="https://a.example/x?p=1&amp;q=2">a</a>')   # the href as Markdown renders it
            self.assertIn('class="dead"', html)
            self.assertIn("x&quot;onmouseover=&quot;x", html)                           # escaped, never a new attribute
            note.text = "https://a.example/x?p=1&q=2"                                    # the b link left the note
            links.collect()
            self.assertEqual([r["url"] for r in links.for_note("A.md")], ["https://a.example/x?p=1&q=2"])
            self.assertEqual([r["url"] for r in store.links(linkrot.IN_USE)], ["https://a.example/x?p=1&q=2"])
            self.assertTrue(store.link("https://b.example/y"))                          # the record and its copies stay
            note.published = False                                                       # unpublished: nothing is checked
            links.collect()
            self.assertEqual(store.links(linkrot.IN_USE), [])
            self.assertEqual(links.for_note("A.md"), [])
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class WriteTest(unittest.TestCase):
    def sync(self):
        niwa.sync.commit()
        self.assertTrue(niwa.sync.pull())
        niwa.sync.push()
        self.assertEqual(niwa.sync.ahead(), 0)

    def test_publish_meta_and_push(self):
        status, _ = req("/publish", {"rel": "Notes/Paper lanterns.md", "on": "1", "confirm": "1"})
        self.assertEqual(status, 302)
        self.assertTrue(niwa.garden.get("Notes/Paper lanterns").published)       # visible before the commit
        status, _ = req("/meta", {"rel": "Notes/Paper lanterns.md", "growth": "evergreen", "confidence": "likely",
                                  "garden_pin": ""})
        self.assertEqual(status, 302)
        self.sync()
        text = remote_file("personal/Notes/Paper lanterns.md")
        self.assertIn("publish: true", text)
        self.assertIn("growth: evergreen", text)
        self.assertTrue(text.endswith("Bamboo frames.\n"))                        # body untouched
        log = subprocess.run(["git", "--git-dir", REMOTE, "log", "-1", "--format=%an|%s"], capture_output=True, text=True).stdout
        self.assertTrue(log.startswith("garden|garden: ") and "publish Paper lanterns" in log and "garden Paper lanterns" in log, log)
        events = [json.loads(l) for l in remote_file(".garden/events/" + sorted(
            os.listdir(os.path.join(niwa.REPO, ".garden", "events")))[-1]).splitlines()]
        self.assertEqual([e["type"] for e in events][-2:], ["publish", "garden"])
        self.assertIn(".garden/events/*.jsonl merge=union", remote_file(".gitattributes"))
        _, body = req("/stream")
        self.assertIn("Paper lanterns", body)                                      # planted shows in the stream

    def test_agents_suggest_but_never_publish(self):
        status, body = req("/api/suggest", json_body={"path": "Projects/Lantern.md", "reason": "ready"}, origin=False,
                           agent="agent-a")
        self.assertEqual(status, 201, body)
        self.assertEqual(req("/api/suggest", json_body={"path": "MOC/Crafts.md"}, origin=False, agent="agent-a")[0], 409)
        status, _ = req("/publish", {"rel": "Projects/Lantern.md", "on": "1", "confirm": "1"}, origin=False)
        self.assertEqual(status, 403)                                              # cross-site form post refused
        self.assertFalse(niwa.garden.get("Projects/Lantern").published)

    def test_open_suggestions_are_listed(self):
        status, body = req("/api/suggestions")
        self.assertEqual(status, 200, body)
        data = json.loads(body)
        self.assertEqual(data["days"], 60)
        self.assertEqual(set(data), {"suggestions", "days"})
        by_path = {s["path"]: s for s in data["suggestions"]}
        self.assertIn(by_path["Notes/Paper lanterns.md"]["agent"], ("agent-a", "bot"))   # the pre-split history event (or a later test's)
        self.assertEqual(set(by_path["Notes/Paper lanterns.md"]), {"path", "reason", "agent", "date"})
        self.assertEqual(req("/api/suggest", json_body={"path": "Projects/Lantern.md", "reason": "ready"},
                             origin=False, agent="agent-b")[0], 201)
        data = json.loads(req("/api/suggestions")[1])
        first = data["suggestions"][0]
        self.assertEqual((first["path"], first["agent"], first["reason"]), ("Projects/Lantern.md", "agent-b", "ready"))
        self.assertEqual(first["date"], time.strftime("%Y-%m-%d", time.gmtime()))    # newest first
        self.assertNotIn("MOC/Crafts.md", {s["path"] for s in data["suggestions"]})   # published notes never appear
        self.assertEqual(json.loads(req("/api/suggestions?days=9999")[1])["days"], 365)
        self.assertEqual(json.loads(req("/api/suggestions?days=0")[1])["days"], 1)
        self.assertEqual(req("/api/suggestions?days=x")[0], 400)
        self.assertEqual(req("/api/suggestions", user="stranger@test")[0], 403)       # same access as the other reads

    def test_prepublish_check_stops_a_risky_publish(self):
        path = os.path.join(niwa.garden.root, "Notes", "Risky.md")
        with open(path, "w") as f:
            f.write("---\ntitle: Risky\n---\nThe box is at 192.168.1.20.\n")
        niwa.garden.revision += "x"
        status, body = req("/publish", {"rel": "Notes/Risky.md", "on": "1"})
        self.assertEqual(status, 200)                                              # the check page, not a redirect
        self.assertIn("LAN or tailnet address", body)
        self.assertFalse(niwa.garden.get("Notes/Risky").published)
        os.remove(path)


def tearDownModule():
    SERVER.shutdown()
    shutil.rmtree(TMP, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
