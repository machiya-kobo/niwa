# Changelog

Niwa follows [SemVer](https://semver.org). Before 1.0, a new feature, a changed default or setting, or a changed API
field is a minor bump, and a fix or wording change is a patch. Settings are listed in the README.

## 0.14.1

Hardening from CodeQL's review (nothing was exploitable).

- The `/theme` redirect builds its target with `websafe.location`: a local path, percent-encoded, never `//host` or `/\host`. It no longer depends on `urlsplit` dropping CR and LF from a folded Referer.
- Every response header, cookies included, goes through `websafe.header_value` before anything is written, on the owner's and the public port. A CR, LF, NUL or other control character in a header value now gives a plain 500 and never a second header.

## 0.14.0

vaultkit 0.29.0 (the sign-in hardening, owner decisions 2026-10-08).

- **Remote images load on a click.** An image from another site in a note is a placeholder (its alt text, its address and a Load image button) on the web pages, the owner's and the public garden's, so opening a note no longer tells that site anything. Images from the vault are unchanged. Gemini and Gopher are text and are unchanged.
- The Hister sign-in is told the peer's address, so the Tailscale fallback believes the login header only from `NIWA_TRUSTED_PROXIES` inside vaultkit too, not only in Niwa's own header stripping.
- A `class` in a note's HTML survives only when it is one vaultkit allows (`task`, `wikilink`, `seed`, `mermaid`, `language-*`). All 27 notes of the sample vault render byte for byte as before.

## 0.13.5

vaultkit 0.28.0: the index is faster and is built aside, then put in place at once, so a request during a re-index never sees notes without their links. A re-index after one commit on a 1,500-note vault takes 305 ms instead of 714 ms, and the longest wait a visitor sees during a resync dropped from 841 to 101 ms. The "tended" dates are unchanged (checked against the sample vault and a 1,500-note vault with 300 commits). No change to the app.

## 0.13.4

A public image, and a pinned build. Each signed release tag now builds `ghcr.io/machiya-kobo/niwa:<version>` (and `:latest`) for amd64 and arm64 on GitHub Actions, and signs it with cosign (docs/install.md). The Dockerfile's base images (Python and the Hister CLI) are pinned by digest. No change to the app.

## 0.13.3

vaultkit 0.27.4: a hovered, unselected filter pill fills with 24% of its colour over the raised colour, and its text and outline take a hover shade that reads at 4.5:1 on that fill in every theme. No markup change.

## 0.13.2

vaultkit 0.27.3: an unselected filter pill lifts onto the raised colour under the pointer, in its panel shade, readable in every theme (0.13.1's 26% fill left most colour pairs under 4.5:1; 0.13.1 was never deployed). No markup change.

## 0.13.1

vaultkit 0.27.2: an unselected filter pill fills with 26% of its colour under the pointer (the landing page's All, Notes, Projects and Maps). Niwa has no sidebar, selectable rows or tabbed lists, so `.sidehead` and `.rows` are vendored but unused. No markup change.

## 0.13.0

A performance pass, and round 2 of Shiori's look (vaultkit 0.27.1). No settings or API change.

**Faster** (1,500-note vault, 424 published, 300 commits of history, on this VM):
- The Queue scanned every unpublished note on every view: 490 to 760 ms, and 640 KB of HTML. The scan runs once per note text now, so the view takes about 100 ms (the first view after a start still scans: about 640 ms).
- A re-index after a pull ran once for every request that arrived during it, in the request path: eight visitors saw up to 8 s and kept the server busy for 13 s of CPU. One request-independent re-index now runs in the sync thread, and anyone who asks meanwhile waits for that one (the worst wait was 0.84 s). The new revision's holds are worked out before anyone sees its notes.
- Pages, the feeds, the stylesheet and scripts are gzipped for a client that accepts it: the Queue is 59 KB instead of 674 KB, the landing page 24 KB instead of 165 KB, the Stream 9 KB instead of 72 KB. Mermaid (5.4 MB) goes out as 1.6 MB and is compressed once, not on every request.

**Looks** (Shiori's result card, section headings and header from vaultkit 0.27):
- Notes in the garden, search results, the Queue's rows and the topic maps are cards: a title in the garden's green, a snippet, a meta row with the chips. The Stream's Konbini rows are tinted cards of the same shape. Plain lists (Linked From, Nearby, Links) stay rows.
- Section headings are Title Case as written ("Topic Maps", "Linked From", "This Week"); the Stream's day and event labels lose their capitals-and-spacing style too.
- The current page in the header is a raised pill, with no underline.

## 0.12.0

From the pre-launch security review, and a pass over the README and install page.

- **Refuses to start on a public bind without `NIWA_TRUSTED_PROXIES`.** `NIWA_AUTH=tailscale` or `header`, and `NIWA_AUTH=hister` with the tailscale fallback (its default), believe a login header. On a bind other than `127.0.0.1` anyone who reaches the port could send it, publish writes included, so Niwa now exits unless `NIWA_TRUSTED_PROXIES` names the proxy (like `10.210.4.2/32`), as Kura and Konbini do. It used to start with a warning. `NIWA_BIND_BEHIND_PROXY=1` alone no longer suffices, since it can't tell the proxy from another container on the network. `NIWA_AUTH=open` is unchanged. **Upgrade note:** a container or LAN install on the default bind that used the tailscale gate must set `NIWA_TRUSTED_PROXIES` or bind `127.0.0.1`.
- Log lines no longer carry the query string (search terms, sign-in codes), on the owner's listeners and the public garden.
- The image runs as `USER 1000:1000`.
- vaultkit 0.26.3 (link chips and chips thicken their outline on hover instead of filling).
- The Quickstart and the container and BSD runs set `NIWA_GOPHER_PUBLIC_PORT=7070`, so the Gopher menus link to the port that listens. README and install page tightened.

## 0.11.1

vaultkit 0.26.2: chips are outlined in their colour on no fill, as Shiori draws them. A soft fill behind a text colour pulled it under 4.5:1 in most themes (Niwa's audit of 0.11.0); only the current pill is filled now. Link chips keep a light fill on hover. No markup changes.

## 0.11.0

Shiori's look, shared by every Machiya app (machiya's docs/style-guide.md), with vaultkit 0.26.1 vendored. Niwa keeps its own: airy, a 68ch measure, stages as seasons, the garden's green.

- **Filter pills.** The landing page's All, Notes, Projects and Maps are pills (the shared `.pills`), the current one filled, with counts. The Queue has no filter row and gets none.
- **Chips.** Stages, board columns, the Queue's Clean, Error and Warning counts, the claim and the suggestion badges are the shared state chips. Links that open something (Board, Blog Post, View in Kura, Public Page, Garden, Archived Copy, Private Copy) are outlined link chips in the colour of what they open.
- **Tinted rows.** In the Stream, what comes from Konbini (the Now rows and the project entries) is tinted and says "Card · Konbini". Garden events, system lines and reading lines stay plain. The public garden has none of this.
- **Icons.** `favicon.ico` (16, 32 and 48 px) and `niwa-small.svg`, the sprout with the baseline dropped and the stem and leaves bolder, so the tab icon reads at 16 px. `/favicon.ico` is served by the owner's pages and the public garden. The home-screen, manifest and header icons were already the same sprout.
- Niwa's own CSS for the type chips, count badges, stage, column and check badges and move labels is gone.

## 0.10.1

The owner's choices for the short-post features, replacing 0.10.0's comment markers and 1,500-word default. The comment markers never published anything the owner wrote: nobody had used them.

- An excerpt is the section under a heading called `Garden` (with its sub-sections), plus an `Updates` section. It replaces the `<!-- garden -->` comment markers of 0.10.0. A note with no `Garden` heading publishes whole. See docs/writing.md.
- `NIWA_LONG_WORDS` defaults to 800 (was 1,500).

## 0.10.0

Short, focused posts (owner request, 2026-10-07): the notes in a vault are long, and a garden is short posts with small updates. See docs/writing.md.

- **A garden folder for the Queue.** `NIWA_QUEUE_FOLDERS` limits the Queue to those folders, plus held-back notes and what agents suggested. Unset, nothing changes.
- **Word counts.** Each Queue row and the owner's note page show the note's length.
- **A length warning.** A note over `NIWA_LONG_WORDS` (default 1,500; `0` turns it off) gets a "long" warning. It informs, it never blocks.
- **Excerpts.** The text between `<!-- garden -->` and `<!-- /garden -->` is all the garden publishes of a note: the web, Gemini, Gopher, the feed, search, the scan, link checking and the word count see only that. A secret outside the markers doesn't hold the note back. A note with no marker publishes whole.
- **Short updates.** Dated bullets (`- 2026-10-07: text`) under an `Updates` heading show in the Stream, on the web, the public garden, Gemini and Gopher.

## 0.9.1

- The queue's "Review" is a link to the note (which shows every finding and holds the Publish button) instead of a form post. A clean note still has its Publish button.
- docs/settings.md groups the 44 settings into Basics (the ten most installs set) and Advanced, by topic. No setting changed.

## 0.9.0

An owner review of how Niwa works, to keep it simple.

- **The landing page is one list.** Your intro, the topic maps, then every note once, the most recently tended first, each with its stage. "Start here", "Recently tended", "Seedlings", "Needs tending", "Everything" (the full list grouped by stage) and "Projects in bloom" are gone: they listed the same notes up to four times. The type chips still filter the list.
- **The Tend form is the stage.** Confidence and the "start here" pin have no controls and no badge. A note's `confidence` and `garden_pin` lines stay as they are, and saving the stage never removes them. (`POST /meta` still sets them for a script that sends them.)
- **A note shows what publishing would accept.** Open a note that isn't in the garden and each scan finding is shown in full and highlighted in the text, and the button says what it accepts: "Publish with 1 error and 1 warning" (one click, no second page). It replaces "Publish anyway". A held-back note shows the same.
- The queue's held-back badge says "held back by the scan".

## 0.8.4

- vaultkit 0.25.2: code blocks, inline code and the search field's text use the menu text color, so they pass 4.5:1 contrast in the light themes (3.99 in Tokyo Night Day and 4.39 in Solarized Light before).

## 0.8.3

- vaultkit 0.25.0: accents on raised panels (Settings groups, the Rooms menu, toasts, code blocks) use their panel shades, so links and accent text there reach 4.5:1 in every palette; About says "License".
- Niwa's own raised panels (topic-map cards, link previews, the Tend row) take the same panel shades.

## 0.8.2

- vaultkit 0.24.0: the footer's status line, the phone tab bar's labels and the Settings group text pass 4.5:1 contrast in every palette.

## 0.8.1

- `NIWA_TRUSTED_PROXIES` (addresses or CIDRs, comma-separated): when set, an identity header (`Tailscale-User-Login` and Tailscale's others, `Remote-User`, `NIWA_AUTH_HEADER`) counts only on a connection from one of those addresses. From any other peer it is dropped before the gate reads it, so the request is anonymous. Unset, nothing changes.

## 0.8.0

- **Public garden** (off by default): `NIWA_PUBLIC_PORT` and `NIWA_GARDEN_URL` turn on a second, read-only website for anyone, with the published notes, their tags and images, the stream of garden events, search (60 a minute per address) and the feed. It has no sign-in, queue, settings or writes, reads and sets no cookies, trusts no identity header, and shows nothing from Konbini, Kura or Hister. Your own address and its sign-in are unchanged, and its note pages link each published note's public page. Search engines may index it; `NIWA_PUBLIC_NOINDEX=1` asks them not to. `NIWA_PUBLIC_BIND` binds it somewhere else.
- **Held back until acknowledged (changes Gemini, Gopher and the feed too):** a `publish: true` note whose pre-publish scan finds an error (an address, a key, a token, or a word from the new `NIWA_SCAN_DENY`) is now kept out of every channel, the web, the public garden, Gemini, Gopher and the feed, until you press "Publish anyway" on its page. That records exactly those findings in Niwa's own database (never the vault); a new finding, or a `publish: true` written outside Niwa, holds the note again. **After upgrading**, notes published with "Publish anyway" before 0.8.0 are held until you acknowledge them once more: the Queue lists them under Held Back.
- The scan also warns about tailnet names (`*.ts.net`) and email addresses.
- **archive.org by default:** `NIWA_ARCHIVE` now defaults to `wayback`, so Niwa sends the published notes' external links to the Wayback Machine (archive.org). A live link keeps pointing at the original with a small "archive.org" link to its snapshot beside it, on your pages and the public garden; a dead link points at its snapshot as before. Gemini and Gopher add the snapshot as a second link line, mark a dead link "(dead link)", and give bare URLs a link line too. Set `NIWA_ARCHIVE=none` to keep links away from archive.org.

## 0.7.0

vaultkit 0.23.0 (the house Settings order, Machiya's `docs/ui.md` "Settings").

- Settings run Appearance (Theme, Mode, Text Size, Use This Device's Size under it), Garden, Rooms, Account, About. Offline Copies moved into Garden, so there is no This Device section; no setting's key changed.
- Shorter copy: the Settings footers, the Queue and Stream intros, the empty garden, and the private-folder error (no setting name).

## 0.6.1

- Pull to refresh in the installed app moves the page content (it springs back, and holds with a spinner while it reloads) instead of an overlay (vaultkit 0.22.1).

## 0.6.0

vaultkit 0.22.0 (the sweep's shared fixes, Machiya's `docs/vaultkit.md`, "adopting websafe").

- Sign-in cookies are host-only and per room: Niwa sets `__Host-machiya_sso_niwa` (a room session, good here only, from a one-time code at `/machiya/callback`) instead of reading a cookie shared across the tailnet, and its loop guard is `__Host-machiya_sso_niwa_try`. The older shared `machiya_sso` and Hister's own token are still read until the sign-in helper stops setting them. Callers that aren't browsers can send a room token (`Authorization: Bearer mht_…`) that names Niwa. `NIWA_AUTH_ACCEPT_ORIGINS` lists other origins whose room sessions Niwa also accepts.
- `NIWA_KONBINI_TOKEN_FILE` holds a room token for Konbini (made on the helper's sessions page) instead of Hister's owner token; nothing changes in how Niwa sends it.
- Vault images are served with vaultkit's `websafe.asset_headers` (sandboxed; `X-Frame-Options`, `Referrer-Policy` and `nosniff` on every non-HTML response). The link checker uses `websafe.public_opener` (IPv6 forms of inside addresses, NAT64 and 6to4 included); the Hister and Konbini clients use `websafe.token_opener` (no redirect, ever); the garden writer uses `safe_path` (no symlink anywhere in the path).
- vaultkit refuses symlinks in the vault and limits frontmatter; menus close on Back and a pulled-down page refreshes in the installed app.
- `markdown` 3.11 or later is required (older ones run out of memory on one note under Python 3.13): the Dockerfile, the README and the BSD steps (a venv that keeps the packages' PyYAML and pips `markdown`) say so.

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
