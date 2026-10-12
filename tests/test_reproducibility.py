"""Round trips, agreement with the original task files, and dataset-library loading."""
import glob
import hashlib
import json
import os
import subprocess
import sys

import pytest

from obligationbench.export import check_round_trip, row_to_task, task_to_row
from obligationbench.tasks import load_tasks

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BENCH = os.environ.get("OBLIGATIONBENCH_BENCH_DIR")  # the generator's output root with the original task files


def test_round_trip_toy(toy_task):
    assert check_round_trip(toy_task, "heldout_balanced")


def test_round_trip_published(rows):
    for cfg, rs in rows.items():
        for r in rs:
            t = row_to_task(r)
            split = {"balanced": "heldout_balanced", "natural": "heldout_natural", "dev": "dev", "val": "val",
                     "locator": "heldout_locator", "onebranch": "heldout_onebranch", "text": "heldout_text", "fdaaa": "fdaaa"}[cfg]
            r2 = task_to_row(t, split, parent_task_id=r["parent_task_id"], generator_seed=r["generator_seed"],
                             generator_version=r["generator_version"])
            assert r2 == r, r["task_id"]


@pytest.mark.skipif(not BENCH, reason="set OBLIGATIONBENCH_BENCH_DIR to the original task files to compare")
def test_published_tasks_identical_to_original_files(rows):
    native = {}
    for p in glob.glob(os.path.join(BENCH, "instances_v2", "*", "*", "*.json")) + glob.glob(os.path.join(BENCH, "instances_fdaaa", "fdaaa-*.json")):
        if os.path.basename(p) == "manifest.json":
            continue
        with open(p, encoding="utf-8") as fh:
            t = json.load(fh)
        native[t["id"]] = t
    n = 0
    for cfg, rs in rows.items():
        for r in rs:
            assert row_to_task(r) == native[r["task_id"]], r["task_id"]
            n += 1
    assert n == 938 + 480 + 240 + 240 + 319


def test_manifest_hashes_match_files(rows, manifest):
    for cfg, rs in rows.items():
        for r in rs:
            t = row_to_task(r)
            h = hashlib.sha256(json.dumps(t, sort_keys=True).encode("utf-8")).hexdigest()
            assert manifest["tasks"][r["task_id"]] == h


def test_generator_seed_recorded(rows, manifest):
    assert manifest["generator_seed"] == 20260801
    assert all(r["generator_seed"] == 20260801 for rs in rows.values() for r in rs)


@pytest.mark.parametrize("hash_seed", ["1", "2"])
def test_corpus_regenerates_from_shipped_inputs(hash_seed):
    """Every task of the primary corpus and of the one-branch, locator, and text
    variants regenerates byte for byte from inputs/ (the harvest reduced to the fields
    the generators read), in a fresh interpreter with the given string-hash seed. An
    earlier generator seeded its family enumeration with hash(domain), which Python
    randomizes per process, so runs in separate processes enumerated different
    families; two seeds check that the output no longer depends on it."""
    env = dict(os.environ, PYTHONHASHSEED=hash_seed)
    env.pop("OBLIGATIONBENCH_BENCH_DIR", None)
    p = subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "reproduce_corpus.py")],
                       env=env, capture_output=True, text=True)
    assert p.returncode == 0, p.stdout[-3000:] + p.stderr[-3000:]
    assert "all published tasks regenerated identically" in p.stdout


def test_reference_scores_and_denominators(data_dir):
    """The reference predictions reproduce the values the paper prints, and every task
    without a prediction is a declared exclusion (data/reference_predictions/<model>/
    EXCLUDED.json: episodes whose model calls timed out); nothing else is missing."""
    p = subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "reproduce_scores.py")],
                       capture_output=True, text=True)
    assert p.returncode == 0, p.stdout[-3000:] + p.stderr[-3000:]
    assert "no other prediction missing" in p.stdout


def test_hf_datasets_loads_local_files(data_dir):
    datasets = pytest.importorskip("datasets")
    ds = datasets.load_dataset("json", data_files={"test": os.path.join(data_dir, "val.jsonl")}, split="test")
    assert len(ds) == 48
    row = ds[0]
    assert set(row) >= {"task_id", "task_json", "reference_atom_values", "specification_view"}
    assert row_to_task(row)["id"] == row["task_id"]
