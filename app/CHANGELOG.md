# Changelog

Niwa follows [SemVer](https://semver.org). Before 1.0, a new feature, a changed default or setting, or a changed API
field is a minor bump, and a fix or wording change is a patch. Settings are listed in the README.

## 0.5.1

Fixes from the 2026-10 security sweep.

- A vault image served from `/a/` (an SVG with script in it) is sandboxed (`Content-Security-Policy: sandbox`), so it can't read the owner's pages or post to Niwa when opened on its own; every response now carries `X-Content-Type-Options: nosniff`.
- A note in a `NIWA_PRIVATE_FOLDERS` folder is never published, whatever its `publish:` line says: not on the web, gemini, gopher or the feed, and "Publish" (and "Publish anyway") refuses it.
- A cross-site `POST /api/...` (a hostile page's form, with the tailnet login riding along) is refused; scripts that send no `Origin`, or an `Authorization` or `X-Access-Token` header, are unaffected.
- Gemini and gopher: control characters in titles, tags and echoed paths become spaces, so a title can't add a menu row or a link line.
- The link checker (and the Hister save) only connect to public addresses: any spelling of an inside address, a name that resolves inside, and every redirect hop are refused, and such a link is shown as unknown, never dead.
- The Hister client never follows a redirect (the owner's token rides on every call).
- Garden writes hold the git sync's lock, so a publish can't be lost to a conflict replay.
- Each listener caps its concurrent connections (web 64, gemini and gopher 32) and closes any connection open past 120 s (60 s).
- Start-up warns when `NIWA_AUTH=tailscale` (no identity file) listens on a non-loopback address.

## 0.5.0

- Settings follow the signed-in person (vaultkit 0.21.0, Machiya's `docs/contracts/prefs.md`). With `NIWA_AUTH=hister` and the sign-in helper, `/api/prefs` is the account's: Niwa forwards it with the caller's own credential, and a fresh browser's first page is drawn in the account's theme. In the Tailscale fallback there is no account (503) and the page keeps its local values.
- `/api/prefs` answers `{"v", "rev", "prefs", "updated"}` with an `ETag` (304 on a matching `If-None-Match`), and accepts only the schema's keys (`theme`, `palette`, `text_size`, `apps_hidden`, `niwa.link_previews`, ...); any other key is a 400. Niwa's own store answers the same way where there is no helper.
- Settings has the house order: Shared (Theme, Appearance, Text Size, Apps, with where they are kept), Garden, This Device (Use This Device's Size, Offline Copies), Account, About. Link Previews follows the person (`niwa.link_previews`).

## 0.4.13

- `MACHIYA_SSO_COOKIE` names the Hister sign-in cookie (default `machiya_sso`, unchanged), so a second stack on the same domain (the dev stack) can use its own (vaultkit 0.20.0).

## 0.4.12

- The Rooms menu's Machiya row reads "Machiya · home": the stack's front door; its status page moved to /status (vaultkit 0.19.1).

## 0.4.11

- `NIWA_AUTH=hister`: Hister's sign-in (through the hister-login helper) as Niwa's gate; when sign-in is unavailable the owner's tailnet login still gets in, with a banner (vaultkit 0.19.0). Off by default; `tailscale` is unchanged.

## 0.4.10

- `NIWA_HISTER_TOKEN_FILE`: the owner's Hister token, sent as `X-Access-Token` on every call to Hister (and to the `hister` command's environment, never its arguments), for the coming Hister sign-in. Unset sends nothing, as before.

## 0.4.9

- A "Machiya · status" row in the Rooms menu and a link from the footer's "Part of Machiya" to the stack's status page, and `GET /api/changelog` serves this changelog for its recent deploys (vaultkit 0.18.0).

## 0.4.8

- A search pill under the header on every page, at every width, as Shiori's: results appear as you type, Escape or the X puts the page back, and on a phone a magnifier submits (vaultkit 0.17.2). The Search tab and nav link are gone; the tab bar has its old tabs again.

## 0.4.7

- In the installed app on an iPhone the header's logo and title sit lower, clear of the band under the status bar that iOS draws soft; the phone header is pinned again (vaultkit 0.16.8).

## 0.4.6

- On a phone the header scrolls with the page instead of staying pinned (vaultkit 0.16.7): the installed app on iOS drew a pinned header soft. The Rooms menu's text meets AA contrast in every theme.

## 0.4.5

- No search field in the header at any width (vaultkit 0.16.4): Search is the third tab on a phone and the third link on a wide screen, and "/" opens the search page. 0.4.4 was tagged but never deployed.

## 0.4.4

- The header is solid on a phone (vaultkit 0.16.3), the same in every room; 0.4.3 was tagged but never deployed.

## 0.4.3

- On a phone the tabs are Garden, Stream, Search and Queue (then Rooms): Search is third, as in every room, and the header has no search field at phone width (vaultkit 0.16.2). Tags stays on the desktop navigation and in the links.

## 0.4.2

- The phone tab bar is more see-through, frosted glass like Shiori's (vaultkit 0.16.1). 0.4.1 was tagged but never deployed.

## 0.4.1

- On a phone the tab bar is a floating pill like Shiori's (vaultkit 0.16.0): it fits five tabs on any phone, the current tab sits on a raised pill, and it follows the light or dark variant as Shiori does.

## 0.4.0

- Machiya's identity file (`MACHIYA_IDENTITY_FILE`, vaultkit 0.10.0's `identity`): set, it replaces `NIWA_USERS`.
  Every request is resolved to a principal (a token, a Tailscale login or tagged node, a trusted proxy's header);
  pages and read APIs need the `niwa` `read` grant, `POST /api/suggest` needs `suggest`, and publishing, dismissing
  and the garden fields need `publish`. An agent no longer gets the owner's powers by sending a same-origin `Origin`
  without `X-Agent`; same-origin stays the guard against cross-site form posts. Events record the principal as
  `actor` and `X-Agent` as `agent`. No or a bad proof answers 401, a missing grant 403. `/api/status`'s full view
  is the owner's. Unset, nothing changes.
- `NIWA_AUTH=header` with `NIWA_AUTH_HEADER` (a trusted proxy's login header), with an identity file only; with one,
  `tailscale` and `header` refuse a non-loopback bind unless `NIWA_BIND_BEHIND_PROXY=1`. `NIWA_ACCEPT_APP_CAPS=1`
  knows Tailscale tagged nodes by their app capability.
- `NIWA_KONBINI_TOKEN_FILE`: Niwa's service token, sent to Konbini as `Authorization: Bearer` on every call.
- The built-in sign-in, with an identity file and `NIWA_SIGNIN=1` (vaultkit's `signin`): `GET`/`POST /signin` and
  `POST /signout` (same-origin only), the session cookie, and a 401 page in the browser that links to
  `/signin?next=`. Settings shows who is signed in and a Sign Out button.
- Shiori device pairing: `POST /api/pair` turns a one-time code from the identity CLI into a device token.
- Per-user preferences: `GET`/`PUT /api/prefs`, kept in `prefs.sqlite3` next to `NIWA_DB` (the `niwa` `read` grant;
  a PUT made with a cookie or login must be same-origin, one with a token needn't).
- `NIWA_PUBLIC_URL`: Niwa's web address, an origin with no path. `http://` turns off the session cookie's `Secure`
  and is the only origin the sign-in accepts there; its host joins the names `NIWA_AUTH=open` serves.
- Without an identity file `/signin`, `/signout` and `/api/pair` answer 404, as before. `/api/prefs` works there too
  (vaultkit 0.12's `identity.ambient`: the Tailscale login's preferences, or open mode's owner), and every page
  carries `<meta name="machiya-prefs">`, so theme and text size follow the person. Signed in, the header has a person
  button to Settings, Account.
- `/settings` is `Cache-Control: no-store`.
- Gemini and gopher open with the web's intro (a published `Garden.md`, else `NIWA_INTRO`) instead of a fixed
  "Notes from the vault.".
- `/feed.xml`: RSS 2.0 of the published notes, the 50 most recently tended first, behind the garden's gate;
  autodiscovery in every page's head and an RSS link in the footer.
- The icons are named after the room (`/static/icons/niwa*.svg|png`, which every page already asked for: the favicon
  and the iOS icon were 404); the old `garden*` names answer 301 to them. The manifest has `lang`, `categories` and
  shortcuts (Search, Tags, Random Note).
- vaultkit 0.13.0.

## 0.3.1

- A post body over 1 MiB is read and dropped (up to 16 MiB) before its 413, which now says `Connection: close`: a
  client still sending saw the connection reset instead of the answer.
- A remote URL's password with an `@` in it is redacted whole: `https://u:p@ss@host` showed `https://***@ss@host`.
- `NIWA_HOST` and `NIWA_ALLOWED_HOSTS` names are matched without case, a trailing dot or a port, on both sides:
  `name:8080` in the setting answered 403.
- The README says that with `NIWA_AUTH=open` a request without a `Host` header (an HTTP/1.0 client) gets 403.

## 0.3.0

- Gemini and gopher serve only the images a published note shows; an image only unpublished or private notes use
  was reachable there by its path.
- The gemini and gopher stream no longer names the owner's login for a suggestion made without `X-Agent`.
- `NIWA_AUTH=open` answers only to an IP address, `localhost`, `NIWA_HOST` or a name in the new `NIWA_ALLOWED_HOSTS`
  (a guard against DNS rebinding).
- `/api/status` shows the Konbini and Hister addresses and errors only to the owner (anyone else gets
  `{"on", "ok"}`), and credentials in a remote URL are redacted there and in the clone log line.
- A gemini client that connects and says nothing no longer holds up the others (the TLS handshake moved off the
  accept thread), and every listener drops a client that stalls for 30 seconds.
- Publishing a note without frontmatter answers 422 instead of closing the connection; a bad or oversized
  `Content-Length` answers 400 or 413.
- `/theme` sends the browser back only to a page on this site.
- Link rot checks and archives only the links published notes still have, finds a dead link whose URL has a `&`,
  and escapes the archived-copy addresses it writes into pages. Pages read the link table once per change.

## 0.2.3

- The gopher listener starts after a restart within a minute of the last connection (it sets `SO_REUSEADDR`, as the
  gemini listener does).
- The gemini certificate is created on systems without an OpenSSL configuration file (a clean NetBSD).
- `NIWA_GOPHER_PUBLIC_PORT` sets the port the gopher menus advertise (default 70; the listener stays on 7070).
- `NIWA_KONBINI_API_URL` sets the address Niwa's server calls Konbini on, when it differs from the one browsers use
  (default `NIWA_KONBINI_URL`).
- Two-line callouts (`> [!tip]` and the text on the next line) show their text, and an escaped table alias
  (`[[Note\|alias]]`) links to the note (vaultkit 0.9.5 and 0.9.6).
- The README has a Quickstart for a container (podman or docker) and for Debian, OpenBSD, FreeBSD and NetBSD, with a
  sample vault (`sample-vault/`, `tools/demo-vault`), screenshots, and `tools/quickstart-test`, which runs the README's
  commands from a fresh clone.

## 0.2.2

- The offline banner ends "Check your network or VPN."
- The README explains the gopher port mapping (menus point at port 70, the container listens on 7070), says what
  Machiya, a room and the owner are, and notes that any reverse proxy works if it sets `Tailscale-User-Login`.
- Internal cleanup: unused code removed, and docstrings describe what the code does.

## 0.2.1

- The gemini and gopher streams show only garden events about published notes; the board (Konbini) appears only in
  the owner's web stream.
- The gemini landing page reads "Notes from the vault."
- `SECURITY.md` puts the small-web stream in scope; `THIRD_PARTY_NOTICES` lists Python Markdown, PyYAML and the
  Debian packages the image installs; the README install example sets up the deploy key first and documents
  `NIWA_COLD_MAP`.

## 0.2.0

**Features**
- `GET /api/suggestions[?days=60]` lists the open suggestions (a note an agent suggested that is still unpublished),
  newest first, as `{"suggestions": [{"path", "reason", "agent", "date"}], "days": 60}`. `days` is clamped to 1 to 365.
  It needs the same access as the other pages.
- `NIWA_PRIVATE_FOLDERS` names top-level folders whose notes never appear in the queue; the pre-publish check refuses
  them and warns about links to them. Default: none.
- `NIWA_IGNORE_AUTHORS` names git authors (bots) whose commits don't count as "tended" in the stream. Niwa's own
  author is always ignored.
- `NIWA_SKIP_HOSTS` lists hosts the link checker never visits, on top of `localhost`, `*.ts.net` and every private,
  loopback or link-local IP address. `NIWA_LINKS_USER_AGENT` sets its User-Agent (default `niwa-links/1`).
- `NIWA_INTRO` sets the landing page's intro text while no `Garden.md` is published (default: "Notes from the vault,
  shared as they grow.").
- `NIWA_HISTER_SAVE` lets the link checker index a live link into Hister; by default Hister is only looked up.
- `NIWA_ARCHIVE` is `none` by default: nothing is sent to the Wayback Machine. `wayback` asks it for snapshots and
  swaps a dead link for its snapshot. Links are checked for life either way.
- `NIWA_HOST` names the gemini certificate and the gopher menus. Unset, they name `localhost`, the footer has no
  Gemini or Gopher links, and Niwa logs a warning. An existing certificate is kept.
- `NIWA_REPO_SUBDIR` is the folder that holds the notes; by default the repo root. `TZ` sets the stream's time zone;
  the default is `UTC`.
- With `MACHIYA_SOURCE_URL` set, the footer and About link to the source code (vaultkit 0.9).

**Upgrading from 0.1.x:** these defaults changed. Set `NIWA_ARCHIVE=wayback` to keep asking the Wayback Machine,
`NIWA_REPO_SUBDIR=<folder>` if the notes are not at the repo root, `TZ=<zone>` for your local days,
`NIWA_PRIVATE_FOLDERS` for folders that must stay out of the queue, `NIWA_HOST` for the
certificate name, and `NIWA_LINKS_USER_AGENT` for the User-Agent you want sites to see.

**Fixes**
- Private address ranges are matched against IP literals only, so a real host such as `100.example.com` is checked;
  `172.16.0.0/12` and `100.64.0.0/10` addresses are skipped.
- Two suggestions for one note within the same second resolve to the later one.
- The image exposes only the ports it uses (8080, 1965, 7070).

## 0.1.0

The garden for a Markdown vault (a Git repo), on the web, gemini (1965) and gopher (7070). Notes with
`publish: true` appear; only the owner publishes, from the web UI, and agents may only suggest. Growth stages,
confidence, pins, backlinks, topic maps, the queue, the stream and the pre-publish check; link rot with Wayback and
Hister copies; `NIWA_AUTH` (`tailscale` or `open`) and `NIWA_BIND` for running with or without Tailscale; borrowing a
shared vault copy (`NIWA_REPO_REFERENCE`, `NIWA_REPO_SPARSE`); settings from an env file.
