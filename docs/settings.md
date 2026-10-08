# Settings

[Back to the README](../README.md)

Most installs set a handful of the settings under [Basics](#basics). The rest are under [Advanced](#advanced), by topic: where Niwa runs, [Hister sign-in](#sign-in-hister), [the identity file](#sign-in-identity-file-proxy-header-open-mode), the [public garden](#public-garden), [link checking](#link-checking) and [the Machiya stack](#the-machiya-stack-and-its-apps).

## Basics

What a normal install sets. Everything else has a default that works.

| Env | Default | |
|---|---|---|
| `NIWA_REPO_URL` | — | vault repo to clone once (ssh for writes; set `GIT_SSH_COMMAND` for the key). Unset: use `NIWA_REPO_DIR` as it is |
| `NIWA_REPO_SUBDIR` | — | the vault folder in the repo that holds the notes. Unset: the repo root |
| `NIWA_HOST` | — | the name in the Gemini certificate and Gopher menus, and the footer's Gemini and Gopher links. Unset: `localhost`, no footer links, and a startup warning |
| `NIWA_AUTH` | `tailscale` | `tailscale`: your pages and writes need a `Tailscale-User-Login` in `NIWA_USERS`. `open`: no login (a startup warning), for localhost or a trusted LAN; it answers only a `Host` that is an IP address, `localhost`, `NIWA_HOST`, `NIWA_PUBLIC_URL`'s host or in `NIWA_ALLOWED_HOSTS` (against DNS rebinding). `header`: with `MACHIYA_IDENTITY_FILE` only, a trusted proxy's login header (`NIWA_AUTH_HEADER`). `hister`: Hister's sign-in (the next row but one). In every mode form posts must be same-origin and agents may only suggest. Anything else refuses to start |
| `NIWA_USERS` | — | allowed `Tailscale-User-Login`s; `*` = anyone; unset = nobody (`/api/status` is open) |
| `NIWA_PRIVATE_FOLDERS` | — | top-level folders of the notes (comma-separated, e.g. `Private,Inbox`) whose notes are never queued and never published: a note there with `publish: true` is not served on the web, Gemini, Gopher or the feed, "Publish" refuses it (no "publish anyway"), and the pre-publish check warns about links to them. Unset: no folder is special |
| `NIWA_SCAN_DENY` | — | words or names (comma-separated: hostnames, people, places) that must never be published. The pre-publish scan counts each one as an error, so a note with one stays out of the garden until you publish it anyway. Matched whole, ignoring case |
| `NIWA_QUEUE_FOLDERS` | — | folders (comma-separated, e.g. `Garden`) the Queue lists notes from, plus held-back notes and anything an agent suggested. Unset: every unpublished note. See [Writing for the garden](writing.md) |
| `NIWA_LONG_WORDS` | `800` | a note over this many words (the part you publish) gets a "long" warning; the publish button then says "Publish with 1 warning". `0` turns it off |
| `NIWA_ARCHIVE` | `wayback` | `wayback` asks the Wayback Machine for a snapshot of each link in the published notes (it sends those URLs to archive.org): a live link gets an "archive.org" link beside it, and a dead link points at its snapshot, on the web, Gemini and Gopher. `none` never contacts archive.org; links are still checked for life and snapshots already recorded still show. Any other value counts as `none`, with a startup warning |
| `NIWA_INTRO` | `Notes from the vault, shared as they grow.` | the landing page's intro while no `Garden.md` is published, on the web, Gemini and Gopher: plain text (HTML-escaped), one line. Publish `Garden.md` to write your own (Gemini and Gopher show it too) |
| `TZ` | `UTC` | the time zone for the stream's days and "this week" counts, e.g. `Europe/Berlin` |

## Advanced

### Where Niwa runs

| Env | Default | |
|---|---|---|
| `NIWA_PORT` | `8080` | web listener; Gemini 1965, Gopher 7070 |
| `NIWA_BIND` | `0.0.0.0` | the IPv4 address all three listeners bind (web, Gemini, Gopher). Behind `tailscale serve` on a native install, bind `127.0.0.1`: on a public bind anyone who reaches the port could send the `Tailscale-User-Login` header, so `NIWA_AUTH=tailscale` or `header` (and `hister` with the tailscale fallback) refuse to start on a non-loopback bind without `NIWA_TRUSTED_PROXIES` |
| `NIWA_DB` | `/data/niwa.sqlite3` | link records; the Gemini certificate and `prefs.sqlite3` (per-user preferences, 0600) sit next to it |
| `NIWA_REPO_DIR` | `/data/repo` | the clone |
| `NIWA_POLL` | `60` | seconds between pulls |
| `NIWA_GIT_NAME`, `NIWA_GIT_EMAIL` | `garden`, `garden@niwa` | commit author |
| `NIWA_GOPHER_PUBLIC_PORT` | `70` | the port the Gopher menus advertise; the listener itself is on 7070, so map the public port to it |
| `NIWA_IGNORE_AUTHORS` | — | comma-separated git author names of bots that commit to the vault: their commits don't count as "tended" in the stream (Niwa's own `NIWA_GIT_NAME` is always ignored) |

### Sign-in: Hister

| Env | Default | |
|---|---|---|
| `NIWA_AUTH=hister`, `NIWA_AUTH_URL`, `NIWA_AUTH_SIGNIN_URL`, `NIWA_HISTER_USERS`, `NIWA_AUTH_FALLBACK`, `NIWA_AUTH_ACCEPT_ORIGINS`, `MACHIYA_COOKIE_DOMAIN`, `MACHIYA_SSO_COOKIE` | — | Hister sign-in, with `NIWA_PUBLIC_URL` (required) as the way back. `NIWA_AUTH_URL`: the sign-in helper's internal address (`http://hister-login:8081`); unset, Niwa runs on the Tailscale login alone, with a warning. `NIWA_AUTH_SIGNIN_URL` (required): the helper's public sign-in page. `NIWA_HISTER_USERS` (required, never `*`): the Hister usernames let in. `NIWA_AUTH_FALLBACK`: `tailscale` (the default: the `NIWA_USERS` logins get in while sign-in is down, never `*`) or `none` (503 then; needs `NIWA_AUTH_URL`). Niwa keeps its own host-only cookie (`__Host-machiya_sso_niwa`), set after one silent trip through the helper (`/machiya/callback`). Non-browsers send a room token (`Authorization: Bearer mht_…`) naming Niwa. `NIWA_AUTH_ACCEPT_ORIGINS`: other origins whose sessions Niwa accepts (Shiori's hosted pages). `MACHIYA_SSO_COOKIE`: the cookie name's base (default `machiya_sso`), the same as the helper's. `MACHIYA_COOKIE_DOMAIN`: the domain of the older shared `machiya_sso` cookie, still read and cleared until the helper stops setting it. Refused at start: a missing setting, a `*`, or an identity file as well |
| `NIWA_PUBLIC_URL` | — | your own Niwa's address, an origin with no path (`https://niwa.example`, `http://192.168.1.5:8080`); anything else refuses to start. With an identity file, the sign-in, sign-out and preference writes accept it as same-origin. `http://` means plain http: the session cookie isn't `Secure`, and only this origin counts. Unset: https and the request's own `Host`; over plain http the sign-in then refuses. Its host is also served with `NIWA_AUTH=open` |
| `NIWA_BIND_BEHIND_PROXY` | — | `1` is implied by `NIWA_TRUSTED_PROXIES`: set that instead. On its own it no longer lets a header mode bind a non-loopback address, because it can't tell the proxy from another container on the network |
| `NIWA_TRUSTED_PROXIES` | — | addresses or CIDRs (comma-separated, e.g. `10.210.4.2/32`) of the proxies in front of the web port. Set, an identity header (`Tailscale-User-Login` and Tailscale's others, `Remote-User`, `NIWA_AUTH_HEADER`) counts only on a connection from one of them; from anyone else it is ignored, so the request is anonymous. Required on a non-loopback bind in every mode that believes a login header (`tailscale`, `header`, `hister` with the tailscale fallback): Niwa refuses to start without it. On `127.0.0.1` it can stay unset: headers then count from any peer, as before. Doesn't touch the public garden, which reads no identity header |

### Sign-in: identity file, proxy header, open mode

| Env | Default | |
|---|---|---|
| `MACHIYA_IDENTITY_FILE` | — | Machiya's identity file ([`docs/identity.md`](https://github.com/machiya-kobo/machiya/blob/main/docs/identity.md)): people, agents and services with grants, replacing `NIWA_USERS`. Pages and read APIs need the `niwa` `read` grant, `POST /api/suggest` needs `suggest`, and publishing and the garden fields need `publish` (the owner has all). No or a bad proof is 401, no grant 403. Mount the file's **directory** read-only (the CLI replaces the file), with its `session_key_file` beside it |
| `NIWA_SIGNIN` | — | `1`, `on`, `true` or `yes`: with an identity file, the built-in sign-in. `/signin` takes a name and password (set with `python3 -m vaultkit.identity passwd NAME`) and sets the `machiya_session` cookie (shared across rooms with `MACHIYA_COOKIE_DOMAIN`). A browser without a session gets a 401 page linking to it, and Settings shows Sign Out. Unset: `/signin` is 404 |
| `NIWA_AUTH_HEADER` | — | with an identity file and `NIWA_AUTH=header`: the trusted proxy's login header (`Remote-User`, …), matched against each principal's `proxy` logins. `header` without an identity file refuses to start |
| `NIWA_ACCEPT_APP_CAPS` | — | `1`: with an identity file, a Tailscale tagged node (an agent's machine) is known by the app capability `tailscale serve --accept-app-caps=github.com/machiya-kobo/cap/identity` forwards. Only where Serve (Tailscale v1.92 or later) forwards and strips that header; an older one passes a client's own copy through |
| `NIWA_ALLOWED_HOSTS` | — | with `NIWA_AUTH=open`: more names (comma-separated) the web UI answers to besides IP addresses, `localhost`, `NIWA_HOST` and `NIWA_PUBLIC_URL`'s host, e.g. a LAN name. Names match without case, port or a trailing dot (`Box.lan:8080` is `box.lan`). A request with no `Host` header (an HTTP/1.0 client may send none) gets 403 |

### Public garden

| Env | Default | |
|---|---|---|
| `NIWA_PUBLIC_PORT` | — | the public garden's port (for example `8081`): a read-only website for anyone, with only the published notes. Unset: off |
| `NIWA_GARDEN_URL` | — | the public garden's address, an origin with no path (`https://garden.example`): its feed and links use it, never the request's `Host`. Required with `NIWA_PUBLIC_PORT`; your own pages link each published note's public page |
| `NIWA_PUBLIC_BIND` | `NIWA_BIND` | the address the public garden binds, when it differs from your own listeners' |
| `NIWA_PUBLIC_NOINDEX` | — | `1`, `on` or `true`: ask search engines not to index the public garden (`robots.txt` disallows all, `noindex` on every page). Unset: indexable |

### Link checking

| Env | Default | |
|---|---|---|
| `NIWA_LINKS_USER_AGENT` | `niwa-links/1` | the link checker's User-Agent (add a contact URL for the sites it checks) |
| `NIWA_SKIP_HOSTS` | — | host names (comma-separated; each matches itself and its subdomains) the link checker never visits, on top of `localhost`, `*.ts.net` and every private, loopback or link-local IP address |
| `NIWA_COLD_MAP` | — | optional: the URL of a JSON map of static page snapshots, `{"urls": {norm(url): {"snapshot", "date"}}}` (keys from `app/urlnorm.py`), used as the owner's private copy of a link |
| `NIWA_HISTER_SAVE` | — | `1`, `on` or `true`: link rot may index a live link into Hister when Hister doesn't have it. Unset: Hister is only looked up (the owner's copy is shown), never written to |

### The Machiya stack and its apps

| Env | Default | |
|---|---|---|
| `NIWA_REPO_REFERENCE` | — | in the Machiya stack: the stack's vault mirror, mounted read-only at the same absolute path. Niwa borrows its objects, so its own clone keeps only its own commits. Unset: a full clone of its own |
| `NIWA_REPO_SPARSE` | — | with a reference: the paths to check out (cone), e.g. `notes,.garden,.board` (the notes, Niwa's events, older events from a shared board). Unset: everything |
| `MACHIYA_ROOMS` | — | the Rooms switcher, `shiori=https://…,konbini=…,niwa=…,kura=…,hister=…,searxng=…,machiya=…` (the stack sets it; `machiya=` is the stack's landing page: a "Machiya · home" row and the footer's "Part of Machiya" link). Unset: the switcher shows Konbini and Kura from the two settings above, or nothing |
| `MACHIYA_SOURCE_URL` | — | where the source code is published: a "Source code" link in the footer and About, as the AGPL asks of a networked service |
| `NIWA_KONBINI_URL`, `NIWA_KURA_URL` | — | Konbini and Kura, both optional: the addresses browsers follow |
| `NIWA_KONBINI_TOKEN_FILE` | — | a file with Niwa's token for Konbini, sent as `Authorization: Bearer` (with `X-Agent: niwa`): a room token (`mht_…`, from the sign-in helper or `hister_login.py token mint --rooms konbini`) when Konbini uses Hister sign-in, or an identity token (`python3 -m vaultkit.identity token mint niwa`). Never logged. A file with no token refuses to start |
| `NIWA_KONBINI_API_URL` | `NIWA_KONBINI_URL` | the address Niwa's own server calls Konbini on, when it differs from the one browsers use (in a container stack: `http://konbini:8081` inside, `http://localhost:8081` outside) |
| `NIWA_HISTER_URL`, `NIWA_HISTER_PUBLIC` | — | Hister (optional): the owner's private link copies and the stream's reading line; `NIWA_HISTER_PUBLIC` is the address the owner's browser uses for links to it |
| `NIWA_HISTER_TOKEN_FILE` | — | the file with your Hister token (first line), sent as `X-Access-Token` and to the `hister` tool in its environment (never on its command line). Re-read when the file changes; never logged or shown in `/api/status`. A file with no token stops startup |
