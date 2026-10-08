# Niwa

[Machiya](https://github.com/machiya-kobo/machiya) is a set of small self-hosted apps for finding what you've read: your pages ([Hister](https://github.com/asciimoo/hister)), the web ([SearXNG](https://github.com/searxng/searxng)), your notes ([Obsidian](https://obsidian.md)) and your code ([Forgejo](https://forgejo.org) or [GitHub](https://github.com)).

Niwa (庭, garden) is Machiya's digital garden. Publish the notes you choose from your Obsidian vault to the Web. It's also a Gemini capsule and a Gopher hole.

<p align="center">
<a href="https://machiya-kobo.github.io/">Machiya</a> · <a href="#quickstart">Quickstart</a> · <a href="docs/install.md">Install</a> · <a href="docs/settings.md">Settings</a> · <a href="docs/access.md">Access</a> · <a href="docs/api.md">API</a> · <a href="#license">License</a>
</p>

<p align="center"><a href="docs/screenshots/niwa-garden-dark.png"><img src="docs/screenshots/niwa-garden-dark.png" alt="The garden's landing page in the dark theme: topic maps for Crafts and Travel, then every note once with its growth stage" width="100%"></a><br>Wander the garden</p>
<table>
  <tr>
    <td align="center" width="33%"><a href="docs/screenshots/niwa-note-light.png"><img src="docs/screenshots/niwa-note-light.png" alt="A note, Chochin folding, with its tip callout, backlinks and nearby notes" width="100%"></a><br>Tend a note</td>
    <td align="center" width="33%"><a href="docs/screenshots/niwa-queue-dark.png"><img src="docs/screenshots/niwa-queue-dark.png" alt="The queue of unpublished notes in the dark theme, each with its scan result and a Publish button" width="100%"></a><br>Pick what to publish</td>
    <td align="center" width="33%"><a href="docs/screenshots/niwa-stream-light.png"><img src="docs/screenshots/niwa-stream-light.png" alt="The stream: this week's tended notes, day by day" width="100%"></a><br>See what changed</td>
  </tr>
</table>
<p align="center"><a href="docs/screenshots/niwa-note-phone-light.png"><img src="docs/screenshots/niwa-note-phone-light.png" alt="A note on a phone" width="24%"></a><br>Read it on your phone</p>

## Grow your garden

- Publish with one button. Niwa adds `publish: true` to the note's frontmatter and touches nothing else.
- **Your notes stay yours.** Niwa writes only `publish`, `growth` and its events (`.garden/events/`), never a note's body, as one commit rebased onto your changes.
- Growth stages (seedling, budding, evergreen), backlinks, nearby notes and topic maps.
- A queue of notes worth sharing: your agents' suggestions first, limited to one garden folder if you like.
- Short posts: publish just the part under a Garden heading, get a warning when a note runs long, and post one-line dated updates to the Stream ([how](docs/writing.md)).
- A stream of what changed, an RSS feed, search and a random note.

## Keep your secrets

- Every publish is scanned first (the part you publish): LAN and tailnet addresses, MAC addresses, keys, tokens, tailnet names, email addresses, and any words you list in `NIWA_SCAN_DENY`.
- Niwa shows each finding in the note. A note with an error stays out of the garden until you publish it with its findings, even if `publish: true` came from somewhere else.
- Notes in private folders (`NIWA_PRIVATE_FOLDERS`) never publish.

## Keep your links

- Niwa checks every link in a published note and saves a copy at the Wayback Machine. A live link gets a small "archive.org" link beside it; a dead one points at the copy.
- That sends your published notes' links to archive.org. `NIWA_ARCHIVE=none` turns it off.
- With Hister, your own pages show your private copy too.

## Meet your audience where they are

- Gemini and Gopher, for visitors still on the Information Superhighway.
- The public website is optional and off by default (`NIWA_PUBLIC_PORT`): published notes only, no sign-in, no cookies.

Niwa runs on its own. With [Konbini](https://github.com/machiya-kobo/konbini) a note gets board badges and the board half of the stream, with [Kura](https://github.com/machiya-kobo/kura) a link to the full note, and with [Hister](https://github.com/asciimoo/hister) private copies of its links.

## Quickstart

Run Niwa on the sample vault: a paper-lantern workshop and a trip to Kyoto, nine notes in the garden. You need Python 3.11 or later, `git` and `openssl` (for the Gemini certificate). On Debian or Ubuntu:

<!-- quickstart: packages-debian -->
```bash
sudo apt-get update && sudo apt-get install -y python3-venv git openssl curl netcat-openbsd
```

`curl` and `nc` are for [the checks](docs/install.md#check-all-three-listeners).

**1. Get the code:**

```sh
git clone https://github.com/machiya-kobo/niwa.git && cd niwa
```

**2. Install `markdown` 3.11 or later and `pyyaml`** into a venv:

<!-- quickstart: venv -->
```bash
python3 -m venv .venv && .venv/bin/pip install -q 'markdown>=3.11' pyyaml
```

**3. Make the sample vault a git repository.** Niwa pushes what you publish, so it needs a repository it can push to:

<!-- quickstart: vault -->
```bash
tools/demo-vault demo-vault --bare
mkdir -p demo-data
```

**4. Start it** on `127.0.0.1` with the login check off (`NIWA_AUTH=open`, for your own machine only):

<!-- quickstart: native-run-debian background -->
```bash
NIWA_AUTH=open NIWA_BIND=127.0.0.1 NIWA_HOST=localhost NIWA_GOPHER_PUBLIC_PORT=7070 NIWA_REPO_SUBDIR=personal \
  NIWA_REPO_URL="file://$PWD/demo-vault.git" NIWA_REPO_DIR="$PWD/demo-data/repo" \
  NIWA_DB="$PWD/demo-data/niwa.sqlite3" .venv/bin/python app/niwa.py
```

| Listener | Address |
|---|---|
| Web | http://127.0.0.1:8080/ |
| Gemini | `gemini://localhost/` (port 1965) |
| Gopher | `gopher://localhost:7070/` |

Publish a note and Niwa commits it to `demo-vault.git` about two minutes later (`git -C demo-vault.git log`).
Ctrl-C stops it, and `rm -rf demo-vault demo-vault.git demo-data` cleans up.

### Next

- **Check all three listeners:** [one script](docs/install.md#check-all-three-listeners).
- **Run it in a container or on the BSDs:** [docs/install.md](docs/install.md).
- **Point it at your own vault:** [a deploy key and a few settings](docs/install.md#your-own-vault).
- **Let people in, or open a public garden:** [docs/access.md](docs/access.md).
- **Run it with the rest of Machiya:** [the stack](docs/install.md#as-part-of-the-machiya-stack).
- **Every setting:** [docs/settings.md](docs/settings.md).
- **The API:** [docs/api.md](docs/api.md). **The code:** [docs/layout.md](docs/layout.md).

## License

Copyright (C) 2026 Micheal Waltz and Machiya contributors.

Niwa is free software under the GNU Affero General Public License, version 3 or (at your option) any later version: see [LICENSE](LICENSE). What it ships from other projects (Mermaid, the Hister CLI in the image) is listed with their licenses in [THIRD_PARTY_NOTICES](THIRD_PARTY_NOTICES). Contributions are welcome: [CONTRIBUTING.md](CONTRIBUTING.md); report a vulnerability privately: [SECURITY.md](SECURITY.md).
