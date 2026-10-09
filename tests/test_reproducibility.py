"""Round trips, agreement with the original task files, and dataset-library loading."""
import glob
import hashlib
import json
import os

import pytest

from obligationbench.export import check_round_trip, row_to_task, task_to_row
from obligationbench.tasks import load_tasks

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


def test_fixed_seed_generation_is_deterministic(tmp_path):
    """Two runs of the record generator on the same harvest with the same seed produce
    identical task files. Uses the first 40 harvested security records and small quotas
    so the test runs in seconds; requires OBLIGATIONBENCH_BENCH_DIR for the harvest."""
    if not BENCH:
        pytest.skip("set OBLIGATIONBENCH_BENCH_DIR to the harvest")
    from obligationbench.generation import run_generator
    outs = []
    for i in range(2):
        d = tmp_path / ("run%d" % i)
        (d / "harvest" / "security").mkdir(parents=True)
        src = os.path.join(BENCH, "harvest", "security", "records.jsonl")
        with open(src, encoding="utf-8") as fh, open(d / "harvest" / "security" / "records.jsonl", "w", encoding="utf-8") as out:
            for k, line in enumerate(fh):
                if k >= 40:
                    break
                out.write(line)
        os.environ["OBLIGATIONBENCH_BENCH_DIR"] = str(d)
        try:
            import importlib
            import obligationbench.generation.record_tasks as rt
            importlib.reload(rt)
            rc = run_generator("records", ["--domains", "security", "--balanced-per-domain", "4", "--natural-per-domain", "2", "--dev-per-domain", "2"])
        finally:
            os.environ["OBLIGATIONBENCH_BENCH_DIR"] = BENCH
            importlib.reload(rt)
        assert rc == 0
        files = sorted(glob.glob(str(d / "instances_v2" / "security" / "*" / "*.json")))
        assert files
        outs.append({os.path.relpath(f, d): hashlib.sha256(open(f, "rb").read()).hexdigest() for f in files})
    assert outs[0] == outs[1]


def test_hf_datasets_loads_local_files(data_dir):
    datasets = pytest.importorskip("datasets")
    ds = datasets.load_dataset("json", data_files={"test": os.path.join(data_dir, "val.jsonl")}, split="test")
    assert len(ds) == 48
    row = ds[0]
    assert set(row) >= {"task_id", "task_json", "reference_atom_values", "specification_view"}
    assert row_to_task(row)["id"] == row["task_id"]
