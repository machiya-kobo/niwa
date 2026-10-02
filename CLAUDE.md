# CLAUDE.md — Niwa

Niwa 庭 is a digital garden: it publishes the notes of a Markdown vault (a Git repo) that carry `publish: true` as a website, a gemini capsule and a gopher hole (README.md). It is part of Machiya; shared docs and contracts live in `machiya-kobo/machiya`, and `app/vaultkit/` is vendored from there.

## Rules

- **Only the owner publishes** or changes `publish`, `growth`, `confidence`, `garden_pin`, from the web UI (same-origin form posts). Agents get 403; they may only `POST /api/suggest`. Writes edit frontmatter lines only, never note bodies.
- **Standalone:** everything Niwa needs is its own clone, state and code. Konbini, Kura and Hister are optional URLs, and a page must still render when they're unset or down.
- **Never break gemini and gopher** (`app/smallweb.py`): they're part of the garden.
- **Hister results, copies and `private_url`** appear only on the owner's web pages: never on gemini or gopher, which read only `archive_url` (Wayback). Every Hister call sends `Origin: hister://`; never `hister index --force` a URL Hister already has. Bump `HISTER_VERSION` in `app/Dockerfile` with the Hister server.
- **Never edit `app/vaultkit/`**: fix it in `machiya-kobo/machiya` (`vaultkit/`), tag, then `tools/vendor-vaultkit <tag>`.
- **No owner-specific defaults:** hostnames, user agents, folder names and the like come from settings (README), not from code, tests or comments.
- **Tests before every change ships:** `python3 -m unittest discover -s tests` (needs `markdown` 3.7 or later and `pyyaml`; 3.7 is the oldest supported version).
- Commits: `niwa: …`.
