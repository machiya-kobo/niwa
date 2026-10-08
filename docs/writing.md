# Writing for the garden

[Back to the README](../README.md)

A garden is short, focused posts that grow with small updates. Your vault is bigger and messier. Niwa has four small tools to bridge the two.

## Keep posts short

Niwa shows each note's length in the Queue and on the note's page, and warns above 1,500 words (`NIWA_LONG_WORDS`, `0` turns it off). The warning never blocks a publish: the button says "Publish with 1 warning".

## Give the Queue one folder

Set `NIWA_QUEUE_FOLDERS=Garden` and the Queue lists only the notes in `Garden/`, plus held-back notes and anything an agent suggested. Write your garden posts there, or move a note in when it's ready. Unset, the Queue lists every unpublished note.

## Publish part of a note

Wrap the part you want to share:

```markdown
Private notes, a stray IP address, half-formed ideas.

<!-- garden -->
The part that goes in the garden.
<!-- /garden -->

More private notes.
```

- Only the wrapped text is published: on the web, Gemini, Gopher, the feed and search. The scan, the links and the word count see only that text too, so a secret outside the markers doesn't hold the note back.
- A note with no marker publishes whole. Several pairs join up. A marker that never closes runs to the end of the note.
- Obsidian doesn't show the comments in reading view, and other apps ignore them.
- The note's page shows how much it publishes: "excerpt, 240 of 3,100 words".

## Add short updates

Under a heading called `Updates`, add dated bullets:

```markdown
## Updates

- 2026-10-07: refolded the seam; it holds now
- 2026-10-01: first fold
```

Each update appears in the Stream (and on the public Gemini and Gopher streams) with the note's title, on its date. Niwa never writes to your note body, so you add updates in Obsidian.
