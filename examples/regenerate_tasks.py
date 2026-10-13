#!/usr/bin/env python3
"""Example D: run the generator on a few harvested records with the fixed seed, twice,
and check that the task ids and reference labels are identical.

Needs the harvest (SUFFICE_BENCH_DIR pointing at a directory with
harvest/<domain>/records.jsonl). Uses the first 40 security records and small quotas
so it runs in seconds. To regenerate the published variants from the published primary
corpus, use scripts/reproduce_corpus.py."""
import glob
import hashlib
import importlib
import json
import os
import shutil
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

bench = os.environ.get("SUFFICE_BENCH_DIR")
if not bench or not os.path.exists(os.path.join(bench, "harvest", "security", "records.jsonl")):
    sys.exit("set SUFFICE_BENCH_DIR to a directory holding harvest/security/records.jsonl")

runs = []
for i in range(2):
    d = tempfile.mkdtemp(prefix="suffice-example-")
    os.makedirs(os.path.join(d, "harvest", "security"))
    with open(os.path.join(bench, "harvest", "security", "records.jsonl"), encoding="utf-8") as src, \
            open(os.path.join(d, "harvest", "security", "records.jsonl"), "w", encoding="utf-8") as out:
        for k, line in enumerate(src):
            if k >= 40:
                break
            out.write(line)
    os.environ["SUFFICE_BENCH_DIR"] = d
    import suffice.generation.record_tasks as rt
    importlib.reload(rt)
    from suffice.generation import run_generator
    run_generator("records", ["--domains", "security", "--balanced-per-domain", "4", "--natural-per-domain", "2", "--dev-per-domain", "2"])
    files = sorted(glob.glob(os.path.join(d, "instances_v2", "security", "*", "*.json")))
    runs.append({os.path.relpath(f, d): hashlib.sha256(open(f, "rb").read()).hexdigest() for f in files})
    if i == 0:
        t = json.load(open(files[0], encoding="utf-8"))
        print("example task", t["id"], "reference values", {a["id"]: a["gold_value"] for a in t["atoms"]})
    shutil.rmtree(d)
os.environ["SUFFICE_BENCH_DIR"] = bench
print("run 1: %d task files; run 2: %d; identical: %s" % (len(runs[0]), len(runs[1]), runs[0] == runs[1]))
