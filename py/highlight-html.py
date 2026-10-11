#!/usr/bin/env python3
"""Syntax-highlight the <pre class="src src-LANG"> blocks in exported org HTML.

Org highlights source blocks with htmlize.el, which is not installed here (the
export prints "Cannot fontify source block").  Rather than add an Emacs
package, re-highlight after the fact with pygments, which is already present.

Only *source* blocks are touched.  `<pre class="example">` holds program
output, not code, and is left alone.

A noweb reference <<name>> whose block the export labelled as a chunk (an
element with id="chunk-<slug>") becomes a link to that block; the first
reference to each chunk gets id="use-<slug>", which the chunk's label links
back to.  The reference is swapped for a placeholder before highlighting, so
the lexer sees a single token in its place.

    $LITNOTE/py/highlight-html.py out/notes/x.html
"""
import html
import re
import sys

from pygments import highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import get_lexer_by_name
from pygments.util import ClassNotFound

# org's class suffix -> pygments lexer name
LANG = {'python': 'python', 'sh': 'bash', 'shell': 'bash',
        'emacs-lisp': 'elisp', 'elisp': 'elisp', 'makefile': 'make',
        'yaml': 'yaml', 'org': 'org', 'json': 'json'}

BLOCK = re.compile(r'<pre class="src src-([\w-]+)"[^>]*>(.*?)</pre>', re.S)
REF = re.compile(r'<<([^\n<>]+?)>>')


def slug(name):
    return re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')

# Light and dark palettes under the same `.src` prefix; the dark rules sit in
# a media query so they win only when the reader's OS asks for dark.
LIGHT, DARK = 'friendly', 'native'


def css():
    light = HtmlFormatter(style=LIGHT).get_style_defs('.src')
    dark = HtmlFormatter(style=DARK).get_style_defs('.src')
    # Drop each style's own background/colour on the container itself so the
    # stylesheet in export-note.el keeps control of the block frame.
    strip = re.compile(r'^\.src\s*\{[^}]*\}\s*', re.M)
    light, dark = strip.sub('', light), strip.sub('', dark)
    return ('<style>\n/* pygments (light) */\n' + light
            + '\n@media (prefers-color-scheme: dark) {\n/* pygments (dark) */\n'
            + dark + '\n}\n</style>')


def main(path):
    with open(path, encoding='utf-8') as f:
        doc = f.read()
    n = 0
    skipped = set()
    chunks = set(re.findall(r'id="chunk-([a-z0-9-]+)"', doc))
    used = set()

    def repl(m):
        nonlocal n
        lang, body = m.group(1), m.group(2)
        name = LANG.get(lang.lower())
        if name is None:
            skipped.add(lang)
            return m.group(0)
        try:
            lexer = get_lexer_by_name(name)
        except ClassNotFound:
            skipped.add(lang)
            return m.group(0)
        code = html.unescape(re.sub(r'<[^>]+>', '', body))
        refs = []

        def ref(r):
            if slug(r.group(1)) not in chunks:
                return r.group(0)
            refs.append(r.group(0))
            return f'NOWEBREF{len(refs) - 1}Q'

        code = REF.sub(ref, code)
        out = highlight(code, lexer, HtmlFormatter(nowrap=True)).rstrip('\n')
        for i, text in enumerate(refs):
            k = slug(REF.match(text).group(1))
            back = '' if k in used else f' id="use-{k}"'
            used.add(k)
            out = out.replace(f'NOWEBREF{i}Q', f'<a class="chunk-ref" href="#chunk-{k}"{back}>'
                                                f'{html.escape(text)}</a>', 1)
        n += 1
        return f'<pre class="src src-{lang}">{out}</pre>'

    doc = BLOCK.sub(repl, doc)
    if n and '</head>' in doc:
        doc = doc.replace('</head>', css() + '\n</head>', 1)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(doc)

    print(f'{path}: highlighted {n} source block(s)'
          + (f', skipped languages: {sorted(skipped)}' if skipped else ''))
    return 0


if __name__ == '__main__':
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    sys.exit(main(sys.argv[1]))
