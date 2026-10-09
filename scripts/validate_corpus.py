#!/usr/bin/env python3
"""Validate the packaged corpus: counts, structure, reference labels, hashes.

    python scripts/validate_corpus.py [--data data] [--no-schema]

Exits nonzero on any problem. Prints the verification table."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "src"))

from obligationbench.export import row_to_task  # noqa: E402
from obligationbench.tasks import load_tasks  # noqa: E402
from obligationbench.validate import validate_corpus, validate_tasks  # noqa: E402

NATIVE = {"balanced": "heldout_balanced", "natural": "heldout_natural", "dev": "dev", "val": "val",
          "locator": "heldout_locator", "onebranch": "heldout_onebranch", "text": "heldout_text"}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--data", default=os.path.join(ROOT, "data"))
    ap.add_argument("--no-schema", action="store_true")
    a = ap.parse_args(argv)
    by_split = {}
    for cfg, native in NATIVE.items():
        p = os.path.join(a.data, cfg + ".jsonl")
        if os.path.exists(p):
            by_split[native] = load_tasks(p)
    fd_path = os.path.join(a.data, "fdaaa.jsonl")
    fdaaa = load_tasks(fd_path) if os.path.exists(fd_path) else None
    problems = []
    for name, tasks in list(by_split.items()) + ([("fdaaa", fdaaa)] if fdaaa else []):
        bad = validate_tasks(tasks.values(), schema=not a.no_schema)
        problems += ["%s %s: %s" % (name, t, "; ".join(p)) for t, p in bad.items()]
    problems += validate_corpus(by_split, fdaaa)
    # hashes against the manifest
    mpath = os.path.join(a.data, "manifest.json")
    if not os.path.exists(mpath):
        mpath = os.path.join(os.path.dirname(a.data), "manifest.json")
    if os.path.exists(mpath):
        man = json.load(open(mpath, encoding="utf-8"))
        for name, tasks in list(by_split.items()) + ([("fdaaa", fdaaa)] if fdaaa else []):
            for tid, t in tasks.items():
                h = hashlib.sha256(json.dumps(t, sort_keys=True).encode("utf-8")).hexdigest()
                if man["tasks"].get(tid) != h:
                    problems.append("%s: hash differs from the manifest" % tid)
    else:
        problems.append("no manifest.json found")
    fams = {json.loads(t["notes_for_annotators"])["family"] for s in ("heldout_balanced", "heldout_natural", "dev", "val") for t in by_split.get(s, {}).values()}
    primary = sum(len(by_split.get(s, {})) for s in ("heldout_balanced", "heldout_natural", "dev", "val"))
    rows = [("Primary tasks", 938, primary), ("Balanced", 480, len(by_split.get("heldout_balanced", {}))),
            ("Natural", 218, len(by_split.get("heldout_natural", {}))), ("Development", 192, len(by_split.get("dev", {}))),
            ("Validation", 48, len(by_split.get("val", {}))), ("Template families", 120, len(fams)),
            ("Locator variant", 480, len(by_split.get("heldout_locator", {}))), ("One-branch variant", 240, len(by_split.get("heldout_onebranch", {}))),
            ("Text variant", 240, len(by_split.get("heldout_text", {}))), ("FDAAA set", 319, len(fdaaa or {}))]
    print("| Check | Expected | Observed | Status |\n|---|---|---|---|")
    for name, exp, obs in rows:
        print("| %s | %d | %d | %s |" % (name, exp, obs, "pass" if exp == obs else "FAIL"))
    print("| Reference labels execute, hashes match, structure valid | yes | %s | %s |" % (
        "yes" if not problems else "%d problem(s)" % len(problems), "pass" if not problems else "FAIL"))
    for p in problems[:30]:
        print("PROBLEM:", p)
    return 0 if not problems and all(e == o for _, e, o in rows) else 1


if __name__ == "__main__":
    sys.exit(main())
