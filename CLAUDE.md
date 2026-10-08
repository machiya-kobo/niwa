# CLAUDE.md — Niwa

Niwa 庭 is a digital garden: it publishes the notes of a Markdown vault (a Git repo) that carry `publish: true` as a website, a Gemini capsule and a Gopher hole. It is one of the Machiya apps; shared docs and contracts live in [machiya-kobo/machiya](https://github.com/machiya-kobo/machiya) (`docs/`, `docs/contracts`). The README is the overview and the Quickstart; `docs/` has the detail.

## Layout

- `app/niwa.py`: the web listeners (owner and public), the gate, the settings; `garden.py`: the vault as the garden publishes it (index, scan, relations); `gmodern.py`: the HTML pages; `shell.py`: the page shell and icons; `smallweb.py`: Gemini and Gopher; `writer.py`: the only code that writes to the vault; `stream.py`, `links.py`, `feed.py`, `state.py` (SQLite), `hister.py`, `konbini.py`: the stream, link checks, the feed, state and the optional sister services.
- `app/static/`: `niwa.css` and `niwa.js` (the garden's own look), the icons, Mermaid. `app/vaultkit/` is vendored: see below.
- `tests/test_niwa.py`: the whole suite. `sample-vault/` and `tools/`: the demo vault, the screenshots and the Quickstart test.

## Set up, run, test

From a fresh clone (Python 3.11 or later):

```sh
python3 -m venv .venv && .venv/bin/pip install 'markdown>=3.11' pyyaml
.venv/bin/python -m unittest discover -s tests          # the tests; no linter is configured
```

Run it on the sample vault with the Quickstart in the [README](README.md#quickstart); `tools/quickstart-test` runs those blocks and checks their output, so keep them byte for byte. Settings are in [docs/settings.md](docs/settings.md).

## Rules that matter when you change code

- **Only the owner publishes.** `publish` and `growth` change only from the web UI (same-origin form posts); agents may only `POST /api/suggest`. Writes edit frontmatter lines, never note bodies. With `MACHIYA_IDENTITY_FILE` the same rules are enforced by grants (docs/access.md); the old gate (`NIWA_USERS`) applies without it.
- **A note is what the garden publishes, on every channel.** Read the vault only through `Garden.source()`, never a note file directly for anything public. A `publish: true` note whose scan finds errors is held back everywhere until the owner publishes it with its findings: a new channel must go through `garden.published()`.
- **Never break Gemini and Gopher** (`app/smallweb.py`), and never put Hister results, copies or private URLs on them.
- **The public garden** (`PublicHandler`) is published notes only, read-only, no cookies, and never reads an identity header or calls Hister, Kura or Konbini. Its tests sweep every route with sentinel URLs: keep them passing.
- **Standalone:** Konbini, Kura and Hister are optional URLs, and every page must still render when they are unset or down.
- **Never edit `app/vaultkit/`.** It is vendored from machiya's `vaultkit/`; the image build fails if it is edited. Fix it upstream, then `tools/vendor-vaultkit <tag>`.
- **Contrast:** every text stays at 4.5:1 in all ten themes (the style guide, rule 4). Add a check to the contrast test when you add a colour.
- **No personal details in the repo:** hostnames, network and folder names, logins and emails come from settings, and tests, fixtures, docs and comments use `example.com` and the sample vault. `tests/test_private_names.py` guards this when you keep a names list outside the repo (see the file).
- Add a test with any change in behavior. Prose follows machiya's `docs/voice.md`: American English, plain, no filler. Match the surrounding code's naming and comment density; commits start with `niwa: `.
