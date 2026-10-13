#!/usr/bin/env python3
"""Regenerate the corpus into a temporary directory with the vendored generators and
compare every task with the published files.

    python scripts/reproduce_corpus.py [--what all|primary|variants] [--bench inputs]

``--bench`` is the generators' input root; its ``harvest/<domain>/records.jsonl`` are
the harvested records. The default, ``inputs/``, holds the harvest of 2026-08-01
reduced to the fields the generators read (``scripts/reduce_harvest.py``). ``all``
regenerates the primary corpus from the harvest and then the one-branch, locator, and
text variants, in the order they were made; ``primary`` stops after the primary
corpus; ``variants`` copies the published primary corpus and the generator manifest
(``inputs/generator_manifest.json``) in first and regenerates only the variants. The
report gives, per split, how many tasks are identical to the published ones, and the
script exits nonzero unless all are. Expected: every split identical (1,898 tasks;
the FDAAA set comes from its own builder in the PRIME code).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "src"))

from suffice.tasks import DOMAINS, load_tasks  # noqa: E402

NATIVE = {"balanced": "heldout_balanced", "natural": "heldout_natural", "dev": "dev", "val": "val",
          "locator": "heldout_locator", "onebranch": "heldout_onebranch", "text": "heldout_text"}
PRIMARY = ("heldout_balanced", "heldout_natural", "dev", "val")
VARIANTS = ("heldout_onebranch", "heldout_locator", "heldout_text")


def _hash(t) -> str:
    return hashlib.sha256(json.dumps(t, sort_keys=True).encode("utf-8")).hexdigest()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--bench", default=os.path.join(ROOT, "inputs"),
                    help="input root holding harvest/<domain>/records.jsonl (default: inputs/)")
    ap.add_argument("--what", choices=["all", "primary", "variants"], default="all")
    ap.add_argument("--data", default=os.path.join(ROOT, "data"))
    ap.add_argument("--manifest", default=os.path.join(ROOT, "inputs", "generator_manifest.json"),
                    help="the generator's manifest of families and splits (used by --what variants)")
    ap.add_argument("--keep", action="store_true", help="keep the regenerated files")
    a = ap.parse_args(argv)
    published = {}
    for cfg, native in NATIVE.items():
        p = os.path.join(a.data, cfg + ".jsonl")
        if os.path.exists(p):
            published[native] = {tid: _hash(t) for tid, t in load_tasks(p).items()}
    tmp = tempfile.mkdtemp(prefix="suffice-regen-")
    os.symlink(os.path.abspath(os.path.join(a.bench, "harvest")), os.path.join(tmp, "harvest"))
    inst = os.path.join(tmp, "instances_v2")
    os.makedirs(inst)
    if a.what == "variants":
        for cfg in ("balanced", "natural", "dev", "val"):
            for tid, t in load_tasks(os.path.join(a.data, cfg + ".jsonl")).items():
                d = os.path.join(inst, t["domain"].split("_v")[0], NATIVE[cfg])
                os.makedirs(d, exist_ok=True)
                with open(os.path.join(d, tid + ".json"), "w", encoding="utf-8") as fh:
                    json.dump(t, fh, indent=1, sort_keys=True, default=str)
        shutil.copy2(a.manifest, os.path.join(inst, "manifest.json"))
    os.environ["SUFFICE_BENCH_DIR"] = tmp
    import importlib
    import suffice.generation.record_tasks as rt
    import suffice.generation.text_tasks as tt
    importlib.reload(rt)
    importlib.reload(tt)
    from suffice.generation import run_generator
    if a.what in ("all", "primary"):
        run_generator("records", [])
    if a.what in ("all", "variants"):
        run_generator("records", ["--one-branch-per-domain", "60", "--seq-base", "9000"])
        run_generator("records", ["--locator-per-domain", "120"])
        run_generator("text", [])
    targets = {"all": PRIMARY + VARIANTS, "primary": PRIMARY, "variants": VARIANTS}[a.what]
    print("\n| Split | Published | Regenerated identical | Missing | Extra |\n|---|---|---|---|---|")
    ok = True
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
    if a.keep:
        print("\nregenerated files are in", tmp)
    else:
        shutil.rmtree(tmp, ignore_errors=True)
    print("\nall published tasks regenerated identically" if ok else "\nDIFFERENCES")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
