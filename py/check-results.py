#!/usr/bin/env python3
"""Warn about source blocks in an org note that produced no output.

`make` deliberately does not re-run anything -- it ships the #+RESULTS: that
are already in the buffer.  That is the right default, because the blocks here
take minutes and an export should not quietly start a long job.  The cost is
that a block which failed, or was added and never run, exports as a gap with
the prose underneath it still describing numbers.  This is the check that says
so out loud.

Two kinds of block are skipped, because for them showing nothing is the point
rather than a fault: `:eval no`, an illustration of a command rather than a run
of it, and `:results silent`, a block that does its work in the session and has
nothing to say about it.  A check with known false positives stops being read,
so anything that legitimately produces no output should carry one of those.

Exit status is always 0.  This reports, it does not block: exporting a note
that is still being worked on is the normal case.
"""
import os
import re
import sys

BEGIN = re.compile(r'^\s*#\+begin_src\b(.*)$', re.I)
END = re.compile(r'^\s*#\+end_src\s*$', re.I)
RESULTS = re.compile(r'^\s*#\+RESULTS(\[[^]]*\])?:', re.I)
QUIET = re.compile(r':eval\s+(no|never)\b|:results\s[^:]*\b(silent|none)\b', re.I)
HEADING = re.compile(r'^\*+\s')
LINK = re.compile(r'^\s*\[\[file:([^]]+)\]\]\s*$')


def block_name(lines, begin):
    """The #+name: on the line above the #+begin_src at index BEGIN, or None."""
    k = begin - 1
    while k >= 0 and lines[k].strip().lower().startswith(('#+header', '#+caption', '#+attr')):
        k -= 1
    m = re.match(r'^\s*#\+name:\s*(\S+)', lines[k], re.I) if k >= 0 else None
    return m.group(1) if m else None


def empty_blocks(path):
    """(line number, heading) for each block whose results are missing/empty."""
    lines = open(path).read().split('\n')
    out, heading = [], '(top)'
    i = 0
    while i < len(lines):
        if HEADING.match(lines[i]):
            heading = lines[i].lstrip('* ').strip()
        m = BEGIN.match(lines[i])
        if not m:
            i += 1
            continue
        start, quiet = i + 1, bool(QUIET.search(m.group(1)))
        while i < len(lines) and not END.match(lines[i]):
            i += 1
        i += 1
        # The results node follows the block, separated by at most blank lines.
        j = i
        while j < len(lines) and not lines[j].strip():
            j += 1
        if quiet:
            continue
        if j >= len(lines) or not RESULTS.match(lines[j]):
            # A named block's results can sit anywhere in the file and org will
            # still find them, so "missing" here often means "detached": the
            # results exist, and export will print them under another heading.
            name = block_name(lines, start - 1)
            elsewhere = next((k for k, l in enumerate(lines)
                              if name and re.match(rf'^\s*#\+RESULTS:\s*{re.escape(name)}\s*$', l)),
                             None)
            if elsewhere is not None:
                out.append((start, heading,
                            f'results detached, found at line {elsewhere + 1}; '
                            f'$LITNOTE/py/name-blocks.py --reattach --write'))
            else:
                out.append((start, heading, 'no #+RESULTS:'))
            continue
        if j + 1 >= len(lines) or not lines[j + 1].strip() \
                or HEADING.match(lines[j + 1]):
            out.append((start, heading, 'empty #+RESULTS:'))
            continue
        # A plot block's result is a link, and org writes the link whether or
        # not the block managed to save the figure.  With `:results graphics
        # file' the block's stdout is discarded, so a plotting block that
        # raised leaves a perfectly well-formed result pointing at nothing --
        # and the export then shows a broken image under prose describing it.
        link = LINK.match(lines[j + 1])
        if link and not os.path.exists(link.group(1)):
            out.append((start, heading,
                        f'result links to a missing file: {link.group(1)}'))
    return out


def main():
    total = 0
    for path in sys.argv[1:]:
        for line, heading, why in empty_blocks(path):
            if not total:
                print('\n*** blocks with no output; the export will have gaps',
                      file=sys.stderr)
            total += 1
            print(f'  {path}:{line}  {why}  under {heading!r}', file=sys.stderr)
    if total:
        print(f'  -- {total} block(s).  Run them with '
              "`bin/note run` before exporting.\n", file=sys.stderr)


if __name__ == '__main__':
    main()
