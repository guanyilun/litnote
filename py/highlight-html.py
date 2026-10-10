#!/usr/bin/env python3
"""Syntax-highlight the <pre class="src src-LANG"> blocks in exported org HTML.

Org highlights source blocks with htmlize.el, which is not installed here (the
export prints "Cannot fontify source block").  Rather than add an Emacs
package, re-highlight after the fact with pygments, which is already present.

Only *source* blocks are touched.  `<pre class="example">` holds program
output, not code, and is left alone.

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
        out = highlight(code, lexer, HtmlFormatter(nowrap=True)).rstrip('\n')
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
