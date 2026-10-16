#!/usr/bin/env python3
"""Run every run cell of a project's notes, in order: the whole analysis from its inputs.

    run-cells.py [--root DIR] [--notes analysis/a.org note/b.org] [--from NOTE[:K]]
                 [--only NOTE] [--dry-run] [--log-dir out/runs]

A run cell is a block `#+begin_src sh :run <where>`.  Notes are taken in the
explicit --notes order (otherwise analysis/, note/, then legacy notes/), and
cells in the order they appear.  Each cell runs as `bash -e` in the project
root; its output goes to LOG_DIR/<note>-<k>.log.  The first failing cell stops
the run.  Cells marked `:run manual` are listed but not run.
"""
import argparse
import glob
import os
from pathlib import Path
import re
import subprocess
import sys
import time

CELL = re.compile(r'^[ \t]*#\+begin_src[ \t]+(?:sh|bash)\b([^\n]*):run[ \t]+(\S+)[^\n]*\n(.*?)^[ \t]*#\+end_src',
                  re.I | re.M | re.S)
INCLUDE = re.compile(r'^[ \t]*#\+INCLUDE:[ \t]+"([^"]+\.org)"', re.I | re.M)


def note_order(root, review, notes=None):
    if notes is not None:
        return notes
    if review:
        names = INCLUDE.findall(Path(root, review).read_text())
        return [os.path.relpath(os.path.normpath(os.path.join(root, os.path.dirname(review), n)), root)
                for n in names]
    return [os.path.relpath(p, root) for folder in ("analysis", "note", "notes")
            for p in sorted(glob.glob(os.path.join(root, folder, "*.org")))]


def cells(root, note):
    text = Path(root, note).read_text()
    return [(m.group(2), m.group(3)) for m in CELL.finditer(text)]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default=".")
    order = ap.add_mutually_exclusive_group()
    order.add_argument("--review", help="Legacy review-document include order")
    order.add_argument("--notes", nargs="*", help="Documents in execution dependency order")
    ap.add_argument("--from", dest="start")
    ap.add_argument("--only")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--log-dir", default="out/runs")
    args = ap.parse_args()
    root = os.path.abspath(args.root)
    start_note, start_k = (args.start.split(":") + ["1"])[:2] if args.start else (None, "1")
    started = start_note is None
    plan = []
    for note in note_order(root, args.review, args.notes):
        stem = os.path.splitext(note)[0]
        if note.startswith("notes/"):
            stem = os.path.basename(stem)  # Preserve legacy selectors and log names.
        def matches(selector):
            key = os.path.splitext(selector)[0]
            return stem == key or ("/" not in key and os.path.basename(stem) == key)
        for k, (where, body) in enumerate(cells(root, note), 1):
            if not started and matches(start_note) and k >= int(start_k):
                started = True
            if started and (args.only is None or matches(args.only)):
                plan.append((stem, k, where, body))
    if not plan:
        sys.exit("no run cells selected")
    os.makedirs(os.path.join(root, args.log_dir), exist_ok=True)
    for stem, k, where, body in plan:
        label = f"{stem}:{k} ({where})"
        if args.dry_run or where == "manual":
            print(f"{'[manual] ' if where == 'manual' else ''}{label}")
            for line in body.rstrip().splitlines():
                print(f"    {line}")
            continue
        log = os.path.join(root, args.log_dir, f"{stem}-{k}.log")
        t0 = time.time()
        print(f"{label} ...", end="", flush=True)
        os.makedirs(os.path.dirname(log), exist_ok=True)
        with open(log, "w") as fh:
            rc = subprocess.run(["bash", "-e", "-c", body], cwd=root, stdout=fh, stderr=subprocess.STDOUT).returncode
        print(f" {'ok' if rc == 0 else f'FAILED ({rc})'} in {time.time() - t0:.0f} s, log {os.path.relpath(log, root)}")
        if rc:
            sys.exit(rc)


if __name__ == "__main__":
    main()
