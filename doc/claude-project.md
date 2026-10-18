# Working in a litnote project

This project is a literate analysis: the org documents in `note/` and `analysis/` are the
source of truth for computational reasoning and analysis code. Explanatory
visuals may be maintained separately in `diagrams/`. These rules apply to every litnote project; the
project's own `CLAUDE.md` adds what is specific to it (environment, how jobs
are submitted, where data lives).

## Two document roles

- **`analysis/`: investigation.** Organize working analyses around exploration
  and execution dependencies. Record questions, inputs, commands, results,
  decisions and relevant unsuccessful trials. Keep computations recoverable;
  a polished narrative is not required for every exploratory step.
- **`note/`: explanation.** Each note presents a coherent question, algorithm
  or argument in the order that best supports understanding. Apply the
  explanatory design and comprehension review below to these documents.
  Preserve uncertainty and contrary evidence relevant to the conclusions.

One note can draw on several analyses and one analysis can support several
notes. Link to or include authoritative evidence rather than copying code
or results. Keep stable algorithms and their explanations in `note/` and
tangle reusable implementations to `src/` for analyses to import. There is
no separate literate `library/` category. An analysis can be developed into
a note as understanding stabilizes; avoid leaving two maintained copies.

Review documents individually. `readme.org` is the navigation and status
index, not a concatenation of every document. Presentation order does not
set execution order: list documents with run cells in dependency order in
`RUN_NOTES` in the Makefile. Within each document, run cells and session
blocks retain their execution dependencies. Rendering and run plans default
to top-level `.org` files in each directory; a project can list
documents in sub-folders (for example `analysis/topic/*.org`) in `NOTES`
and `RUN_NOTES` in its Makefile. `make check-tangled` searches
sub-folders.

## Design the explanation first

Organize the program around the ideas the intended reader needs to
understand. Explain how those ideas justify and refine one another,
connect them to executable code, and show the evidence supporting
important claims. Tangling assembles the executable source; the note
presents the reasoning in the order that best supports understanding.

Think of three connected structures: the concepts and their justifications,
the computation and its dependencies, and the exposition that connects
them. Good alignment means the reader can find how a concept is implemented
and why an important computation belongs in the algorithm. These structures
need not have identical shapes. Express their connections through ordinary
prose, headings, equations, named chunks and references; no graph or extra
annotations are required.

- **Establish the problem and reader.** State the intended behavior, inputs,
  outputs, assumptions, and what counts as success. Write explanatory notes
  for a beginning graduate student in the relevant field. Assume general
  undergraduate preparation, not familiarity with this project or its
  specialized methods. Introduce technical terms, motivate equations, define
  their symbols, and explain intermediate reasoning rather than skipping
  directly to a formula or implementation. State any additional prerequisites.
- **Give the reader a conceptual overview.** Explain the governing idea and
  the roles of the main components before refining their implementation
  when that helps. Top-down exposition is a useful default, not a required
  order: a motivating example or definition may need to come first.
- **Make each abstraction earn its name.** A chunk should represent a
  meaningful responsibility. Explain how it contributes to its parent
  algorithm. Extract it when hiding the details clarifies the surrounding
  reasoning; keep straightforward lines visible when a jump adds no insight.
  Split when responsibilities diverge, and merge needless fragments.
- **Explain decisions and dependencies.** Say why the method applies, which
  assumptions justify an approximation, and what must remain true. Make
  significant inputs, outputs and state changes clear, especially variables
  shared across Noweb chunks. Do not narrate obvious syntax.
- **Connect mathematics to implementation.** Define symbols and units, map
  them to code identifiers, and explain numerical choices and boundary cases.
- **Keep claims and evidence connected.** Put correctness arguments, focused
  tests and numerical checks near the claims they support, with their limits.
  A successful run alone does not establish correctness.

## Layout

| path | role | edit? |
|---|---|---|
| `note/*.org` | standalone explanations and core algorithms | yes |
| `analysis/*.org` | executable investigations and evidence | yes |
| `bin/`, `src/`, `scripts/` | tangled implementations | never by hand |
| `diagrams/` | explanatory SVGs and optional generating scripts | yes |
| `out/` | generated results and rendered documents | never by hand |
| `readme.org` | document index, status and open items | yes |
| `Makefile` | project paths, code globs and `RUN_NOTES` | as needed |

Existing `notes/` projects and their `REVIEW` setting remain supported;
new projects use the two roles above and do not create a combined document.

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
   Start with the problem and conceptual overview, then refine meaningful
   components beside their explanations. Use named Noweb chunks when the
   reading order differs from executable order; see "Rules" below.
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
6. **Run everything again.** `make runs` runs every run cell of the notes in
   order (`RUN_NOTES` order, then each document top to bottom),
   each as `bash -e` in the project root, logging to `out/runs/`, and stops at
   the first failure; `make runs-list` shows the plan. So a run cell must be
   complete on its own: it calls tangled scripts, creates the directories it
   writes to, and runs in the foreground. Keep logic out of run cells (loops,
   comparisons, filters): put it in a tangled script and call that, so every
   result comes from reviewed code. Mark a cell `:run manual` if it must not be
   rerun automatically.
7. **Render and check.** `make` renders `out/notes/` HTML files and warns about
   blocks with no output. `make check-tangled` must say *all tangled and in
   sync*; if it reports `EDITED` or `NOT TANGLED`, move the change into a
   document. This checks that code is available in the review source, not that
   a reader has reviewed or understood it.
   Keep every analysis path in `CODE`, even when some files are knowingly
   left out, so the report stays an honest list of what review doesn't
   cover.

## Notes evaluated in a session (cheap steps)

For cheap steps the note is a notebook: python blocks share one interpreter,
held open by an Emacs daemon, and their output is the block's
`#+RESULTS:`. The export labels that as output too. Drive them with
`bin/note`, never by editing results:

```sh
bin/note start && bin/note open analysis/x.org
bin/note stale              # blocks changed since the last run, and empty results
bin/note run                # re-run from the first changed block to the end
bin/note block name1 name2  # only these, when you know nothing above changed
bin/note py 'print(x)'      # a one-off in the same interpreter
```

- Give every block a `#+name:` so its results stay attached when text is
  inserted above it; `$LITNOTE/py/name-blocks.py --write analysis/x.org` adds
  names and re-anchors results.
- Mark blocks that legitimately print nothing `:eval no` or `:results
  silent`, so `make`'s empty-result warning stays meaningful.
- Editing a block's body makes it and everything after it stale. Say so
  when you edit, and re-run (or tell the user) before quoting its output.
- When a step becomes expensive (a slurm job, a long run), move it to a
  tangled script and include its output instead; don't leave the session
  busy for minutes, and never submit batch jobs from a block.

## Writing the prose

An explanatory note is read by a person who wants to follow the reasoning, so write it
the way you would explain the analysis to a colleague. This is the default
for `note/`, new sections and rewrites alike. Working analyses need enough
context to reproduce and interpret the investigation; they need not satisfy
the full presentation requirements while exploration is ongoing.

- **Explain the analysis, not the work.** A note walks the reader through
  the analysis and explains what the results show: the question, the method
  as a choice, the figure, the interpretation. It is not a log of how the
  work was done (what was ported, what matched, which version was used).
  Keep correctness arguments and focused checks near the claims they
  support. Extensive regression comparisons or validation studies can live
  in a separate checks note, linked from the relevant explanation.
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
- **Explain visually.** Actively use visualization in explanatory notes.
  When introducing a mechanism, geometry, conceptual hierarchy, algorithm
  or data flow, look for a diagram that makes the relationships easier for
  a beginning graduate student to grasp. Use plots to expose comparisons,
  uncertainty and behavior. Avoid decorative figures that add no explanation.
  - *Result figures* come from analysis outputs. Show relevant selections,
    units and uncertainty; keep their numerical provenance recoverable.
  - *Explanatory diagrams* can be standalone SVG files in `diagrams/`, linked
    from the note. Their SVG markup and optional generating scripts do not
    need to appear in the note or be tangled from it. Keep them in version
    control, and keep their labels and relationships consistent with the
    explanation. Scripts used only to draw conceptual illustrations are
    exempt from analysis-code tangling requirements; scripts computing
    scientific results are not.
  Use a few colors, readable labels, arrows with clear meaning, and a
  layout readable at page width. Introduce each figure in the argument and
  explain the connection it helps the reader see. Use absolute image paths
  in Org so the current export pipeline can inline them after moving HTML.
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
  - To compare two images of the same layout, such as a measured map and
    a reference, stack them with a draggable divider:
    `#+ATTR_HTML: :data-swipe /abs/other.png :data-swipe-labels a|b`.
    Left of the divider is the figure's own image, right of it the other;
    the reader drags it, or clicks and uses the arrow keys. With
    `:data-frames`, `:data-swipe` lists one image per frame. The caption
    says what the two sides are.
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
- **Interleave explanation and implementation.** Choose block boundaries
  by conceptual responsibility, rather than mechanically splitting at every
  function or preserving source-file order. Put the rationale beside the
  relevant implementation or link explicitly to it. Several blocks can
  share a `:tangle` path when reading and executable order agree; otherwise
  assemble named chunks from an outline. Put `:shebang` on the first tangled
  block only. Straightforward plumbing can stay together with a sentence
  explaining its inputs and outputs.
- **Refine meaningful ideas with Noweb.** Use a short outline with
  `:noweb yes` when named components help the reader understand the whole.
  Length alone does not require extraction. Each component is a `#+name:`
  block with no `:tangle` and with `:eval no` when it is a source fragment.
  Place it beside the prose that explains it. References can precede their
  definitions when the reader already understands their role. Tangling
  supplies the reference's indentation; the page links references to their
  chunks and back. Chunks can contain chunks, but avoid unnecessary depth.
  Functions provide callable interfaces; Noweb chunks reveal implementations
  in explanatory stages, including inside a function. Keep important control
  flow and state changes visible or explicitly explain where they occur.
- **Shared code goes in a library, not in copies.** When a second script
  needs a function another script has, move it to a library module (e.g.
  `src/<topic>.py`) and import it from both; don't copy it. The library's
  blocks stay in the note next to the prose that explains them, with
  `:tangle` pointing at the library file. Above all, a model used both to
  simulate and to fit must be one function. Use library functions for
  reusable behavior and Noweb chunks for
  explanatory refinement; a library function can itself be assembled from
  chunks. Shared textual boilerplate is another use of Noweb. When moving
  code that produced included outputs, check that the
  old and new code give the same results, and say so in the note.
- **Never paste output by hand.** Session outputs enter through Babel's
  `#+RESULTS:`; external-run outputs enter through `#+INCLUDE` of a file
  the run wrote. Re-run changed computations before relying on their results.
- **Self-contained.** Link freely between this project's notes and analyses.
  Don't rely on unexplained external folders or colleagues' working files as provenance ("made in ../other", "copied from X's
  directory"). Say what each input is and show the command, tangled here,
  that reproduces it. Scientific references are fine.
- **Analysis code is tangled or evaluated in a document.** Standalone
  explanatory SVGs and their illustration-only generating scripts are
  exempt and should stay outside `CODE` globs. Computational code lives in
  notes: session blocks for cheap steps, tangled blocks for scripts. A new
  script is a new block in a note,
  never a new file. Code no longer used moves to `attic/` (with a line in
  `attic/README.md`) rather than staying in `CODE` paths.
- **The HTML is an output.** Fix things in the note and re-render; never
  edit `out/notes/` HTML files.
- **Tooling lives in litnote.** Don't copy or patch export, check or daemon
  code inside a project. Change the litnote repo (`$LITNOTE`, see the
  Makefile), keep it general, and commit there.

## Review comments

The user reviews the rendered HTML and leaves comments in the right margin.
They arrive either pasted into the conversation or as a downloaded
`review_comments_<page>.org`. Each open comment is an org `TODO` heading
giving the section, the quoted text, and the comment; a `# rc-json:` line
carries the anchor data and can be ignored. For each one:

1. Find the section and quoted text in the individual document being reviewed.
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

- **Links and includes.** Documents are rendered individually, preserving
  `note/` and `analysis/` beneath `out/notes/`. Use relative document links
  such as `../analysis/compare.org`. An included report is authoritative
  output; re-render its consuming document after a run changes the report
  (use `make -B` when necessary). Legacy combined documents still support
  `REVIEW`, but new projects do not need one.
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
  the name in its label back to the outline. This is the same outline-first
  pattern used for conceptual refinement.
- **Emacs in scripts.** `emacs`/`make` read stdin. Inside `ssh host bash -s <
  script`, redirect them from `/dev/null` or they swallow the rest of the
  script.
- **Environment.** Build under the project's environment; the pygments
  version changes the highlighted HTML.
- **Dates.** Write absolute dates in notes and `readme.org`, not "today" or
  "yesterday".

## Review for understanding

Read the overview without expanding every chunk. Can a reader with the
stated background explain the algorithm's purpose and main reasoning?
Then inspect its refinements:

- Does each major component have a clear role in the whole?
- Are important assumptions and justifications introduced or referenced?
- Can the reader connect the explanation to the actual operations, including
  boundary cases and shared state?
- Can they predict a relevant behavioral change without tracing every line?
- Are supporting arguments and checks easy to find?
- Can a beginning graduate student follow the terms, equations and steps
  without relying on unstated specialist or project knowledge?
- Do diagrams and plots clarify the important relationships, with readable
  labels and explanations connecting them to the argument?
- Would splitting, merging, renaming or moving a chunk reduce the effort
  needed to follow the argument?

Report localized findings: identify the passage or chunk, explain what the
reader cannot infer or what the prose misrepresents, cite the supporting
code or text, and propose a concrete revision. Distinguish observed
inconsistencies from uncertain interpretations. Avoid a single readability
score or demands for more prose without a specific explanatory need.

For example: "The overview says invalid measurements are rejected, but the
implementation never checks uncertainty values. Define the accepted inputs
and make the validation agree with that contract."

Build checks establish mechanical properties, not human understanding.
`make check-tangled` checks source coverage and consistency; it does not
establish that covered code was understood or reviewed.

## Done means

- an explanatory note passes the review for understanding above; a working
  analysis records its question, inputs, execution, evidence and current
  uncertainty without requiring a polished exposition;
- prose is clear, code blocks are bare, and chunk boundaries serve the
  explanation;
- figures or diagrams clarify results and relationships where useful, each
  with a caption;
- the run cell and included output match what was actually run;
- `make` succeeds and `make check-tangled` reports all in sync;
- `readme.org` open items are updated if something was closed or raised;
- you have told the user what changed and what still needs their decision.
