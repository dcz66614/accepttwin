#!/usr/bin/env python3
"""Minimal workspace-bounded cleanup command (P032 T011, §17.3).

Deletes only the evidence / temporary files the caller names, and
only when each one resolves to a regular file *inside the
``evidence/`` subtree* of the workspace root (T014, T011 P2: the
default deletable subtree is narrowed to ``evidence/`` — an
operator explicitly naming a file can no longer delete source
files, or any other file outside ``evidence/``, by mistake).
Anything else is refused and nothing is deleted.

Usage::

    python scripts/clean_evidence.py [--root DIR] [--dry-run] FILE [FILE ...]

* ``--root`` defaults to the project root (the parent of ``scripts/``).
* Paths may be relative to the root or absolute; absolute paths
  outside the root, ``..`` escapes, symlinks, directories, the
  root itself, and any file outside ``evidence/`` are all refused.
* All targets are validated before anything is deleted, so one bad
  target blocks the whole batch — there are no partial deletions.
* ``--dry-run`` prints what would be deleted and deletes nothing.

Exit codes: 0 = all named files deleted (or, with ``--dry-run``,
listed); 2 = refused (bad target, nothing deleted); 1 = unexpected
error. This command never runs a shell, never takes a glob, and
never deletes anything it was not explicitly given.

See :mod:`accepttwin.privacy` for the enforced rules.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Allow running as `python scripts/clean_evidence.py` from the repo root
# as well as `python -m` from anywhere: make `src/` importable.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from accepttwin.privacy import PrivacyError, delete_evidence_files


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Delete named files under evidence/ inside the workspace "
            "(P032 T011, PROJECT_BOOK §17.3; T014 narrows the default "
            "deletable subtree to evidence/ — files outside evidence/ "
            "are refused even when explicitly named). Refuses anything "
            "outside the workspace root."
        )
    )
    parser.add_argument(
        "paths",
        nargs="+",
        help="file(s) to delete, relative to --root or absolute; "
        "must resolve under evidence/",
    )
    parser.add_argument(
        "--root",
        default=str(Path(__file__).resolve().parents[1]),
        help="workspace root; targets must resolve inside it "
        "(default: project root)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="list what would be deleted and delete nothing",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        deleted = delete_evidence_files(
            args.root,
            args.paths,
            dry_run=args.dry_run,
            allowed_subtrees=("evidence",),
        )
    except PrivacyError as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 2
    verb = "would delete" if args.dry_run else "deleted"
    for path in deleted:
        print(f"{verb}: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
