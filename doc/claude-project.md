# Working in a litnote project

This project is a literate analysis: the org notes in `notes/` are the
source of truth, and everything else is either tangled from them or written
by running what was tangled. These rules apply to every litnote project; the
project's own `CLAUDE.md` adds what is specific to it (environment, how jobs
are submitted, where data lives).

## Layout

| path | what | edit? |
|---|---|---|
| `notes/*.org` | the analysis: prose, code blocks, run cells, included outputs | **yes, the only place** |
| `notes/<name>_analysis.org` | the review document; `#+INCLUDE`s the other notes | when notes are added or reordered |
| `bin/`, `src/`, `scripts/`, … | code tangled from the notes | never by hand |
| `out/` | files written by runs (reports, figures); `out/notes/*.html` from `make` | never by hand |
| `readme.org` | where things stand, open items, notes table | yes |
| `Makefile` | four lines: `LITNOTE`, `CODE`, `REVIEW`, `include` | rarely (`CODE` globs) |

## Two kinds of step

- **Cheap computations: notebook style.** Python blocks evaluated in the
  note's live session; the output is the block's `#+RESULTS:`. No report
  files, no tangling. This is the default. See "Notes evaluated in a
  session" below.
- **Expensive runs or batch jobs: tangle, run, include.** Anything that
  goes through slurm, takes long, or needs resources an Emacs session
  can't give it. The code is tangled to a script, run outside Emacs, and its
  output file is included. See "The loop" below.

Pick per step by what running it costs, not per note: a notebook note can
tangle one script for its batch job and include that job's report.

## The loop (expensive steps)

Every change to a tangled step goes around this loop:

1. **Write the note.** A paragraph saying what the step does and why, then
   the code, bare, with an absolute `:tangle` path:
   ```org
   #+begin_src python :tangle /abs/project/bin/fit.py
   ```
   A script with more than one idea in it is several blocks tangled to the
   same file, in order, with the explanation of each piece (its equation,
   the choice it makes) in the prose right above it; see "Explanations
   interleaved with the code" below.
2. **Tangle.** `make tangle` writes every block to its file.
3. **Run outside Emacs.** Run the tangled script in a shell or through the
   batch queue, and have it write its output to a report file under
   `out/` (and figures to png files). Never run expensive steps through
   babel or the export.
4. **Show the run in the note.** A run cell with the exact command, and
   right after it the report, included:
   ```org
   #+begin_src sh :run login :eval no
   python bin/fit.py --group all > out/fit/summary.txt
   #+end_src

   #+INCLUDE: "/abs/project/out/fit/summary.txt" example
   ```
   Figures go in after the run that saved them, each with a name and a
   caption that describes what is plotted (see "Figures are explained like
   in a paper" under "Writing the prose"):
   ```org
   #+NAME: fig:residuals
   #+CAPTION: /Residuals of the fit./  ...
   [[file:/abs/project/out/fit/residuals.png]]
   ``` The export labels these cells `→ path`,
   `▶ run (where)` and `output`, so the page reads as an executed notebook.
5. **Write the prose from the output.** Every number in the text comes from
   an included report; re-read the report after each re-run and update
   the text.
6. **Render and check.** `make` renders `out/notes/*.html` and warns about
   blocks with no output. `make check-tangled` must say *all tangled and in
   sync*; if it reports `EDITED` or `NOT TANGLED`, move the change into a
   note. This is also the review-coverage check: the reviewer reads the
   notes, so a file that isn't tangled from one is code nobody reviewed.
   Keep every analysis path in `CODE`, even when some files are knowingly
   left out, so the report stays an honest list of what review doesn't
   cover.

## Notes evaluated in a session (cheap steps)

For cheap steps the note is a notebook: python blocks share one interpreter,
held open by an Emacs daemon, and their output is the block's
`#+RESULTS:`. The export labels that as output too. Drive them with
`bin/note`, never by editing results:

```sh
bin/note start && bin/note open notes/x.org
bin/note stale              # blocks changed since the last run, and empty results
bin/note run                # re-run from the first changed block to the end
bin/note block name1 name2  # only these, when you know nothing above changed
bin/note py 'print(x)'      # a one-off in the same interpreter
```

- Give every block a `#+name:` so its results stay attached when text is
  inserted above it; `$LITNOTE/py/name-blocks.py --write notes/x.org` adds
  names and re-anchors results.
- Mark blocks that legitimately print nothing `:eval no` or `:results
  silent`, so `make`'s empty-result warning stays meaningful.
- Editing a block's body makes it and everything after it stale. Say so
  when you edit, and re-run (or tell the user) before quoting its output.
- When a step becomes expensive (a slurm job, a long run), move it to a
  tangled script and include its output instead; don't leave the session
  busy for minutes, and never submit batch jobs from a block.

## Writing the prose

A note is read by a person who wants to follow the reasoning, so write it
the way you would explain the analysis to a colleague. This is the default
for every note, new sections and rewrites alike.

- **Think it through in order.** Say what we want to know and why, then
  what we did, then what we found. Short paragraphs.
- **Plain words, short sentences.** One idea per sentence. Don't chain
  clauses with semicolons, colons and parentheses; at most one
  parenthetical in a sentence, and preferably none. Avoid stacked
  qualifiers such as "(the X of the Y, see "Z")".
- **Lead with the point.** In a results paragraph, the first sentence is
  the takeaway in plain words; the numbers that support it come after.
- **Define terms in plain words** the first time a section uses them.
- **Say what a number means** when it isn't obvious ("about 1 in 40", "a
  third of them").
- **Bullets for parallel items only,** each one or two readable sentences,
  not a list of clauses. Use `/Label./` bullets sparingly.
- **Figures are explained like in a paper: the caption describes, the
  text interprets.** Every figure has a `#+NAME: fig:x` and a `#+CAPTION:`;
  org numbers them, and the text cites them as `Figure [[fig:x]]`, which
  renders as "Figure 3".
  - The caption says only what is plotted, which the plotting code fixes
    before anything runs: a short italic title (`/What it is./`), then the
    data and selection, each panel, the axes with units and scales, what
    colours, markers, sizes and lines mean, and what a reference line is
    for. It makes no claims about the result. Write it with the plotting
    code and check it against the image; update it when the code changes.
  - What the figure shows goes in the results text, which cites it. Like
    every other claim there, it is written after the run, backed by the
    included report, and re-read after each re-run.
  - Don't leave a figure's explanation to a separate "how to read"
    paragraph; the encoding belongs in the caption.
  - When one figure varies with a parameter, make it one figure with
    frames instead of many figures: `#+ATTR_HTML: :data-frames /abs/b.png
    /abs/c.png :data-labels a = 0|a = 1|a = 2` (no quotes; labels joined by
    `|`, the image itself first). The reader steps through them with j / k.
    The caption says what the frames are.
- **Explain each equation in words**: what it computes and what its symbols
  are, next to the code that implements it (see the rules below).
- **Precise, not chatty.** No hype and no filler. Keep the spelling the note
  already uses.

A quick test: read a paragraph aloud. If you have to stop to find out what
a clause refers to, split it.

## Rules

- **Explanations go in the prose, not in the code.** Don't write
  explanatory comments or docstrings in tangled blocks; the paragraph above
  the block explains. Keep only what the code needs to work (e.g. a
  `__doc__` that argparse prints).
- **Explanations interleaved with the code.** Don't put one paragraph above a
  long block and leave the reader to match it to the code. Split a file into
  blocks at its natural pieces (a function or a few related ones), all with
  the same `:tangle` path; org concatenates them in order, so the tangled
  file is the same. Before each block, the prose that block needs: the
  equation it implements, in the note's math (`\begin{equation*}`), with its
  symbols tied to the names in the code; the units; the choice it makes and
  why. A reader should be able to check each block against the text right
  above it. Put `:shebang` on the first block of a script only. Pure
  plumbing (argument parsing, reading and writing files) can stay in one
  block with a sentence on what it reads and writes.
- **Never paste output by hand.** Outputs enter by `#+INCLUDE` of a file a
  run wrote, so they can't drift from the code.
- **Self-contained.** Don't point to other analysis folders or colleagues'
  working files as provenance ("made in ../other", "copied from X's
  directory"). Say what each input is and show the command, tangled here,
  that reproduces it. Scientific references are fine.
- **Every analysis file is tangled or evaluated in a note.** Code lives in
  notes: session blocks for cheap steps, tangled blocks for scripts. A new
  script is a new block in a note,
  never a new file. Code no longer used moves to `attic/` (with a line in
  `attic/README.md`) rather than staying in `CODE` paths.
- **The HTML is an output.** Fix things in the note and re-render; never
  edit `out/notes/*.html`.
- **Tooling lives in litnote.** Don't copy or patch export, check or daemon
  code inside a project. Change the litnote repo (`$LITNOTE`, see the
  Makefile), keep it general, and commit there.

## Review comments

The user reviews the rendered HTML and leaves comments in the right margin.
They arrive either pasted into the conversation or as a downloaded
`review_comments_<page>.org`. Each open comment is an org `TODO` heading
giving the section, the quoted text, and the comment; a `# rc-json:` line
carries the anchor data and can be ignored. For each one:

1. Find the section and quoted text in the notes (the review document
   includes the other notes, so the text is usually in one of them).
2. Make the change in the note, and in the code, report or paper it
   implies. If the comment is a question, answer it in the conversation, and
   in the note too if the note should have said it.
3. Re-render (`make`) and run `make check-tangled`.
4. Report back per comment what changed. A comment whose quoted text you
   rewrote will show "anchor not found" on reload; tell the user it can be
   resolved.

If a comment states a general preference ("explanations don't belong in
code", "should be self-contained"), apply it to every note, not only the
paragraph it was left on.

## Pitfalls

- **Includes.** `#+INCLUDE: "x.org" :lines "N-" :minlevel 2` in the review
  document skips the first N-1 lines of each note (its header). When you add
  or remove header lines in a note, fix N. `:minlevel 2` makes the note's
  sections level 2, so each include needs its own level-1 heading (the
  note's title) right above it; without one, every note ends up inside the
  section before it ("How to read this").
- **YAML blocks.** `:comments link` (the file-wide default) needs a comment
  syntax Emacs `-Q` doesn't have for YAML. Put `:comments no` on YAML blocks,
  or the first line of the file is garbage.
- **One class over several blocks.** Tangling removes each block's common
  indentation, so a method can't be continued in its own indented block;
  with the org of Emacs 27 (9.4) neither `-i` nor a file-local
  `org-src-preserve-indentation` changes that in batch. Write each method
  as a named block at column 0, next to its prose, and assemble them with a
  short outline block (`:noweb yes`) whose indented `<<name>>` lines expand
  with that indentation:
  ```org
  #+begin_src python :tangle /abs/project/bin/fit.py :noweb yes
  class Model:
      <<model-init>>

      <<model-fit>>
  #+end_src
  ```
  The method blocks take no `:tangle`. The page labels each one
  `⟨name⟩ in → path`, links every `<<name>>` in the outline to it, and links
  the name in its label back to the outline. The same pattern writes any
  step outline-first: `<<load the group>>`, `<<fit each weighting>>`, each
  filled in under its own paragraph. Name the pieces as prose; that is the
  outline the reader sees.
- **Emacs in scripts.** `emacs`/`make` read stdin. Inside `ssh host bash -s <
  script`, redirect them from `/dev/null` or they swallow the rest of the
  script.
- **Environment.** Build under the project's environment; the pygments
  version changes the highlighted HTML.
- **Dates.** Write absolute dates in notes and `readme.org`, not "today" or
  "yesterday".

## Done means

- the note explains the change in plain prose ("Writing the prose"), and its
  code blocks are bare;
- the run cell and included output match what was actually run;
- `make` succeeds and `make check-tangled` reports all in sync;
- `readme.org` open items are updated if something was closed or raised;
- you have told the user what changed and what still needs their decision.
