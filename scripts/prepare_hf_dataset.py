#!/usr/bin/env python3
"""Build the Hugging Face dataset directory of ObligationBench from the native task
files, and the data/ directory of this repository (the same files).

    python scripts/prepare_hf_dataset.py --bench PATH/TO/bench --out dist/obligationbench-dataset

``--bench`` is the generator's output root: it holds instances_v2/<domain>/<split>/*.json
(the primary corpus and the derived variants) and instances_fdaaa/fdaaa-*.json. Every
task is exported verbatim (``task_json``) with the flattened fields of the row schema
(docs/data_schema.md). The script fails unless the counts match the published corpus,
every exported row round-trips to its source task, and every task validates.
"""
from __future__ import annotations

import argparse
import glob
import hashlib
import json
import os
import shutil
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "src"))

from obligationbench import __version__  # noqa: E402
from obligationbench.export import row_to_task, task_to_row  # noqa: E402
from obligationbench.tasks import DOMAINS, PRIMARY_SPLITS, VARIANT_SPLITS, load_tasks  # noqa: E402
from obligationbench.validate import (EXPECTED_FDAAA, EXPECTED_PRIMARY, EXPECTED_VARIANTS,  # noqa: E402
                                      parent_map, validate_corpus, validate_tasks)

CONFIG_FILE = {"heldout_balanced": "balanced", "heldout_natural": "natural", "dev": "dev", "val": "val",
               "heldout_locator": "locator", "heldout_onebranch": "onebranch", "heldout_text": "text"}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--bench", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--skip-schema", action="store_true", help="skip the per-task schema validation (faster)")
    a = ap.parse_args(argv)
    inst = os.path.join(a.bench, "instances_v2")
    by_split = {}
    for split in PRIMARY_SPLITS + VARIANT_SPLITS:
        tasks = {}
        for dom in DOMAINS:
            d = os.path.join(inst, dom, split)
            if os.path.isdir(d):
                tasks.update(load_tasks(d))
        if tasks:
            by_split[split] = tasks
    fdaaa = load_tasks(os.path.join(a.bench, "instances_fdaaa")) if os.path.isdir(os.path.join(a.bench, "instances_fdaaa")) else {}
    fdaaa = {k: v for k, v in fdaaa.items() if k.startswith("fdaaa-")}
    with open(os.path.join(inst, "manifest.json"), encoding="utf-8") as fh:
        gen = json.load(fh)
    seed = int(gen.get("seed", 20260801))

    problems = validate_corpus(by_split, fdaaa or None)
    for name, tasks in list(by_split.items()) + [("fdaaa", fdaaa)]:
        bad = validate_tasks(tasks.values(), schema=not a.skip_schema)
        problems += ["%s %s: %s" % (name, t, "; ".join(p)) for t, p in bad.items()]
    if problems:
        for p in problems:
            print("PROBLEM:", p)
        return 1

    os.makedirs(os.path.join(a.out, "data"), exist_ok=True)
    manifest = {"name": "ObligationBench", "version": __version__, "generator_seed": seed,
                "generated_at": gen.get("generated_at"), "configs": {}, "tasks": {}}
    parents = parent_map(by_split.get("heldout_locator", {}), by_split.get("heldout_balanced", {}))
    for split, tasks in by_split.items():
        rows = []
        for tid in sorted(tasks):
            row = task_to_row(tasks[tid], split, parent_task_id=parents.get(tid), generator_seed=seed)
            assert row_to_task(row) == tasks[tid], "round trip failed for %s" % tid
            rows.append(row)
        path = os.path.join(a.out, "data", CONFIG_FILE[split] + ".jsonl")
        with open(path, "w", encoding="utf-8") as fh:
            for r in rows:
                fh.write(json.dumps(r, sort_keys=True) + "\n")
        manifest["configs"][CONFIG_FILE[split]] = {
            "native_split": split, "tasks": len(rows), "families": len({r["family_id"] for r in rows}),
            "domains": dict(Counter(r["domain"] for r in rows)),
            "primary_corpus": split in PRIMARY_SPLITS, "file": "data/%s.jsonl" % CONFIG_FILE[split]}
        for r in rows:
            manifest["tasks"][r["task_id"]] = r["task_sha256"]
    if fdaaa:
        rows = [task_to_row(fdaaa[t], "fdaaa", generator_seed=seed) for t in sorted(fdaaa)]
        with open(os.path.join(a.out, "data", "fdaaa.jsonl"), "w", encoding="utf-8") as fh:
            for r in rows:
                fh.write(json.dumps(r, sort_keys=True) + "\n")
        manifest["configs"]["fdaaa"] = {"native_split": "fdaaa", "tasks": len(rows), "families": len({r["family_id"] for r in rows}),
                                        "domains": dict(Counter(r["domain"] for r in rows)), "primary_corpus": False,
                                        "file": "data/fdaaa.jsonl"}
        for r in rows:
            manifest["tasks"][r["task_id"]] = r["task_sha256"]
    with open(os.path.join(a.out, "manifest.json"), "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=1, sort_keys=True)
    # the scoring package travels with the data so that the dataset directory scores on its own
    pkg_src = os.path.join(ROOT, "src", "obligationbench")
    pkg_dst = os.path.join(a.out, "obligationbench")
    if os.path.isdir(pkg_dst):
        shutil.rmtree(pkg_dst)
    shutil.copytree(pkg_src, pkg_dst, ignore=shutil.ignore_patterns("__pycache__", "generation"))
    for name in ("LICENSE", "NOTICE.md"):
        src = os.path.join(ROOT, "data", name) if os.path.exists(os.path.join(ROOT, "data", name)) else os.path.join(ROOT, name)
        if os.path.exists(src):
            shutil.copy2(src, os.path.join(a.out, name))
    card = os.path.join(ROOT, "docs", "dataset_card.md")
    if os.path.exists(card):
        shutil.copy2(card, os.path.join(a.out, "README.md"))
    for cfg, info in manifest["configs"].items():
        print("%-10s %5d tasks %4d families  %s" % (cfg, info["tasks"], info["families"], info["domains"]))
    print("wrote", a.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
