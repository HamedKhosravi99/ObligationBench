"""Conversion between the native task format and the dataset rows published on
Hugging Face, in both directions, and the row schema.

A dataset row flattens what a user needs to read without parsing the task, and
carries the verbatim task in ``task_json`` so that the native format is recovered
exactly (``row_to_task``). Fields are grouped as

* identity: ``task_id``, ``family_id``, ``domain``, ``corpus_split``, ``variant``,
  ``parent_task_id``, ``topology``, ``source_dataset``, ``source_record_id``;
* agent-visible content: ``request``, ``scope``, ``conclusions``,
  ``conclusion_order``, ``evidence_atoms`` (each check's tool, parameters or
  candidate fields or text source, predicate, availability), ``sufficient_routes``,
  ``constraints``, ``specification_view`` (the same content as one JSON object,
  what an agent given the rule sees);
* evaluator-only labels, never to be shown to an agent: ``reference_atom_values``,
  ``reference_supported_conclusions``, ``strongest_supported_level``,
  ``answerable``;
* the record the task is about: ``record_json`` (the evidence view, which an agent
  reaches only through the evidence actions);
* provenance: ``generator_seed``, ``generator_version``, ``task_sha256``;
* ``task_json``: the complete native task.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, List, Optional

from .env import RecordEnv
from .scoring import ceiling_level, supported
from .tasks import Task, domain_of, family_of, levels, topology_of

SCHEMA_VERSION = "1.0"
GENERATOR_VERSION = "obligationbench corpus of 2026-08-01 (generator v2); variants of 2026-10-08/09"

SOURCE_DATASET = {
    "security": "GitHub Advisory Database via OSV",
    "clinical": "ClinicalTrials.gov",
    "drugsafety": "openFDA drug enforcement reports",
    "financial": "SEC EDGAR XBRL company facts",
}

VARIANT_OF_SPLIT = {
    "heldout_balanced": "none", "heldout_natural": "none", "dev": "none", "val": "none",
    "heldout_locator": "locator", "heldout_onebranch": "onebranch", "heldout_text": "text",
    "fdaaa": "fdaaa",
}
CORPUS_SPLIT_NAME = {"heldout_balanced": "balanced", "heldout_natural": "natural", "dev": "dev", "val": "val"}

ROW_FIELDS = [
    "task_id", "family_id", "domain", "corpus_split", "variant", "parent_task_id", "topology",
    "source_dataset", "source_record_id", "request", "scope", "conclusions", "conclusion_order",
    "evidence_atoms", "sufficient_routes", "constraints", "specification_view",
    "reference_atom_values", "reference_supported_conclusions", "strongest_supported_level",
    "answerable", "generator_seed", "generator_version", "schema_version", "task_sha256",
    "record_json", "task_json",
]
EVALUATOR_ONLY_FIELDS = ["reference_atom_values", "reference_supported_conclusions",
                         "strongest_supported_level", "answerable"]


def task_sha256(task: Task) -> str:
    return hashlib.sha256(json.dumps(task, sort_keys=True).encode("utf-8")).hexdigest()


def task_to_row(task: Task, split: str, parent_task_id: Optional[str] = None,
                generator_seed: int = 20260801, generator_version: str = GENERATOR_VERSION) -> Dict[str, Any]:
    if split not in VARIANT_OF_SPLIT:
        raise ValueError("unknown split %r" % split)
    env = RecordEnv(task)
    view = env.agent_view()
    lv = levels(task)
    supp = supported(task)
    atoms: List[Dict[str, Any]] = []
    for a in task["atoms"]:
        r = a.get("resolver") or {}
        hint = a.get("spec_hint") or {}
        atoms.append({
            "id": a["id"],
            "available": bool(r),
            "tool": r.get("tool"),
            "record_id": (r.get("params") or {}).get("record_id") or (hint.get("source") or {}).get("record_id"),
            "field_path": (r.get("params") or {}).get("field_path") if not hint.get("candidates") else None,
            "candidate_fields": list(hint.get("candidates") or []) or None,
            "text_source": dict(hint["source"]) if hint.get("source") else None,
            "description": hint.get("what"),
            "predicate": r.get("attest") if r.get("tool") == "inspect_record" else None,
        })
    routes = [{"conclusion": c, "literals": list(route)}
              for c, rs in sorted(task["gold_licenses"].items()) for route in rs]
    sup = sorted(c for c, ok in supp.items() if ok)
    row = {
        "task_id": task["id"],
        "family_id": family_of(task),
        "domain": domain_of(task),
        "corpus_split": CORPUS_SPLIT_NAME.get(split),
        "variant": VARIANT_OF_SPLIT[split],
        "parent_task_id": parent_task_id,
        "topology": topology_of(task),
        "source_dataset": SOURCE_DATASET.get(domain_of(task), "ClinicalTrials.gov" if split == "fdaaa" else None),
        "source_record_id": task.get("seed"),
        "request": task.get("user_prompt"),
        "scope": task.get("scope"),
        "conclusions": [{"id": c["id"], "level": int(c["level"]), "text": c["text"]} for c in task["claims"]],
        "conclusion_order": [list(p) for p in task.get("order", [])],
        "evidence_atoms": atoms,
        "sufficient_routes": routes,
        "constraints": list(task.get("phi") or []),
        "specification_view": json.dumps(view, sort_keys=True),
        "reference_atom_values": [{"id": a["id"], "value": a["gold_value"]} for a in task["atoms"]],
        "reference_supported_conclusions": sup,
        "strongest_supported_level": ceiling_level(task),
        "answerable": ceiling_level(task) > 0,
        "generator_seed": generator_seed,
        "generator_version": generator_version,
        "schema_version": SCHEMA_VERSION,
        "task_sha256": task_sha256(task),
        "record_json": json.dumps(task.get("records") or {}, sort_keys=True),
        "task_json": json.dumps(task, sort_keys=True),
    }
    assert list(row) == ROW_FIELDS
    return row


def row_to_task(row: Dict[str, Any]) -> Task:
    return json.loads(row["task_json"])


def agent_visible(row: Dict[str, Any]) -> Dict[str, Any]:
    """The row without the evaluator-only labels (and without the record, which an
    agent reaches through the evidence actions)."""
    return {k: v for k, v in row.items() if k not in EVALUATOR_ONLY_FIELDS and k not in ("record_json", "task_json")}


def check_round_trip(task: Task, split: str) -> bool:
    return row_to_task(task_to_row(task, split)) == task
