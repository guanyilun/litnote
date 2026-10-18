#!/usr/bin/env python3
"""Rewrite <img src="..."> in an exported HTML file as base64 data URIs.

Org emits absolute paths for the ``[[file:/.../plot.png]]`` results, which
only resolve on this machine.  Inlining makes the .html a single
self-contained file that survives being copied or emailed.

    $LITNOTE/py/inline-images.py out/notes/x.html
"""
import base64
import mimetypes
import os
import re
import sys

IMG = re.compile(r'(<img\b[^>]*?\bsrc=")([^"]+)(")', re.I)
FRAMES = re.compile(r'(<img\b[^>]*?\bdata-frames=")([^"]+)(")', re.I)
SWIPE = re.compile(r'(<img\b[^>]*?\bdata-swipe=")([^"]+)(")', re.I)


def main(path):
    with open(path, encoding='utf-8') as f:
        html = f.read()
    base = os.path.dirname(os.path.abspath(path))
    n_ok = n_miss = 0
    missing = []

    def repl(m):
        nonlocal n_ok, n_miss
        src = m.group(2)
        if src.startswith('data:'):
            return m.group(0)
        p = src[7:] if src.startswith('file://') else src
        if not os.path.isabs(p):
            p = os.path.join(base, p)
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
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    sys.exit(main(sys.argv[1]))
