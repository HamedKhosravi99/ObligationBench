"""Loading SUFFICE tasks.

A task is a JSON object in the benchmark's native format (one file per task under
``bench/instances_v2/<domain>/<split>/`` in the generator's output, or the
``task_json`` field of a dataset row). This module loads tasks from a task file, a
directory of task files, or a ``.jsonl`` dataset file, and exposes the few accessors
the evaluator needs. The scoring code is in :mod:`suffice.scoring`.
"""
from __future__ import annotations

import glob
import json
import os
from typing import Any, Dict, Iterable, List, Optional, Tuple

Task = Dict[str, Any]

PRIMARY_SPLITS = ("heldout_balanced", "heldout_natural", "dev", "val")
VARIANT_SPLITS = ("heldout_locator", "heldout_onebranch", "heldout_text")
DOMAINS = ("security", "clinical", "drugsafety", "financial")


def task_from_row(row: Dict[str, Any]) -> Task:
    """A dataset row stores the verbatim task as JSON in ``task_json``; a task file
    is the task itself."""
    if "task_json" in row:
        return json.loads(row["task_json"])
    return row


def load_tasks(path: str) -> Dict[str, Task]:
    """Load tasks from a ``.jsonl`` dataset file, a single task ``.json`` file, or a
    directory of task files (searched recursively). Returns ``{task_id: task}``."""
    tasks: Dict[str, Task] = {}
    if os.path.isdir(path):
        files = sorted(glob.glob(os.path.join(path, "**", "*.json"), recursive=True))
        files = [f for f in files if os.path.basename(f) != "manifest.json"]
        for f in files:
            with open(f, encoding="utf-8") as fh:
                t = json.load(fh)
            tasks[t["id"]] = t
        return tasks
    with open(path, encoding="utf-8") as fh:
        if path.endswith(".jsonl"):
            for line in fh:
                if line.strip():
                    t = task_from_row(json.loads(line))
                    tasks[t["id"]] = t
        else:
            t = json.load(fh)
            tasks[t["id"]] = t
    return tasks


def iter_rows(path: str) -> Iterable[Dict[str, Any]]:
    """Iterate over the rows of a ``.jsonl`` dataset file."""
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                yield json.loads(line)


def domain_of(task: Task) -> str:
    """Task domain without the generator's version suffix (``security_v2`` -> ``security``)."""
    return str(task.get("domain", "")).split("_v")[0]


def family_of(task: Task) -> Optional[str]:
    """The template family named in the task's generator notes."""
    meta = task.get("notes_for_annotators")
    if isinstance(meta, str):
        try:
            meta = json.loads(meta)
        except ValueError:
            return None
    return (meta or {}).get("family")


def topology_of(task: Task) -> Optional[str]:
    meta = task.get("notes_for_annotators")
    if isinstance(meta, str):
        try:
            meta = json.loads(meta)
        except ValueError:
            return None
    return (meta or {}).get("topology")


def levels(task: Task) -> Dict[str, int]:
    """Conclusion id -> strength level (1 weakest)."""
    return {c["id"]: int(c["level"]) for c in task["claims"]}


def atom_ids(task: Task) -> List[str]:
    return [a["id"] for a in task["atoms"]]


def resolve_field_path(record: Any, field_path: str) -> Tuple[Any, bool]:
    """Walk a dotted path such as ``severity.0.score`` through nested JSON.
    Returns ``(value, found)``; integer segments index lists."""
    if not field_path:
        return record, True
    cur = record
    for part in field_path.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        elif isinstance(cur, (list, tuple)) and part.lstrip("-").isdigit():
            idx = int(part)
            if -len(cur) <= idx < len(cur):
                cur = cur[idx]
            else:
                return None, False
        else:
            return None, False
    return cur, True
