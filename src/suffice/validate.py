"""Integrity checks for a corpus of SUFFICE tasks.

``validate_tasks`` checks every task's structure with the original schema validator
and the benchmark's semantic invariants; ``validate_corpus`` checks the published
counts and the relations between the primary corpus and its derived variants.
Both return a list of problems (empty when everything holds) so that a caller can
print them or fail.
"""
from __future__ import annotations

import json
import os
import tempfile
from collections import Counter, defaultdict
from typing import Any, Dict, Iterable, List, Optional, Sequence

from .env import RecordEnv
from .instance_schema import SchemaError, load_instance
from .scoring import holds, reference_values, supported
from .tasks import Task, domain_of, family_of, levels, topology_of

EXPECTED_PRIMARY = {"heldout_balanced": 480, "heldout_natural": 218, "dev": 192, "val": 48}
EXPECTED_VARIANTS = {"heldout_locator": 480, "heldout_onebranch": 240, "heldout_text": 240}
EXPECTED_FDAAA = 319
EXPECTED_FAMILIES = 120
EXPECTED_TOTAL = 938
PER_DOMAIN = {"heldout_balanced": 120, "dev": 48, "val": 12}
NATURAL_PER_DOMAIN = {"security": 60, "clinical": 60, "drugsafety": 60, "financial": 38}


def _schema_check(task: Task) -> Optional[str]:
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, task["id"] + ".json")
        with open(p, "w", encoding="utf-8") as fh:
            json.dump(task, fh)
        try:
            load_instance(p, validate=True)
        except (SchemaError, Exception) as exc:  # noqa: BLE001
            return "schema: %s" % exc
    return None


def _executes_to_reference(task: Task) -> Optional[str]:
    """Every check with a resolver that reads a field must evaluate, on the stored
    record, to its reference value (the generator's verify-or-drop rule). A read that
    returns no value settles nothing; the FDAAA set records such checks as "U"."""
    env = RecordEnv(task)
    for a in task["atoms"]:
        r = a.get("resolver")
        if not r or r.get("tool") != "inspect_record":
            continue
        p = r.get("params") or {}
        env.inspect_record(p.get("record_id"), p.get("field_path"))
        got = env.ledger.get(a["id"], "U")   # no attestation: the field is absent (FDAAA set: "U")
        if got != a["gold_value"]:
            return "check %s executes to %s, reference %s" % (a["id"], got, a["gold_value"])
    return None


def validate_task(task: Task, schema: bool = True) -> List[str]:
    probs: List[str] = []
    if schema:
        e = _schema_check(task)
        if e:
            probs.append(e)
    ids = [c["id"] for c in task.get("claims", [])]
    lv = levels(task) if ids else {}
    if len(set(ids)) != len(ids):
        probs.append("duplicate conclusion ids")
    aids = [a["id"] for a in task.get("atoms", [])]
    if len(set(aids)) != len(aids):
        probs.append("duplicate check ids")
    for a in task.get("atoms", []):
        if a.get("gold_value") not in ("T", "F", "U"):
            probs.append("check %s has no reference value" % a["id"])
    # strength order: pairs reference conclusions and agree with levels
    for w, s in task.get("order", []):
        if w not in lv or s not in lv:
            probs.append("order pair (%s, %s) names an unknown conclusion" % (w, s))
        elif lv[w] >= lv[s]:
            probs.append("order pair (%s, %s) contradicts the levels" % (w, s))
    # routes: reference known checks, literals well formed, every conclusion has a route family
    for c in ids:
        if c not in task.get("gold_licenses", {}):
            probs.append("conclusion %s has no route family" % c)
    for c, routes in task.get("gold_licenses", {}).items():
        if c not in lv:
            probs.append("routes for unknown conclusion %s" % c)
        if not routes:
            probs.append("conclusion %s has an empty route family" % c)
        for r in routes:
            for lit in r:
                if lit.lstrip("!") not in aids:
                    probs.append("route of %s names unknown check %s" % (c, lit))
    # support is monotone along the order: a supported stronger conclusion implies its weaker ones
    supp = supported(task)
    for w, s in task.get("order", []):
        if supp.get(s) and not supp.get(w):
            probs.append("%s is supported but the weaker %s is not" % (s, w))
    # resolvers execute to the reference values
    e = _executes_to_reference(task)
    if e:
        probs.append(e)
    # text-evidence checks: a source text exists in the record
    for a in task.get("atoms", []):
        r = a.get("resolver") or {}
        if r.get("tool") == "attest_atom":
            src = (a.get("spec_hint") or {}).get("source") or {}
            env = RecordEnv(task)
            obs = env.read_text(src.get("record_id"), src.get("field_path"))
            if "error" in obs:
                probs.append("text check %s has no readable source text" % a["id"])
    # locator-uncertain checks: the true field is among the candidates and every candidate is present
    for a in task.get("atoms", []):
        hint = a.get("spec_hint") or {}
        if hint.get("candidates"):
            p = (a.get("resolver") or {}).get("params") or {}
            if p.get("field_path") not in hint["candidates"]:
                probs.append("locator check %s: true field not among its candidates" % a["id"])
            env = RecordEnv(task)
            for cand in hint["candidates"]:
                if "error" in env.inspect_record(p.get("record_id"), cand):
                    probs.append("locator check %s: candidate %s is not present in the record" % (a["id"], cand))
    return probs


def validate_tasks(tasks: Iterable[Task], schema: bool = True) -> Dict[str, List[str]]:
    out: Dict[str, List[str]] = {}
    for t in tasks:
        p = validate_task(t, schema=schema)
        if p:
            out[t["id"]] = p
    return out


def validate_corpus(by_split: Dict[str, Dict[str, Task]], fdaaa: Optional[Dict[str, Task]] = None) -> List[str]:
    """Counts and relations of the published corpus. ``by_split`` maps each native
    split name to its tasks."""
    probs: List[str] = []
    for split, n in EXPECTED_PRIMARY.items():
        got = len(by_split.get(split, {}))
        if got != n:
            probs.append("%s has %d tasks, expected %d" % (split, got, n))
    for split, n in EXPECTED_VARIANTS.items():
        if split in by_split and len(by_split[split]) != n:
            probs.append("%s has %d tasks, expected %d" % (split, len(by_split[split]), n))
    if fdaaa is not None and len(fdaaa) != EXPECTED_FDAAA:
        probs.append("fdaaa has %d tasks, expected %d" % (len(fdaaa), EXPECTED_FDAAA))
    primary_ids: List[str] = []
    fams: set = set()
    for split in EXPECTED_PRIMARY:
        primary_ids += list(by_split.get(split, {}))
        fams |= {family_of(t) for t in by_split.get(split, {}).values()}
    if len(primary_ids) != len(set(primary_ids)):
        probs.append("task ids repeat across primary splits")
    if len(set(primary_ids)) != EXPECTED_TOTAL and all(s in by_split for s in EXPECTED_PRIMARY):
        probs.append("primary corpus has %d unique tasks, expected %d" % (len(set(primary_ids)), EXPECTED_TOTAL))
    if all(s in by_split for s in EXPECTED_PRIMARY) and len(fams) != EXPECTED_FAMILIES:
        probs.append("primary corpus has %d families, expected %d" % (len(fams), EXPECTED_FAMILIES))
    for split, per in PER_DOMAIN.items():
        c = Counter(domain_of(t) for t in by_split.get(split, {}).values())
        for d, n in c.items():
            if n != per:
                probs.append("%s/%s has %d tasks, expected %d" % (split, d, n, per))
    c = Counter(domain_of(t) for t in by_split.get("heldout_natural", {}).values())
    for d, n in NATURAL_PER_DOMAIN.items():
        if c.get(d, 0) != n:
            probs.append("heldout_natural/%s has %d tasks, expected %d" % (d, c.get(d, 0), n))
    # families are held out whole: dev/val families disjoint from held-out families
    held = {family_of(t) for s in ("heldout_balanced", "heldout_natural") for t in by_split.get(s, {}).values()}
    devval = {family_of(t) for s in ("dev", "val") for t in by_split.get(s, {}).values()}
    if held & devval:
        probs.append("families shared between held-out and development/validation: %s" % sorted(held & devval)[:3])
    # balanced: nested/branching halves, answerable count
    bal = by_split.get("heldout_balanced", {})
    if bal:
        topo = Counter(topology_of(t) for t in bal.values())
        if topo.get("nested") != 240 or topo.get("branching") != 240:
            probs.append("balanced topology counts %s, expected 240/240" % dict(topo))
        answerable = sum(1 for t in bal.values() if any(supported(t).values()))
        if answerable != 396:
            probs.append("balanced has %d answerable tasks, expected 396" % answerable)
    # natural: every conclusion supported
    for t in by_split.get("heldout_natural", {}).values():
        if not all(supported(t).values()):
            probs.append("natural task %s has an unsupported conclusion" % t["id"])
    # locator variant: one parent per task, same conclusions and reference values
    loc = by_split.get("heldout_locator", {})
    if loc and bal:
        parents = parent_map(loc, bal)
        if len(parents) != len(loc):
            probs.append("%d locator tasks have no parent in the balanced split" % (len(loc) - len(parents)))
        if len(set(parents.values())) != len(parents):
            probs.append("locator parents are not unique")
        for tid, pid in parents.items():
            if reference_values(loc[tid]) != reference_values(bal[pid]):
                probs.append("locator task %s differs from its parent in reference values" % tid)
    return probs


def parent_map(variant: Dict[str, Task], primary: Dict[str, Task]) -> Dict[str, str]:
    """Locator-uncertain task id -> the balanced task it was derived from (same
    domain, record, family, and conclusions)."""
    key = lambda t: (domain_of(t), t.get("seed"), family_of(t), json.dumps(t["claims"], sort_keys=True))
    idx = {key(t): tid for tid, t in primary.items()}
    return {tid: idx[key(t)] for tid, t in variant.items() if key(t) in idx}
