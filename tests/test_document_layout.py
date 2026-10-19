"""Regression checks for independent document roles and legacy projects."""
import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


def module(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'py' / f'{name}.py')
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


class DocumentLayoutTests(unittest.TestCase):
    def test_explicit_run_order_is_independent_of_index(self):
        runner = module('run-cells')
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'readme.org').write_text('[[file:note/a.org]]\n[[file:analysis/b.org]]')
            order = ['analysis/b.org', 'note/a.org']
            self.assertEqual(runner.note_order(folder, None, order), order)
            (root / 'notes').mkdir()
            (root / 'notes/review.org').write_text('#+INCLUDE: "b.org"\n#+INCLUDE: "a.org"')
            self.assertEqual(runner.note_order(folder, 'notes/review.org'),
                             ['notes/b.org', 'notes/a.org'])
            (root / 'note').mkdir()
            (root / 'note/c.org').write_text('#+title: C\n')
            self.assertEqual(runner.note_order(folder, 'notes/review.org'),
                             ['notes/b.org', 'notes/a.org', 'note/c.org'])

    def test_same_names_keep_distinct_tangle_provenance(self):
        checker = module('check-tangled')
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for directory in ('note', 'analysis', 'notes'):
                (root / directory).mkdir()
                (root / directory / 'same.org').write_text(
                    f'#+begin_src python :tangle {root}/src/{directory}.py\npass\n#+end_src\n')
            targets = checker.targets(folder)
            for directory in ('note', 'analysis', 'notes'):
                self.assertEqual(targets[f'src/{directory}.py'], {f'{directory}/same.org'})

    def test_run_logs_and_selectors_distinguish_same_named_documents(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for directory in ('note', 'analysis'):
                (root / directory).mkdir()
                (root / directory / 'same.org').write_text(
                    f'#+begin_src sh :run local\necho {directory}\n#+end_src\n')
            command = ['python3', str(ROOT / 'py/run-cells.py'), '--root', folder,
                       '--notes', 'analysis/same.org', 'note/same.org']
            subprocess.check_output(command, text=True)
            for directory in ('note', 'analysis'):
                self.assertEqual((root / f'out/runs/{directory}/same-1.log').read_text().strip(), directory)
            output = subprocess.check_output(command + ['--dry-run', '--only', 'note/same.org'], text=True)
            self.assertIn('note/same:1', output)
            self.assertNotIn('analysis/same:1', output)

    def test_render_destinations_preserve_roles_and_legacy_urls(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for directory in ('note', 'analysis', 'notes'):
                (root / directory).mkdir()
                (root / directory / 'same.org').write_text('#+title: Example\n')
            (root / 'Makefile').write_text(f'LITNOTE := {ROOT}\ninclude $(LITNOTE)/mk/litnote.mk\n')
            output = subprocess.check_output(['make', 'list'], cwd=root, text=True)
            for path in ('out/notes/note/same.html', 'out/notes/analysis/same.html',
                         'out/notes/same.html'):
                self.assertIn(path, output)

    def test_links_between_legacy_and_role_documents_follow_render_paths(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for directory in ('note', 'notes'):
                (root / directory).mkdir()
            (root / 'note/a.org').write_text('#+title: A\n\n[[file:../notes/b.org][b]]\n')
            (root / 'notes/b.org').write_text('#+title: B\n\n[[file:../note/a.org][a]]\n')
            (root / 'Makefile').write_text(f'LITNOTE := {ROOT}\ninclude $(LITNOTE)/mk/litnote.mk\n')
            subprocess.run(['make', 'out/notes/note/a.html', 'out/notes/b.html'], cwd=root,
                           stdin=subprocess.DEVNULL, capture_output=True, check=True)
            self.assertIn('href="../b.html"', (root / 'out/notes/note/a.html').read_text())
            self.assertIn('href="note/a.html"', (root / 'out/notes/b.html').read_text())


    def test_unflattened_legacy_layout_keeps_every_directory(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for directory in ('note', 'notes'):
                (root / directory).mkdir()
            (root / 'note/a.org').write_text('#+title: A\n\n[[file:../notes/b.org][b]]\n')
            (root / 'notes/b.org').write_text('#+title: B\n\n[[file:../note/a.org][a]]\n')
            (root / 'Makefile').write_text(f'LITNOTE := {ROOT}\nOUTDIR := out/html\nLEGACY_FLAT := no\n'
                                           'include $(LITNOTE)/mk/litnote.mk\n')
            output = subprocess.check_output(['make', 'list'], cwd=root, text=True)
            self.assertIn('out/html/notes/b.html', output)
            subprocess.run(['make', 'out/html/note/a.html', 'out/html/notes/b.html'], cwd=root,
                           stdin=subprocess.DEVNULL, capture_output=True, check=True)
            self.assertIn('href="../notes/b.html"', (root / 'out/html/note/a.html').read_text())
            self.assertIn('href="../note/a.html"', (root / 'out/html/notes/b.html').read_text())

if __name__ == '__main__':
    unittest.main()
