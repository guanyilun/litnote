#!/usr/bin/env python3
"""Check that every piece of analysis code is tangled from a note, and that
no tangled file has been edited by hand since.

    check-tangled.py [--root DIR] GLOB...        (make check-tangled)

1. Every file under DIR matching one of the GLOBs must be the :tangle target
   of a block in DIR/note/*.org or DIR/analysis/*.org (also legacy DIR/notes/*.org).  Empty files (a bare __init__.py) are
   skipped.
2. Every tangle target is re-tangled from its note and compared with the file
   on disk.  If they differ, the file on disk is restored (so hand edits are
   never lost silently) and reported: move the edit into the note.
Exit status 1 if anything is reported.
"""
import argparse
import glob
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

TANGLE = re.compile(r'^\s*#\+begin_src\s+\S+.*?:tangle\s+(\S+)', re.I | re.M)


def targets(proj):
    out = {}
    for note in sorted(p for folder in ('note', 'analysis', 'notes')
                       for p in glob.glob(f'{proj}/{folder}/*.org')):
        for t in TANGLE.findall(Path(note).read_text()):
            if t in ('no', 'yes'):
                continue
            p = os.path.normpath(t if os.path.isabs(t) else os.path.join(os.path.dirname(note), t))
            out.setdefault(os.path.relpath(p, proj), set()).add(os.path.relpath(note, proj))
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--root', default='.')
    ap.add_argument('globs', nargs='*')
    a = ap.parse_args()
    proj = os.path.abspath(a.root)
    os.chdir(proj)
    T = targets(proj)
    bad = 0
    code = sorted({f for pat in a.globs for f in glob.glob(pat) if os.path.getsize(f)})
    for f in code:
        if f not in T:
            print(f'NOT TANGLED  {f}')
            bad += 1
    backup = tempfile.mkdtemp(prefix='check_tangled_')
    for f in T:
        if os.path.exists(f):
            os.makedirs(os.path.join(backup, os.path.dirname(f)), exist_ok=True)
            shutil.copy2(f, os.path.join(backup, f))
    for note in sorted({n for ns in T.values() for n in ns}):
        subprocess.run(['emacs', '-Q', '--batch', '-l', 'org', '--eval',
                        f'(org-babel-tangle-file "{note}")'], capture_output=True, check=True)
    for f, notes in sorted(T.items()):
        b = os.path.join(backup, f)
        if not os.path.exists(b):
            print(f'NEW          {f} (created by tangling {", ".join(sorted(notes))})')
        elif open(b, 'rb').read() != open(f, 'rb').read():
            shutil.copy2(b, f)
            print(f'EDITED       {f} differs from {", ".join(sorted(notes))}; kept the file on disk')
            bad += 1
    shutil.rmtree(backup)
    print(f'{len(code)} analysis files, {len(T)} tangle targets: '
          + ('all tangled and in sync' if not bad else f'{bad} problem(s)'))
    sys.exit(1 if bad else 0)


if __name__ == '__main__':
    main()
