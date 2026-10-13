#!/usr/bin/env python3
"""Run every run cell of a project's notes, in order: the whole analysis from its inputs.

    run-cells.py [--root DIR] [--review notes/x_analysis.org] [--from NOTE[:K]]
                 [--only NOTE] [--dry-run] [--log-dir out/runs]

A run cell is a block `#+begin_src sh :run <where>`.  Notes are taken in the
order the review document #+INCLUDEs them (or alphabetically without one), and
cells in the order they appear.  Each cell runs as `bash -e` in the project
root; its output goes to LOG_DIR/<note>-<k>.log.  The first failing cell stops
the run.  Cells marked `:run manual` are listed but not run.
"""
import argparse
import glob
import os
import re
import subprocess
import sys
import time

CELL = re.compile(r'^[ \t]*#\+begin_src[ \t]+(?:sh|bash)\b([^\n]*):run[ \t]+(\S+)[^\n]*\n(.*?)^[ \t]*#\+end_src',
                  re.I | re.M | re.S)
INCLUDE = re.compile(r'^[ \t]*#\+INCLUDE:[ \t]+"([^"]+\.org)"', re.I | re.M)


def note_order(root, review):
    if review:
        names = INCLUDE.findall(open(os.path.join(root, review)).read())
        return [os.path.join("notes", n) for n in names]
    return sorted(os.path.relpath(p, root) for p in glob.glob(os.path.join(root, "notes", "*.org")))


def cells(root, note):
    text = open(os.path.join(root, note)).read()
    return [(m.group(2), m.group(3)) for m in CELL.finditer(text)]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default=".")
    ap.add_argument("--review")
    ap.add_argument("--from", dest="start")
    ap.add_argument("--only")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--log-dir", default="out/runs")
    args = ap.parse_args()
    root = os.path.abspath(args.root)
    start_note, start_k = (args.start.split(":") + ["1"])[:2] if args.start else (None, "1")
    started = start_note is None
    plan = []
    for note in note_order(root, args.review):
        stem = os.path.splitext(os.path.basename(note))[0]
        for k, (where, body) in enumerate(cells(root, note), 1):
            if not started and stem == os.path.splitext(os.path.basename(start_note))[0] and k >= int(start_k):
                started = True
            if started and (args.only is None or stem == os.path.splitext(os.path.basename(args.only))[0]):
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
        with open(log, "w") as fh:
            rc = subprocess.run(["bash", "-e", "-c", body], cwd=root, stdout=fh, stderr=subprocess.STDOUT).returncode
        print(f" {'ok' if rc == 0 else f'FAILED ({rc})'} in {time.time() - t0:.0f} s, log {os.path.relpath(log, root)}")
        if rc:
            sys.exit(rc)


if __name__ == "__main__":
    main()
