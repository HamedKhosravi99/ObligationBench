"""Integrity of the published dataset files (data/*.jsonl built by scripts/prepare_hf_dataset.py)."""
import json
from collections import Counter

import pytest

from obligationbench.export import ROW_FIELDS, row_to_task, task_sha256
from obligationbench.tasks import domain_of, family_of

PRIMARY = {"balanced": 480, "natural": 218, "dev": 192, "val": 48}
VARIANTS = {"locator": 480, "onebranch": 240, "text": 240, "fdaaa": 319}
DOMAINS = ("security", "clinical", "drugsafety", "financial")


def test_primary_split_counts(rows):
    for cfg, n in PRIMARY.items():
        assert len(rows[cfg]) == n, cfg
    assert sum(len(rows[c]) for c in PRIMARY) == 938


def test_variant_counts(rows):
    for cfg, n in VARIANTS.items():
        assert len(rows[cfg]) == n, cfg


def test_primary_ids_unique_and_disjoint(rows):
    ids = [r["task_id"] for c in PRIMARY for r in rows[c]]
    assert len(ids) == len(set(ids)) == 938


def test_variant_ids_disjoint_from_primary(rows):
    primary = {r["task_id"] for c in PRIMARY for r in rows[c]}
    for cfg in VARIANTS:
        assert not primary & {r["task_id"] for r in rows[cfg]}, cfg


def test_domains(rows):
    for cfg, per in (("balanced", 120), ("dev", 48), ("val", 12), ("locator", 120), ("onebranch", 60)):
        c = Counter(r["domain"] for r in rows[cfg])
        assert set(c) == set(DOMAINS) and all(v == per for v in c.values()), (cfg, c)
    assert Counter(r["domain"] for r in rows["natural"]) == {"security": 60, "clinical": 60, "drugsafety": 60, "financial": 38}
    assert Counter(r["domain"] for r in rows["text"]) == {"clinical": 120, "security": 120}
    assert Counter(r["domain"] for r in rows["fdaaa"]) == {"fdaaa_ctgov": 319}


def test_families(rows):
    fams = {r["family_id"] for c in PRIMARY for r in rows[c]}
    assert len(fams) == 120
    held = {r["family_id"] for c in ("balanced", "natural") for r in rows[c]}
    devval = {r["family_id"] for c in ("dev", "val") for r in rows[c]}
    assert len(held) == 60 and len(devval) == 60 and not held & devval
    assert {r["family_id"] for r in rows["onebranch"]} <= held
    assert {r["family_id"] for r in rows["locator"]} == {r["family_id"] for r in rows["balanced"]}


def test_balanced_structure(rows):
    bal = rows["balanced"]
    assert Counter(r["topology"] for r in bal) == {"nested": 240, "branching": 240}
    assert sum(1 for r in bal if r["answerable"]) == 396
    assert sum(1 for r in bal if r["strongest_supported_level"] == 0) == 84


def test_natural_every_conclusion_supported(rows):
    for r in rows["natural"]:
        assert len(r["reference_supported_conclusions"]) == len(r["conclusions"]), r["task_id"]


def test_corpus_split_and_variant_fields(rows):
    for cfg in PRIMARY:
        assert all(r["corpus_split"] == cfg and r["variant"] == "none" and r["parent_task_id"] is None for r in rows[cfg])
    for cfg in VARIANTS:
        assert all(r["corpus_split"] is None and r["variant"] == cfg for r in rows[cfg])


def test_locator_parents(rows):
    bal = {r["task_id"]: r for r in rows["balanced"]}
    parents = [r["parent_task_id"] for r in rows["locator"]]
    assert all(p in bal for p in parents) and len(set(parents)) == 480
    for r in rows["locator"]:
        p = bal[r["parent_task_id"]]
        assert r["reference_atom_values"] == p["reference_atom_values"]
        assert r["conclusions"] == p["conclusions"] and r["domain"] == p["domain"]
        assert any(a["candidate_fields"] for a in r["evidence_atoms"])


def test_row_schema_and_hashes(rows, manifest):
    for cfg, rs in rows.items():
        for r in rs:
            assert set(r) == set(ROW_FIELDS), r["task_id"]   # files are written with sorted keys
            task = row_to_task(r)
            assert task["id"] == r["task_id"]
            assert task_sha256(task) == r["task_sha256"] == manifest["tasks"][r["task_id"]]
            assert r["domain"] == domain_of(task) and r["family_id"] == family_of(task)


def test_evaluator_labels_consistent_with_task(rows):
    from obligationbench.scoring import supported
    for cfg, rs in rows.items():
        for r in rs:
            task = row_to_task(r)
            assert {x["id"]: x["value"] for x in r["reference_atom_values"]} == {a["id"]: a["gold_value"] for a in task["atoms"]}
            assert r["reference_supported_conclusions"] == sorted(c for c, ok in supported(task).items() if ok)


def test_specification_view_hides_labels(rows):
    for cfg, rs in rows.items():
        for r in rs[:50]:
            view = json.loads(r["specification_view"])
            assert "gold_value" not in r["specification_view"]
            for c in view["checks"]:
                assert "value" not in c and "gold" not in json.dumps(c)


def test_deterministic_serialization(rows):
    for cfg, rs in rows.items():
        for r in rs[:20]:
            assert json.dumps(r, sort_keys=True) == json.dumps(json.loads(json.dumps(r, sort_keys=True)), sort_keys=True)
