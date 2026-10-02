# Changelog

Niwa follows [SemVer](https://semver.org). Before 1.0, a new feature, a changed default or setting, or a changed API
field is a minor bump, and a fix or wording change is a patch. Settings are listed in the README.

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
