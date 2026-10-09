#!/usr/bin/env python3
"""Regenerate the corpus into a temporary directory with the vendored generator and
compare every task with the published files.

    python scripts/reproduce_corpus.py --bench /path/to/bench --what variants|primary|all [--data data]

``--bench`` is the generator's input root (harvest/<domain>/records.jsonl). For
``variants`` the published primary corpus is copied in first and the locator, one-branch,
and text variants are regenerated from it; for ``primary`` the primary corpus is
regenerated from the harvest. The report says, per split, how many tasks are byte-
identical to the published ones. See docs/benchmark_generation.md for the expected
outcome (variants: locator and text identical; primary: not reproducible today)."""
from __future__ import annotations

import argparse
import glob
import hashlib
import json
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "src"))

from obligationbench.tasks import DOMAINS, load_tasks  # noqa: E402

NATIVE = {"balanced": "heldout_balanced", "natural": "heldout_natural", "dev": "dev", "val": "val",
          "locator": "heldout_locator", "onebranch": "heldout_onebranch", "text": "heldout_text"}


def _hash(t) -> str:
    return hashlib.sha256(json.dumps(t, sort_keys=True).encode("utf-8")).hexdigest()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--bench", required=True)
    ap.add_argument("--what", choices=["variants", "primary", "all"], default="variants")
    ap.add_argument("--data", default=os.path.join(ROOT, "data"))
    a = ap.parse_args(argv)
    published = {}
    for cfg, native in NATIVE.items():
        p = os.path.join(a.data, cfg + ".jsonl")
        if os.path.exists(p):
            published[native] = {tid: _hash(t) for tid, t in load_tasks(p).items()}
    tmp = tempfile.mkdtemp(prefix="obligationbenchegen-")
    os.symlink(os.path.abspath(os.path.join(a.bench, "harvest")), os.path.join(tmp, "harvest"))
    inst = os.path.join(tmp, "instances_v2")
    os.makedirs(inst)
    if a.what in ("variants",):
        for cfg in ("balanced", "natural", "dev", "val"):
            tasks = load_tasks(os.path.join(a.data, cfg + ".jsonl"))
            for tid, t in tasks.items():
                d = os.path.join(inst, t["domain"].split("_v")[0], NATIVE[cfg])
                os.makedirs(d, exist_ok=True)
                with open(os.path.join(d, tid + ".json"), "w", encoding="utf-8") as fh:
                    json.dump(t, fh, indent=1, sort_keys=True, default=str)
        shutil.copy2(os.path.join(a.bench, "instances_v2", "manifest.json"), os.path.join(inst, "manifest.json"))
    os.environ["OBLIGATIONBENCH_BENCH_DIR"] = tmp
    import importlib
    import obligationbench.generation.record_tasks as rt
    import obligationbench.generation.text_tasks as tt
    importlib.reload(rt); importlib.reload(tt)
    from obligationbench.generation import run_generator
    if a.what in ("primary", "all"):
        run_generator("records", [])
    if a.what in ("variants", "all"):
        run_generator("records", ["--locator-per-domain", "120"])
        run_generator("records", ["--one-branch-per-domain", "60"])
        run_generator("text", [])
    print("\n| Split | Published | Regenerated identical | Missing | Extra |\n|---|---|---|---|---|")
    ok = True
    targets = [s for s in NATIVE.values() if (a.what != "variants" or s in ("heldout_locator", "heldout_onebranch", "heldout_text"))
               and (a.what != "primary" or s in ("heldout_balanced", "heldout_natural", "dev", "val"))]
    for split in targets:
        regen = {}
        for dom in DOMAINS:
            d = os.path.join(inst, dom, split)
            if os.path.isdir(d):
                regen.update({tid: _hash(t) for tid, t in load_tasks(d).items()})
        pub = published.get(split, {})
        same = sum(1 for tid, h in pub.items() if regen.get(tid) == h)
        missing = sum(1 for tid in pub if tid not in regen)
        extra = sum(1 for tid in regen if tid not in pub)
        print("| %s | %d | %d | %d | %d |" % (split, len(pub), same, missing, extra))
        ok = ok and same == len(pub) and not extra
    print("\nregenerated files are in", tmp)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
