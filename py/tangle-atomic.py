#!/usr/bin/env python3
"""Tangle notes without ever leaving a target file missing or half-written.

Org (9.4) tangles by deleting each target and rewriting it block by block, so while `make tangle` runs every
target is briefly absent or partial: other sessions and running jobs that import it fail, and a tangle cut off
partway leaves a file deleted.  This script tangles a copy of each note into a scratch tree (the same absolute
paths under a temporary root, so the `:comments link` paths come out identical), then moves each finished file
over its target with an atomic rename, and only when it changed (unchanged files keep their mtime).  Readers see
the old file or the new one, never a gap.

Handles `:tangle` values that are absolute or relative paths, on source blocks, `#+PROPERTY: header-args` and
`:header-args:` drawers.  A note using `:tangle yes` is tangled the plain way, with a warning.

usage: tangle-atomic.py [--emacs EMACS] NOTE.org ...
"""
import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile

TANGLE = re.compile(r'(:tangle\s+)("[^"]+"|\S+)')
HEADER = re.compile(r'^\s*(#\+begin_src|#\+property:|:header-args)', re.I)


def redirect(text, note_dir, root):
    """The note's text with every :tangle path moved under `root`; the list of (tmp, target) pairs; None for 'yes'."""
    pairs = []

    def sub(m):
        val = m.group(2).strip('"')
        if val in ('no',):
            return m.group(0)
        if val == 'yes':
            raise ValueError('yes')
        target = os.path.normpath(os.path.join(note_dir, os.path.expanduser(val)))
        tmp = root + target
        pairs.append((tmp, target))
        return m.group(1) + tmp

    out = []
    for line in text.splitlines(True):
        out.append(TANGLE.sub(sub, line) if HEADER.match(line) else line)
    return ''.join(out), pairs


def same(a, b):
    """Same content (modes are handled on replace: an existing target keeps its own)."""
    if not os.path.exists(b) or os.path.getsize(a) != os.path.getsize(b):
        return False
    with open(a, 'rb') as fa, open(b, 'rb') as fb:
        return fa.read() == fb.read()


def tangle(note, emacs):
    note = os.path.abspath(note)
    text = open(note, encoding='utf-8').read()
    root = tempfile.mkdtemp(prefix='litnote-tangle-')
    try:
        try:
            new, pairs = redirect(text, os.path.dirname(note), root)
        except ValueError:
            print(f'{note}: uses ":tangle yes"; tangled the plain way', file=sys.stderr)
            subprocess.run([emacs, '-Q', '--batch', '-l', 'org', '--eval', f'(org-babel-tangle-file "{note}")'])
            return
        copy = root + note
        os.makedirs(os.path.dirname(copy), exist_ok=True)
        for tmp, _ in pairs:
            os.makedirs(os.path.dirname(tmp), exist_ok=True)
        with open(copy, 'w', encoding='utf-8') as f:
            f.write(new)
        r = subprocess.run([emacs, '-Q', '--batch', '-l', 'org', '--eval', f'(org-babel-tangle-file "{copy}")'],
                           capture_output=True, text=True)
        msg = [l for l in (r.stdout + r.stderr).splitlines() if l and not l.startswith('Loading')]
        if r.returncode != 0:
            print('\n'.join(msg), file=sys.stderr)
            sys.exit(f'{note}: emacs failed ({r.returncode}); no target touched')
        moved = 0
        for tmp, target in dict(pairs).items():
            if not os.path.exists(tmp):
                continue                      # a block with :tangle overridden to no further down
            if same(tmp, target):
                continue
            os.makedirs(os.path.dirname(target), exist_ok=True)
            stage = os.path.join(os.path.dirname(target), '.' + os.path.basename(target) + '.litnote-tmp')
            shutil.copyfile(tmp, stage)
            # an existing target keeps its mode (a project may keep files owner-only), gaining owner-execute when the
            # new version is executable (a shebang); a new one takes Org's mode
            mode = os.stat(tmp).st_mode & 0o7777
            if os.path.exists(target):
                mode = (os.stat(target).st_mode & 0o7777) | (mode & 0o100)
            os.chmod(stage, mode)
            os.replace(stage, target)         # atomic on one filesystem
            moved += 1
        tangled = [l for l in msg if l.startswith('Tangled')]
        print((tangled[0].replace(os.path.basename(copy), os.path.basename(note)) if tangled else note)
              + f' ({moved} changed)')
    finally:
        shutil.rmtree(root, ignore_errors=True)


ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument('notes', nargs='+')
ap.add_argument('--emacs', default=os.environ.get('EMACS', 'emacs'))
a = ap.parse_args()
for n in a.notes:
    tangle(n, a.emacs)
