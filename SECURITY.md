# Security

## Reporting a vulnerability

Please report security problems privately, not in a public issue: use GitHub's private vulnerability reporting (this
repository's Security tab, then Report a vulnerability), with what you found, how to reproduce it, and what it
affects. You'll get an answer within a week, and a fix or a plan before anything is disclosed.

## What's in scope

- **The owner gate:** a way for an agent or a cross-site request to publish, unpublish, stage, pin or dismiss a note.
  Only the owner's same-origin form posts may; agents may only suggest. With Machiya's identity file
  (`MACHIYA_IDENTITY_FILE`) the power is the `niwa` `publish` grant: a principal without it doing any of these by
  any header (`Origin`, `X-Agent` or its absence), a request with an invalid token or session being served as
  someone else instead of 401, a principal reading or suggesting without `read` or `suggest`, or a header mode
  starting on a public bind without `NIWA_BIND_BEHIND_PROXY` is in scope.
- **Sign-in, pairing and preferences** (with an identity file): a cross-site request signing someone in or out or
  writing their preferences with a cookie or login; `next` sending a browser to another site; a sign-in accepted
  over plain http without `NIWA_PUBLIC_URL` as its origin; a password, a hash or a session or device token reaching
  a page, a log line or a JSON answer (other than the one token `/api/pair` hands out); one principal reading or
  writing another's preferences; any of these routes answering without an identity file.
- **Tokens:** Niwa's Konbini token (`NIWA_KONBINI_TOKEN_FILE`) or a caller's token reaching a log line, a page,
  `/api/status`, or any host but Konbini's.
- **Reading what isn't published:** an unpublished note, its title or its text, or an image only unpublished notes
  show, reaching the website, gemini or gopher; or a note under a `NIWA_PRIVATE_FOLDERS` folder being published.
- **Logins:** the owner's `Tailscale-User-Login` reaching gemini, gopher or the open `/api/status`.
- **The small-web stream:** the gemini and gopher `/stream` pages carry garden events about published notes only. A
  board card, a `next:` step, a blocked-by text, or the title of an unpublished note appearing there is in scope.
- **Private copies:** Hister results, copies or `private_url` reaching gemini, gopher or any page an anonymous
  visitor can open.
- **Writes:** anything that edits more than the garden's frontmatter fields, or a note body.
- **Script injection** from note text, titles, link labels or archived-copy URLs, and requests to hosts the
  configuration doesn't name (the link checker visits only the links in the notes it reads, and archive.org only with
  `NIWA_ARCHIVE=wayback`).
- **The pre-publish check:** a credential, key or private address pattern it should catch and doesn't.

Hister, Kura, Konbini, the vendored vaultkit's upstream, Git and the web server or proxy in front of Niwa are
separate projects: report their problems to them. Running with `NIWA_AUTH=open` on a public address is a
configuration error, not a vulnerability.

## Supported versions

Fixes go into the latest release on the main branch.
