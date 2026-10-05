# Contributing to Niwa

Thanks for helping. Niwa is a small server that shows the notes you mark `publish: true` in a Markdown vault
(a Git repo) on the web (pages behind the owner's gate), as a gemini capsule and as a gopher hole. [CLAUDE.md](CLAUDE.md) is the detailed guide to how it
works and the traps already found; read the part for what you're changing.

## Building

- **Run it from source:** see README → Install. `python3 app/niwa.py` with the settings in the README's table.
- **The image:** `docker build -t niwa app` (or `podman build`). `app/vaultkit/` is vendored and checked at build time.

## Tests

Install `markdown` (3.11 or later) and `pyyaml`, then from the repository root:

```sh
python3 -m unittest discover -s tests
```

The suite serves the garden against a real bare Git remote and a throwaway vault, so it covers the owner gate, the
write path (form post → frontmatter edit → event → commit → push) and the pre-publish check. Add a test with any
change to behaviour. Run the suite on the oldest `markdown` you support (3.11) before changing rendering.

**Never test against a real vault or a real Hister.** Use the throwaway vault in the tests, and a fake that records
requests for Hister.

## Rules

- **Only the owner publishes.** `publish`, `growth`, `confidence` and `garden_pin` change only from the web UI
  (same-origin form posts). Agents may only `POST /api/suggest`.
- **Writes edit frontmatter lines only**, never note bodies.
- **Never break gemini and gopher** (`app/smallweb.py`), and never put Hister results, copies or private URLs on
  them.
- **Never edit `app/vaultkit/`.** It is vendored from `machiya-kobo/machiya` (`tools/vendor-vaultkit <tag>`); the build
  fails if it's edited. Fix it upstream and re-vendor.
- **Keep personal details out of the repo:** server addresses, network names, usernames, folder names from your own
  vault. They belong in settings (see the README), not in code defaults, tests or comments.
- **No new network endpoints** without discussion. Niwa talks to the vault repo, the optional sister services and
  Hister the settings name, and to archive.org only when `NIWA_ARCHIVE=wayback`. No analytics.
- Match the surrounding code: its naming, comment density and idiom. Commits start with `niwa: `.

## Sending a change

Open a pull request with what changed and why, and which tests you ran. Keep one change per pull request. By
contributing, you agree that your work is licensed under the GNU AGPL-3.0-or-later, as the rest of Niwa.

A release bumps `VERSION` in `app/niwa.py` and adds a section to `app/CHANGELOG.md` (served at `/api/changelog`).
