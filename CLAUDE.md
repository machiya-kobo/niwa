# CLAUDE.md — Niwa

Niwa 庭 is a digital garden: it publishes the notes of a Markdown vault (a Git repo) that carry `publish: true` as a website, a gemini capsule and a gopher hole (README.md). It is part of Machiya; shared docs and contracts live in `machiya-kobo/machiya`, and `app/vaultkit/` is vendored from there.

## Rules

- **Only the owner publishes** or changes `publish`, `growth`, `confidence`, `garden_pin`, from the web UI (same-origin form posts). Agents get 403; they may only `POST /api/suggest`. Writes edit frontmatter lines only, never note bodies.
- **Identity:** with `MACHIYA_IDENTITY_FILE` (vaultkit `identity`, Machiya's `docs/identity.md`), `Handler.who()` resolves the principal once per request, and "agents get 403" is enforced by grants: pages and read APIs need `niwa` `read`, `/api/suggest` `suggest`, and `/publish`, `/dismiss`, `/meta` `publish` (`Handler.may`, passed to `writer.py` as `power`). Same-origin stays the CSRF guard for form posts (and for any post made with a session cookie), never the source of the power; `X-Agent` is only the events' `agent` label, `actor` is the principal. No or a bad proof is 401, no grant 403; `who().cookies` go out on every response. Without the file the old gate (`NIWA_USERS`, the "web" label in `writer.py`) applies unchanged. Gemini and gopher are public (published notes only) and never consult it.
- **Sign-in, pairing, preferences** (vaultkit `signin`): `/signin`, `/signout` and `POST /api/pair` (identity file only; 404 without one) come before the gate (after the open-mode `Host` check), each body read with `signin.read_body` and the module's limit; `GET/PUT /api/prefs` after it (`niwa` `read`), stored in `prefs.sqlite3` next to `NIWA_DB`. Without a file the old gate admits and `identity.ambient` names whose preferences they are (`Handler.principal()`); a page whose request has a principal passes `prefs_url` (`ctx.prefs_url`), and a session's name is `who=` (`ctx.who`). Every handler gets `ORIGINS` (`NIWA_PUBLIC_URL`); `http://` there means `secure=False`. Never answer these from gemini or gopher, and never put a password, hash or token in a page or log.
- **Niwa → Konbini** carries Niwa's service token (`NIWA_KONBINI_TOKEN_FILE`, `Authorization: Bearer`, never logged, no redirects followed) and `X-Agent: niwa`.
- **Standalone:** everything Niwa needs is its own clone, state and code. Konbini, Kura and Hister are optional URLs, and a page must still render when they're unset or down.
- **Never break gemini and gopher** (`app/smallweb.py`): they're part of the garden.
- **Hister results, copies and `private_url`** appear only on the owner's web pages: never on gemini or gopher, which read only `archive_url` (Wayback). Every Hister call sends `Origin: hister://`; never `hister index --force` a URL Hister already has. Bump `HISTER_VERSION` in `app/Dockerfile` with the Hister server.
- **Never edit `app/vaultkit/`**: fix it in `machiya-kobo/machiya` (`vaultkit/`), tag, then `tools/vendor-vaultkit <tag>`.
- **No owner-specific defaults:** hostnames, user agents, folder names and the like come from settings (README), not from code, tests or comments.
- **Tests before every change ships:** `python3 -m unittest discover -s tests` (needs `markdown` 3.7 or later and `pyyaml`; 3.7 is the oldest supported version).
- Commits: `niwa: …`.
