# litnote

Shared tooling for literate org analyses; `README.org` is the user guide
and `doc/claude-project.md` the working rules for agents in projects that
use it. This file is about changing litnote itself.

- **General, not domain-specific.** No project, experiment or instrument
  names, paths or examples in the code, comments, template or docs.
  Examples use neutral names (`notes/x.org`, `~/work/myproject`,
  `bin/fit.py`).
- **Projects use this checkout in place.** Every project's next `make` picks
  up a change, so keep the Makefile interface stable (`LITNOTE`, `CODE`,
  `REVIEW`, `NOTES`, `SRC`, `OUTDIR`, the target names) and the `bin/note`
  commands, and treat changes to the exported HTML as visible to every
  reviewer: comment anchors are built from section titles, block kinds and
  text snippets (`lisp/review-comments.html`), so changing how those are
  derived orphans existing comments.
- **Test before committing.**
  - Scaffold a throwaway project: `bin/litnote-new /tmp/x`, then `make
    tangle && make && make check-tangled`, plus `bin/note start`, `open`,
    `status`, `stop`.
  - For export changes, re-render an existing project and diff it with the
    previous render after normalising org's random ids and timestamps:
    `sed -E 's/org[0-9a-f]{7}/orgX/g; s/<!-- 20.*-->//; s/Created: 20.*</</'`.
- **Keep the docs in step.** When behaviour changes, update `README.org`,
  `doc/claude-project.md` and `template/` in the same commit.
- Commit here with a message saying what changed for projects.

@doc/claude-project.md
