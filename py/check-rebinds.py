#!/usr/bin/env python3
"""Find top-level names that more than one block of a note assigns.

``bin/note run`` restarts at the first block whose source changed and trusts that
the session still holds whatever the blocks above it left behind.  That trust
is broken by a later block reusing a name.  Block 3 sets ``rows``, block 20
reads it, block 30 sets ``rows`` to something else: after one full run the
session holds block 30's value, so restarting anywhere between 4 and 20 hands
block 20 the wrong object.  Nothing fails loudly -- in the case that prompted
this, a block that had worked for days produced ``KeyError: 0`` -- and the
staleness check reports the note as current once it has run.

This reads every python block of a note, collects the names each one binds at
module level (assignments, imports, defs, for-loop targets), and reports each
name bound by more than one block together with the blocks that read it in
between.  Rename one of them, or accept the pair knowingly: a name that is
redefined but never read by anything between the two definitions is harmless,
and those are listed separately so the real hazards stand out.

    $LITNOTE/py/check-rebinds.py notes/x.org
"""
import ast
import re
import sys

BEGIN = re.compile(r'^\s*#\+begin_src\s+python\b(.*)$', re.I)
END = re.compile(r'^\s*#\+end_src\s*$', re.I)
NAME = re.compile(r'^\s*#\+name:\s*(\S+)', re.I)
NOEVAL = re.compile(r':eval\s+(no|never)\b', re.I)

# Loop counters and throwaways that every block legitimately reuses.
IGNORE = {'_', 'i', 'j', 'k', 'f', 'r', 'm', 'a', 'b', 'x', 'y', 'w', 'n',
          'fig', 'ax', 'axes', 'tag', 'label', 'band', 'p', 'd', 'c', 's'}


def blocks(path):
    """(index, name, source) for every evaluated python block, in order."""
    lines = open(path).read().split('\n')
    out, name, i = [], None, 0
    while i < len(lines):
        nm = NAME.match(lines[i])
        if nm:
            name = nm.group(1)
        m = BEGIN.match(lines[i])
        if not m:
            i += 1
            continue
        j = i + 1
        while j < len(lines) and not END.match(lines[j]):
            j += 1
        if not NOEVAL.search(m.group(1)):
            out.append((len(out), name or f'line {i + 1}',
                        '\n'.join(lines[i + 1:j])))
        name, i = None, j + 1
    return out


def bound_and_read(src):
    """Module-scope names a block binds, and every name it loads.

    Module scope reaches into the bodies of top-level ``for``, ``while``,
    ``if``, ``with`` and ``try`` statements -- a name assigned inside a loop at
    the top of a block is as global as one assigned outside it -- but not into
    functions, classes or comprehensions, which have scopes of their own.
    Imports are returned separately: importing a module again binds the same
    object, so reusing an import name cannot hand anyone a different value.
    """
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return set(), set(), set()
    bound, imported = set(), set()

    def names_in(target):
        return {n.id for n in ast.walk(target) if isinstance(n, ast.Name)}

    def visit(stmts):
        for node in stmts:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef,
                                 ast.ClassDef)):
                bound.add(node.name)
                continue
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                for a in node.names:
                    imported.add((a.asname or a.name).split('.')[0])
                continue
            if isinstance(node, ast.Assign):
                for t in node.targets:
                    bound.update(names_in(t))
            elif isinstance(node, (ast.AnnAssign, ast.AugAssign)):
                bound.update(names_in(node.target))
            elif isinstance(node, (ast.For, ast.AsyncFor)):
                bound.update(names_in(node.target))
            elif isinstance(node, (ast.With, ast.AsyncWith)):
                for it in node.items:
                    if it.optional_vars is not None:
                        bound.update(names_in(it.optional_vars))
            elif isinstance(node, ast.Try):
                for h in node.handlers:
                    if h.name:
                        bound.add(h.name)
            for field in ('body', 'orelse', 'finalbody'):
                visit(getattr(node, field, []) or [])
            for h in getattr(node, 'handlers', []) or []:
                visit(h.body)

    visit(tree.body)
    return bound, module_reads(src), imported


def module_reads(src):
    """Names a block reads from module scope, by Python's own scoping rules.

    Walking the AST for loads over-counts: ``float(v) for v in xs`` loads
    ``v``, but that ``v`` belongs to the generator's scope and never touches
    the session.  ``symtable`` resolves scopes the way the compiler does, so a
    name counts only where the top level references it or a nested scope
    reaches out to it as a global.
    """
    import symtable
    try:
        top = symtable.symtable(src, 'block', 'exec')
    except SyntaxError:
        return set()
    out = {s.get_name() for s in top.get_symbols() if s.is_referenced()}
    stack = list(top.get_children())
    while stack:
        t = stack.pop()
        out |= {s.get_name() for s in t.get_symbols()
                if s.is_referenced() and s.is_global()}
        stack.extend(t.get_children())
    # Python 3.12 inlines list, set and dict comprehensions (PEP 709), and
    # symtable then reports their loop variables as top-level references with
    # no child scope to tell them apart.  Remove a name when every load of it
    # sits inside a comprehension that binds it: such a load never touches the
    # session.  A name also loaded anywhere else stays a read.
    return out - comprehension_only(src)


def comprehension_only(src):
    """Names loaded only inside comprehensions that bind them."""
    tree = ast.parse(src)
    inside, outside = set(), set()

    def walk(node, bound):
        # Functions, lambdas and classes are their own scopes, and symtable
        # already resolves those correctly; only the block's top level matters.
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef,
                             ast.Lambda, ast.ClassDef)):
            return
        if isinstance(node, (ast.ListComp, ast.SetComp, ast.DictComp,
                             ast.GeneratorExp)):
            names = set(bound)
            for gen in node.generators:
                walk(gen.iter, names)      # the first iterable is outside
                names |= {n.id for n in ast.walk(gen.target)
                          if isinstance(n, ast.Name)}
                for cond in gen.ifs:
                    walk(cond, names)
            for part in ('elt', 'key', 'value'):
                if getattr(node, part, None) is not None:
                    walk(getattr(node, part), names)
            return
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
            (inside if node.id in bound else outside).add(node.id)
        for child in ast.iter_child_nodes(node):
            walk(child, bound)

    walk(tree, frozenset())
    return inside - outside


def main():
    bad = 0
    for path in sys.argv[1:]:
        bl = blocks(path)
        info = [(i, nm) + bound_and_read(src)[:2] for i, nm, src in bl]
        firsts = {}
        hazards, harmless = [], []
        for i, nm, bound, _ in info:
            for name in sorted(bound - IGNORE):
                if name in firsts:
                    j, jnm = firsts[name]
                    # Blocks strictly between the two bindings that read the
                    # name without binding it themselves.
                    readers = [(k, knm) for k, knm, kb, kr in info
                               if j < k < i and name in kr and name not in kb]
                    (hazards if readers else harmless).append(
                        (name, (j, jnm), (i, nm), readers))
                firsts.setdefault(name, (i, nm))
        if hazards:
            print(f'{path}: {len(hazards)} rebinding(s) that can hand a block '
                  f'the wrong value after a partial re-run')
            for name, (j, jnm), (i, nm), readers in hazards:
                who = ', '.join(f'{k} {knm}' for k, knm in readers)
                print(f'  {name!r}: bound in {j} {jnm}, rebound in {i} {nm}; '
                      f'read in between by {who}')
            bad += len(hazards)
        else:
            print(f'{path}: no hazardous rebindings')
        if harmless:
            print(f'  ({len(harmless)} harmless: redefined, but nothing reads '
                  f'the name in between: '
                  + ', '.join(sorted({h[0] for h in harmless})) + ')')
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
