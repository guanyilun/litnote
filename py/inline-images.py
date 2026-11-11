#!/usr/bin/env python3
"""Rewrite <img src="..."> in an exported HTML file as base64 data URIs.

Image paths in a note resolve only where the note is: an absolute path only
on this machine, a relative one only next to the note's source.  Inlining
makes the .html a single self-contained file that survives being copied or
emailed.

    $LITNOTE/py/inline-images.py [--source-dir DIR] out/notes/x.html

A relative path is taken relative to DIR, the directory of the .org file the
page was exported from (the page itself has been moved to out/notes/), and
then relative to the page.
"""
import base64
import mimetypes
import os
import re
import sys

IMG = re.compile(r'(<img\b[^>]*?\bsrc=")([^"]+)(")', re.I)
FRAMES = re.compile(r'(<img\b[^>]*?\bdata-frames=")([^"]+)(")', re.I)
SWIPE = re.compile(r'(<img\b[^>]*?\bdata-swipe=")([^"]+)(")', re.I)


def main(path, source_dir=None):
    with open(path, encoding='utf-8') as f:
        html = f.read()
    bases = ([os.path.abspath(source_dir)] if source_dir else []) + [os.path.dirname(os.path.abspath(path))]
    n_ok = n_miss = 0
    missing = []

    def repl(m):
        nonlocal n_ok, n_miss
        src = m.group(2)
        if src.startswith('data:'):
            return m.group(0)
        p = src[7:] if src.startswith('file://') else src
        if not os.path.isabs(p):
            p = next((os.path.join(b, p) for b in bases if os.path.isfile(os.path.join(b, p))),
                     os.path.join(bases[0], p))
        if not os.path.isfile(p):
            n_miss += 1
            missing.append(src)
            return m.group(0)
        mime = mimetypes.guess_type(p)[0] or 'application/octet-stream'
        with open(p, 'rb') as fh:
            b64 = base64.b64encode(fh.read()).decode('ascii')
        n_ok += 1
        return f'{m.group(1)}data:{mime};base64,{b64}{m.group(3)}'

    out = IMG.sub(repl, html)

    def repl_frames(m):
        if m.group(2).startswith('data:'):
            return m.group(0)
        uris = []
        for src in m.group(2).split():
            r = IMG.match(f'<img src="{src}"')
            u = repl(r)
            uris.append(u[len('<img src="'):-1])
        return f'{m.group(1)}{"|".join(uris)}{m.group(3)}'

    out = FRAMES.sub(repl_frames, out)
    out = SWIPE.sub(repl_frames, out)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(out)

    size = os.path.getsize(path) / 1e6
    print(f'{path}: inlined {n_ok} image(s), {size:.1f} MB')
    if n_miss:
        print(f'  WARNING: {n_miss} image(s) not found, left as links:')
        for s in missing:
            print(f'    {s}')
    return 0


if __name__ == '__main__':
    args = sys.argv[1:]
    source_dir = None
    if args[:1] == ['--source-dir'] and len(args) == 3:
        source_dir, args = args[1], args[2:]
    if len(args) != 1:
        sys.exit(__doc__)
    sys.exit(main(args[0], source_dir))
