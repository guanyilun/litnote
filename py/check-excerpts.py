#!/usr/bin/env python3
"""Verify that source quoted in a note still matches the file it came from.

A note can walk through a script in ``bin/`` by quoting it piece by piece
and discussing each piece.  Quoted code rots: the file gets edited, the
note keeps the old text, and the discussion beneath it slowly stops describing
anything real.  That is the same failure as a stale ``#+RESULTS:``, and it
deserves the same treatment -- an automatic check rather than a good intention.

Mark a quoting block with an ``#+excerpt:`` line naming the file it came from:

    #+excerpt: bin/fit.py
    #+name: excerpt-load-group
    #+begin_src python :eval no
    def load_group(path, group, args):
        ...
    #+end_src

The path is relative to the project root, the directory above the note's
``notes/``.  The block body then has to appear verbatim in that file.  ``#+excerpt:`` is not
an org keyword, so export ignores it; it exists only for this check.

Exit status is 1 when anything has drifted, so this can gate an export.
"""
import argparse
import os
import re
import sys

EXCERPT = re.compile(r'^\s*#\+excerpt:\s*(\S+)\s*$', re.I)
BEGIN = re.compile(r'^\s*#\+begin_src\b', re.I)
END = re.compile(r'^\s*#\+end_src\s*$', re.I)
NAME = re.compile(r'^\s*#\+name:\s*(\S+)\s*$', re.I)


def excerpts(path):
    """(line, name, source file, quoted body) for each marked block."""
    lines = open(path).read().split('\n')
    out = []
    for i, line in enumerate(lines):
        m = EXCERPT.match(line)
        if not m:
            continue
        src, name, j = m.group(1), None, i + 1
        # The #+name: may sit between the marker and the block; skip to the
        # #+begin_src, but not past unrelated prose.
        while j < len(lines) and not BEGIN.match(lines[j]):
            nm = NAME.match(lines[j])
            if nm:
                name = nm.group(1)
            elif lines[j].strip():
                break
            j += 1
        if j >= len(lines) or not BEGIN.match(lines[j]):
            out.append((i + 1, name, src, None))
            continue
        k = j + 1
        while k < len(lines) and not END.match(lines[k]):
            k += 1
        out.append((i + 1, name or '(unnamed)', src, '\n'.join(lines[j + 1:k])))
    return out


def main():
    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('notes', nargs='+')
    p.add_argument('--quiet', action='store_true',
                   help='Print only failures.')
    args = p.parse_args()

    bad = 0
    cache = {}
    for note in args.notes:
        found = excerpts(note)
        if not found:
            continue
        if not args.quiet:
            print(f'{note}: {len(found)} excerpt(s)')
        for line, name, src, body in found:
            where = f'{note}:{line}  {name}'
            if body is None:
                print(f'  DRIFTED {where}: no source block after #+excerpt:')
                bad += 1
                continue
            full = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(note))), src)
            if full not in cache:
                try:
                    cache[full] = open(full).read()
                except OSError as e:
                    cache[full] = None
                    print(f'  DRIFTED {where}: cannot read {src} ({e.strerror})')
            text = cache[full]
            if text is None:
                bad += 1
                continue
            if body.rstrip('\n') in text:
                if not args.quiet:
                    print(f'  ok      {name:34s} {src}')
            else:
                print(f'  DRIFTED {where}: no longer verbatim in {src}')
                bad += 1

    if bad:
        print(f'\n{bad} excerpt(s) no longer match their source.', file=sys.stderr)
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
