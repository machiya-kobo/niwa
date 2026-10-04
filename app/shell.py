"""Niwa's page shell: Machiya's shared shell (vaultkit.shell with ui/machiya.css and machiya.js) as the
room `niwa` (seal 庭, green), plus what is Niwa's own: the tab glyphs, the PWA manifest and service worker, and the
/settings page. niwa.css keeps only the garden's own layout.

Rooms: the switcher lists MACHIYA_ROOMS (the stack sets it). Standing alone, it falls back to Niwa's own sister
settings (niwa.py sets BOARD_URL from NIWA_KONBINI_URL and KURA_URL from NIWA_KURA_URL); with neither, no switcher.
"""
import datetime
import hashlib
import os

from vaultkit import shell as house
from vaultkit.shell import e, prefs  # noqa: F401  (prefs: niwa.py reads the theme and text size with it)

STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
UI_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "vaultkit", "ui")
ICON_DIR = os.path.join(STATIC_DIR, "icons")
ICONS = set(n for n in os.listdir(ICON_DIR) if n.endswith((".png", ".svg"))) if os.path.isdir(ICON_DIR) else set()
GARDEN_HOST = ""    # niwa.py sets it from NIWA_HOST (gemini/gopher footer links); empty = no links
COLUMN_TITLES = {"backlog": "Backlog", "ready": "Ready", "wip": "WIP", "blocked": "Blocked / On Hold",
                 "done": "Done", "archived": "Archived"}
BOARD_URL = ""       # Konbini, e.g. https://konbini.example.net
KURA_URL = ""        # Kura (owner links to the full note)
STATUS = None        # niwa.py: a function returning the footer's {"text": …, "state": "ok|stale|down"}
ROOM = "niwa"
NAV = [("/", "garden", "Garden"), ("/stream", "stream", "Stream"), ("/tags", "tags", "Tags"), ("/queue", "queue", "Queue")]
# The phone's tab bar: Search third (phones have no search field in the top bar), Tags only on the desktop nav.
TABS = [("/", "garden", "Garden"), ("/stream", "stream", "Stream"), ("/search", "search", "Search"), ("/queue", "queue", "Queue")]


def static_path(name):
    """Where /static/<name> lives: Niwa's own files, or the vendored shared UI (machiya.css, machiya.js)."""
    if name in ("machiya.css", "machiya.js", "machiya-sw.js"):
        return os.path.join(UI_DIR, name)
    return os.path.join(STATIC_DIR, name)


def _hash(name):
    try:
        with open(static_path(name), "rb") as f:
            return hashlib.sha1(f.read()).hexdigest()[:10]
    except OSError:
        return "0"


STATIC_V = {n: _hash(n) for n in ("niwa.css", "niwa.js")}
STATIC_V.update(house.UI_VERSION)            # machiya.css / machiya.js / machiya-sw.js: the shared UI's own hashes
VERSION = hashlib.sha1("".join(sorted(STATIC_V.values())).encode()).hexdigest()[:10]


def static_url(name):
    if name in house.UI_VERSION:
        return house.ui_url(name)
    return "/static/%s?v=%s" % (name, STATIC_V.get(name, "0"))


def rooms():
    """The switcher's rooms: the stack's MACHIYA_ROOMS, else Niwa's own sister settings."""
    return house.rooms() or {k: v for k, v in (("konbini", BOARD_URL), ("kura", KURA_URL)) if v}


# -- PWA: manifest, service worker ------------------------------------------

APPS = {"niwa": dict(name="Niwa", start="/", desc="Niwa: a private digital garden grown from the vault")}
# Icons are named after the room key (niwa-*); the old garden-* names answer 301 to these, for home screens and caches
# that still ask for them.
OLD_ICON_PREFIX = "garden"
SHORTCUTS = [("Search", "/search", "Search the published notes"), ("Tags", "/tags", "Topic and area tags"),
             ("Random Note", "/random", "A published note at random")]   # the Stream shows the board: owner-only


def shell_urls(app):
    """What the service worker precaches (the exact URLs the pages link, versioned)."""
    return [static_url("machiya.css"), static_url("machiya.js"), static_url("niwa.css"), static_url("niwa.js"),
            "/static/icons/%s.svg" % app, "/static/icons/%s-192.png" % app, "/offline"]


def manifest(app, theme, headers=None, palette=None):
    """headers: the request's (Sec-CH-Prefers-Color-Scheme picks System's colours: house.manifest_colors)."""
    a = APPS[app]
    return {**{k: v for k, v in {
        "name": a["name"], "short_name": a["name"], "description": a["desc"],
        "id": "/", "start_url": a["start"], "scope": "/", "display": "standalone", "lang": "en",
        "categories": ["productivity", "education"],
        "icons": [
            {"src": "/static/icons/%s-192.png" % app, "sizes": "192x192", "type": "image/png"},
            {"src": "/static/icons/%s-512.png" % app, "sizes": "512x512", "type": "image/png"},
            {"src": "/static/icons/%s-maskable-512.png" % app, "sizes": "512x512", "type": "image/png",
             "purpose": "maskable"},
        ],
        "shortcuts": [{"name": name, "short_name": name, "url": url, "description": desc,
                       "icons": [{"src": "/static/icons/%s-192.png" % app, "sizes": "192x192", "type": "image/png"}]}
                      for name, url, desc in SHORTCUTS],
    }.items() if v is not None}, **house.manifest_colors(theme, headers, palette or house.palettes.DEFAULT)}


# Navigations the worker never stores: the network, else /offline.
NETWORK_ONLY = ["^/search$", "^/settings$", "^/random$", "^/signin$", "^/queue$", "^/stream$"]


def service_worker(app):
    """/sw.js: Machiya's shared worker core (ui/machiya-sw.js) configured for the garden. Notes (/n/) are kept for
    offline reading (the 200 most recently read; pinned ones, offline: true, for good, fetched ahead via
    /api/offline); search, settings, random, sign-in and the owner's queue and stream (unpublished notes, the board)
    are never stored, and an unpublished note's page answers no-store; the APIs are never touched."""
    return house.service_worker(VERSION, shell_urls(app), offline="/offline", bypass=["^/api/", "^/theme$"],
                                network=NETWORK_ONLY, notes={"match": "^/n/", "limit": 200},
                                pages=30, assetMatch=["^/a/"], assets=100, pins="/api/offline")


# -- the page ------------------------------------------------------------------

_SVG = ('<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" '
        'stroke-linejoin="round" aria-hidden="true">%s</svg>')
ICON = {    # Niwa's tabs; the garden is the house's niwa glyph
    "garden": house.GLYPH["niwa"],
    "stream": _SVG % '<path d="M2 8c3-3 5 3 8 0s5 3 8 0 3-3 4 0M2 16c3-3 5 3 8 0s5 3 8 0 3-3 4 0"/>',
    "tags": _SVG % '<path d="M3 12V4h8l9 9-8 8-9-9z"/><circle cx="7" cy="8" r="1.5"/>',
    "queue": _SVG % '<path d="M3 13l2-8h14l2 8v6H3zM3 13h5l2 3h4l2-3h5"/>',
}


def header(current, subtitle="", search=True, ctx=None):
    """The room's header: nav, the Garden search field (not on /search, which has its own), the switcher, the gear,
    and (signed in with the built-in sign-in) the person button to Settings' Account. ctx.who: niwa.py's
    Handler.ctx()."""
    tools = house.search_box("", "/search", "Search the Garden", "Search the Garden") if search else ""
    return house.header(ROOM, NAV, current, rooms(), subtitle, tools, who=getattr(ctx, "who", ""))


def footer(with_status=True):
    status = STATUS() if STATUS and with_status else None
    links = [("gemini://%s/" % GARDEN_HOST, "Gemini"), ("gopher://%s/" % GARDEN_HOST, "Gopher")] if GARDEN_HOST else []
    return house.footer(ROOM, status, [(FEED, "RSS")] + links)


FEED = "/feed.xml"
FEED_LINK = '<link rel="alternate" type="application/rss+xml" title="Niwa" href="%s">\n' % FEED   # autodiscovery


def page(ctx, what, body, current="", head="", status=True):
    """body holds the header and <main>; the footer and the tab bar are added here. what: the page's name, before the
    room's in <title> (shell.title: "Lantern - Niwa"; "" for the home page, "Niwa"). ctx.prefs_url (/api/prefs when
    the request has a principal) lets machiya.js sync theme and text size; ctx.who is the signed-in name.
    status=False: no status line in the footer (the precached /offline)."""
    return house.page(ctx, ROOM, house.title(ROOM, what), body + footer(status), TABS, current, links=rooms(),
                      head=FEED_LINK + head, stylesheets=[static_url("niwa.css")], scripts=[static_url("niwa.js")], icons=ICON,
                      prefs_url=getattr(ctx, "prefs_url", ""), who=getattr(ctx, "who", ""))


def message(ctx, heading, text):
    """A short page in the room's own header, nav and tabs (a write that wasn't saved)."""
    return page(ctx, heading, header("", ctx=ctx) + house.message(heading, text, [("/", "Go to the Garden")]))


def not_found(ctx, what):
    """The 404 page: vaultkit's not_found inside the normal header (search included), nav and tabs."""
    return page(ctx, "Not Found", header("", ctx=ctx) + house.not_found(ROOM, what))


def offline(ctx, app):
    """The precached /offline (vaultkit's offline): no status line, no search box, nothing about the network."""
    return page(ctx, "Offline", header("", search=False, ctx=ctx) + house.offline(ROOM), status=False)


def account_section(name):
    """Settings' Account rows for a principal signed in with the built-in sign-in: who, and a same-origin sign-out
    form (POST /signout)."""
    out = ('<div class="item"><span>Signed in as %s</span><form method="post" action="/signout">'
           '<button type="submit">Sign Out</button></form></div>' % e(name))
    return ("Account", [out], "Signing out ends the session on this browser. Paired devices stay signed in.")


def settings(ctx, version, status_text, vaultkit, signed_in=""):
    garden = ("Garden", [house.toggle("Link Previews", "linkPreviews", True), house.offline_row()],
              "Link Previews: hovering over a link to a note shows its stage and summary. Off, links just open. "
              "Offline Copies: the notes you read last (up to 200) stay on this device for reading without the "
              "network, and notes marked offline: true stay for good. Notes under Archive/ are never kept.")
    sections = [house.appearance_section(ctx, synced=bool(getattr(ctx, "prefs_url", ""))), garden, house.apps_section(ROOM, rooms(), {}),
                account_section(signed_in) if signed_in else None,
                house.about_section(ROOM, version, status_text, vaultkit)]
    return page(ctx, "Settings", header("", "Settings", ctx=ctx) + house.settings_page(sections, ROOM))


def ago(value):
    try:
        d = datetime.date.fromisoformat((value or "")[:10])
    except ValueError:
        return ""
    n = (datetime.date.today() - d).days
    if n <= 0:
        return "today"
    if n == 1:
        return "yesterday"
    if n < 14:
        return "%dd ago" % n
    if n < 60:
        return "%dw ago" % (n // 7)
    if n < 365:
        return "%dmo ago" % (n // 30)
    return "%dy ago" % (n // 365)
