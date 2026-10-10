#!/usr/bin/env python3
"""Give every source block in an org note a #+name:, and anchor its results.

Why this matters beyond tidiness.  An unnamed block's results are found by
position: org looks just past #+end_src and takes whatever #+RESULTS: it finds.
Insert a paragraph and a new block between a block and its results -- an
ordinary edit -- and the results now belong to the new block, which is how
notes/x.org came to have a table of numbers sitting under a
block that prints nothing of the kind.  A named block's results are anchored by
that name instead, so the same edit is harmless.

Naming also makes `bin/note block <name> ...` reach individual blocks, which is
the cheapest way to re-run a scattered handful after a small change.

Adding a name to a block that already has an unnamed #+RESULTS: makes org write
a *second*, named one on the next run and orphan the first.  So the two edits
have to happen together, and they do: this renames the existing results node at
the same time, leaving the note consistent with no need to re-run anything.

    $LITNOTE/py/name-blocks.py notes/x.org           # show what it would do
    $LITNOTE/py/name-blocks.py --write notes/x.org
"""
import argparse
import re
import sys

BEGIN = re.compile(r'^\s*#\+begin_src\b', re.I)
END = re.compile(r'^\s*#\+end_src\s*$', re.I)
RESULTS = re.compile(r'^(\s*#\+RESULTS)(\[[^]]*\])?:(.*)$', re.I)
NAME = re.compile(r'^\s*#\+name:', re.I)
HEADING = re.compile(r'^(\*+)\s+(.*?)\s*$')
NOISE = re.compile(r'\b(the|a|an|and|of|for|to|in|on|is|it|this|that|what|'
                   r'where|how|our|its|with|does|do|are|from|way|same|one)\b')


def slug(text, limit=4):
    """A short kebab-case handle for a heading, keeping the words that carry it."""
    text = re.sub(r'=([^=]+)=', r'\1', text)            # org verbatim markup
    text = re.sub(r'\[\[[^]]*\]\[([^]]*)\]\]', r'\1', text)  # links
    text = NOISE.sub(' ', text.lower())
    words = re.findall(r'[a-z0-9]+', text)
    return '-'.join(words[:limit]) or 'block'


def rename(lines):
    """Yield the rewritten note plus the list of (name, heading) assigned."""
    out, assigned, used = [], [], {}
    heading = 'top'
    i = 0
    while i < len(lines):
        m = HEADING.match(lines[i])
        if m:
            heading = m.group(2)
        if not BEGIN.match(lines[i]):
            out.append(lines[i])
            i += 1
            continue

        already = bool(out) and NAME.match(out[-1])
        if already:
            name = out[-1].split(':', 1)[1].strip()
        else:
            base = slug(heading)
            used[base] = used.get(base, 0) + 1
            name = base if used[base] == 1 else f'{base}-{used[base]}'
            out.append(f'#+name: {name}')
            assigned.append((name, heading))

        while i < len(lines) and not END.match(lines[i]):
            out.append(lines[i])
            i += 1
        if i < len(lines):
            out.append(lines[i])          # the #+end_src
            i += 1

        # Re-point the results node that follows, if there is one, so that org
        # finds it by name rather than writing a fresh one beside it.
        j = i
        while j < len(lines) and not lines[j].strip():
            j += 1
        rm = RESULTS.match(lines[j]) if j < len(lines) else None
        if rm and not rm.group(3).strip():
            out.extend(lines[i:j])
            out.append(f'{rm.group(1)}: {name}')
            i = j + 1
    return out, assigned


def reattach(lines):
    """Move every named results node back to directly after its block.

    Naming a block anchors its results *by name*: org will find
    ``#+RESULTS: foo`` wherever it sits, so a block whose results have drifted
    still looks healthy to org and to ``bin/note stale``.  But export prints a
    results node where it sits in the file, so drifted results appear under the
    wrong heading.  They drift the same way unnamed results get misattributed --
    by inserting text after a block's ``#+end_src`` and before its results --
    and this puts them back.
    """
    # Locate each named results node: header line through the end of its body.
    nodes, i = {}, 0
    while i < len(lines):
        m = RESULTS.match(lines[i])
        name = m.group(3).strip() if m else ''
        if not name:
            i += 1
            continue
        j = i + 1
        if j < len(lines) and re.match(r'^\s*#\+begin_example', lines[j], re.I):
            while j < len(lines) and not re.match(r'^\s*#\+end_example', lines[j], re.I):
                j += 1
            j += 1
        else:
            while j < len(lines) and (lines[j].startswith(':') or
                                      lines[j].startswith('[[')):
                j += 1
        nodes[name] = (i, j)
        i = j

    # Blocks whose results are not the first non-blank thing after #+end_src.
    moves = []
    for i, line in enumerate(lines):
        nm = NAME.match(line)
        if not nm:
            continue
        name = line.split(':', 1)[1].strip()
        if name not in nodes:
            continue
        k = i + 1
        while k < len(lines) and not END.match(lines[k]):
            k += 1
        n = k + 1
        while n < len(lines) and not lines[n].strip():
            n += 1
        if nodes[name][0] != n:
            moves.append((name, k, nodes[name]))
    if not moves:
        return lines, []

    # Cut every misplaced node out, then insert each after its block, working
    # from the bottom of the file up so earlier positions stay valid.
    cut = {r for _, _, (a, b) in moves for r in range(a, b)}
    body = {name: lines[a:b] for name, _, (a, b) in moves}
    ends = {name: k for name, k, _ in moves}
    out = []
    for idx, line in enumerate(lines):
        if idx in cut:
            continue
        out.append(line)
        for name, k in ends.items():
            if idx == k:
                out.extend([''] + body[name])
    return out, [(name, a + 1) for name, _, (a, _) in moves]


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('notes', nargs='+')
    p.add_argument('--write', action='store_true',
                   help='Edit in place; without it, only report.')
    p.add_argument('--reattach', action='store_true',
                   help='Instead of naming, move each named results node '
                        'back to directly after its block.')
    args = p.parse_args()

    for path in args.notes:
        lines = open(path).read().split('\n')
        if args.reattach:
            out, moved = reattach(lines)
            if not moved:
                print(f'{path}: every results node is in place')
                continue
            print(f'{path}: {len(moved)} results node(s) out of place')
            for name, at in moved:
                print(f'  {name:32s} was at line {at}')
            if args.write:
                open(path, 'w').write('\n'.join(out))
            else:
                print('  (dry run; pass --write)', file=sys.stderr)
            continue
        out, assigned = rename(lines)
        if not assigned:
            print(f'{path}: every block already named')
            continue
        print(f'{path}: naming {len(assigned)} block(s)')
        for name, heading in assigned:
            print(f'  {name:32s} under {heading!r}')
        if args.write:
            open(path, 'w').write('\n'.join(out))
        else:
            print('  (dry run; pass --write)', file=sys.stderr)


if __name__ == '__main__':
    main()
