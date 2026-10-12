"""Scoring ObligationBench predictions.

The endpoints are those of the paper (Section 5, "Scoring"), computed from executable
predicates on the stored record and from a replay of the agent's recorded actions;
no language model or person judges an answer, and nothing here depends on how the
agent was built.

Five things are kept apart:

* **truth under the intended standard**: which conclusions the record supports,
  computed from the task's stored check values (``supported``);
* **what the agent's own actions established**: the ledger a replay of its recorded
  reads and attestations produces (``RecordEnv``), and the conclusions that ledger
  licenses (``established``);
* **what the agent stated**: the ``stated`` list of a prediction;
* **authorization under a supplied or learned program**: not a scoring input; an
  enforcement method decides what may be stated, the scorer only measures what was;
* **the final rendered conclusion**: for an enforced agent the runtime's statement
  belongs in ``stated`` like any other.

Prediction format, one JSON object per line::

    {"task_id": "sec-v2-0114", "stated": ["C1"],
     "actions": [{"inspect_record": ["GHSA-5pqf-rvm7-3wgw", "details"]},
                 {"read_text": ["GHSA-5pqf-rvm7-3wgw", "details"]},
                 {"attest_atom": ["E2", "T", "a verbatim quote from the text"]}]}

``stated`` lists the conclusion ids the agent stated (empty: it abstained).
``actions`` lists its evidence actions in order; ``reads`` (a list of
``[record_id, field_path]`` pairs) is accepted as the legacy form for
``inspect_record`` reads only. Without actions or reads, the premature-conclusion
rate and evidence value are not computed.

Endpoints
    false authorization   share of tasks on which some stated conclusion is not
                          supported by the record
    premature             share of tasks on which some stated conclusion was not
                          established by the agent's own actions, directly or
                          through a stronger established conclusion
    utility               100 x level of the strongest supported stated conclusion
                          / top level (levels 1 to 3: 33.3, 66.7, 100); 0 when
                          nothing supported was stated ("supported utility")
    evidence value        100 x level of the strongest conclusion the actions
                          establish / top level
    emission rate         share of answerable tasks (some conclusion is supported)
                          on which the agent stated anything
    evidence recall       share of the checks on the task's routes that the actions
                          settled
    tool calls            recorded evidence actions (``tool_calls``), and the
                          distinct call classes among them (``distinct_calls``),
                          which is what PRIME's budget charges: its executor serves
                          an identical repeat from a cache
    resolver error        text-evidence tasks: share of accepted attestations whose
                          value differs from the reference value
"""
from __future__ import annotations

import json
from collections import defaultdict
from typing import Any, Dict, Iterable, List, Optional, Sequence

from .env import RecordEnv
from .tasks import Task, domain_of, family_of, levels, topology_of

VALID_PREDICTION_KEYS = {"task_id", "stated", "actions", "reads", "agent", "model", "budget", "calls", "note"}


class PredictionError(ValueError):
    pass


def validate_prediction(p: Dict[str, Any], task: Optional[Task] = None, strict: bool = False) -> None:
    """Raise PredictionError on a malformed prediction record. A stated conclusion id
    that the task does not define is an *unsupported statement* and scores as false
    authorization (the paper's rule: an agent that emits a conclusion that does not
    exist has stated something the record does not support); with ``strict=True`` it
    raises instead."""
    if not isinstance(p, dict) or "task_id" not in p:
        raise PredictionError("a prediction is an object with a task_id, got %r" % (p,))
    stated = p.get("stated", [])
    if not isinstance(stated, list) or not all(isinstance(c, str) for c in stated):
        raise PredictionError("%s: stated must be a list of conclusion ids" % p["task_id"])
    if "reads" in p and (not isinstance(p["reads"], list) or
                         not all(isinstance(r, (list, tuple)) and len(r) == 2 for r in p["reads"])):
        raise PredictionError("%s: reads must be a list of [record_id, field_path] pairs" % p["task_id"])
    if "actions" in p and not isinstance(p["actions"], list):
        raise PredictionError("%s: actions must be a list" % p["task_id"])
    if task is not None and strict:
        ids = {c["id"] for c in task["claims"]}
        bad = [c for c in stated if c not in ids]
        if bad:
            raise PredictionError("%s: stated conclusion(s) not in the task: %s" % (p["task_id"], bad))


def holds(route: Sequence[str], values: Dict[str, str]) -> bool:
    """A route holds when each literal does: an atom id needs the value T, its
    negation (``"!E3"``) needs F. An unsettled atom satisfies neither."""
    return all((values.get(a[1:]) == "F") if a.startswith("!") else (values.get(a) == "T")
               for a in route)


def reference_values(task: Task) -> Dict[str, str]:
    """Check id -> reference value (``T``/``F``), computed by the generator by running
    each resolver on the stored record (or, for text-evidence checks, from the
    structured field withheld from the agent)."""
    return {a["id"]: a["gold_value"] for a in task["atoms"]}


def supported(task: Task) -> Dict[str, bool]:
    """Conclusions the record supports under the intended standard: some route whose
    literals all hold on the reference values."""
    gold = reference_values(task)
    return {c: any(holds(r, gold) for r in routes) for c, routes in task["gold_licenses"].items()}


def ceiling_level(task: Task) -> int:
    lv = levels(task)
    return max([lv[c] for c, ok in supported(task).items() if ok] + [0])


def established(task: Task, ledger: Dict[str, str]) -> set:
    """Conclusions a ledger establishes: those with a route all of whose literals the
    ledger settles the right way, plus every weaker conclusion (the task's ``order``
    lists ``[weaker, stronger]`` pairs)."""
    licensed = {c for c, routes in task["gold_licenses"].items() if any(holds(r, ledger) for r in routes)}
    weaker = defaultdict(set)
    for w, s in task.get("order", []):
        weaker[s].add(w)
    out: set = set()
    stack = list(licensed)
    while stack:
        c = stack.pop()
        if c not in out:
            out.add(c)
            stack.extend(weaker[c])
    return out


def route_atoms(task: Task) -> set:
    return {lit.lstrip("!") for routes in task["gold_licenses"].values() for r in routes for lit in r}


def score_task(task: Task, stated: Sequence[str], actions: Optional[Sequence[Any]] = None) -> Dict[str, Any]:
    """Score one prediction. ``actions`` is the recorded action list (see the module
    docstring); ``None`` scores the statement alone."""
    lv = levels(task)
    top = max(lv.values())
    supp = supported(task)
    ceiling = max([lv[c] for c, ok in supp.items() if ok] + [0])
    best = max([lv.get(c, 0) for c in stated if supp.get(c, False)] + [0])
    row: Dict[str, Any] = {
        "task_id": task["id"],
        "domain": domain_of(task),
        "family": family_of(task),
        "topology": topology_of(task),
        "record": task.get("seed"),
        "false_authorization": int(any(not supp.get(c, False) for c in stated)),  # unknown ids are unsupported
        "invalid_conclusion_ids": sorted(c for c in stated if c not in lv),
        "utility": 100.0 * best / top,
        "stated": int(bool(stated)),
        "answerable": int(ceiling > 0),
        "ceiling_level": ceiling,
    }
    if actions is not None:
        env = RecordEnv(task)
        env.replay(actions)
        est = established(task, env.ledger)
        on_routes = route_atoms(task)
        row["premature"] = int(any(c not in est for c in stated))
        row["evidence_value"] = 100.0 * max([lv[c] for c in est] + [0]) / top
        row["reads"] = len(env.reads)
        row["tool_calls"] = len(env.actions)
        row["distinct_calls"] = env.calls
        row["conflicted_checks"] = len(env.conflicts)
        row["evidence_recall"] = (sum(1 for a in on_routes if a in env.ledger) / len(on_routes)) if on_routes else 0.0
        gold = reference_values(task)
        acc = [a for a in env.attestations if a.get("accepted")]
        if any((a.get("resolver") or {}).get("tool") == "attest_atom" for a in task["atoms"]):
            row["attestations_accepted"] = len(acc)
            row["attestations_rejected"] = len(env.attestations) - len(acc)
            row["attestations_wrong"] = sum(1 for a in acc if a["value"] != gold.get(a["atom_id"]))
    return row


def summarize(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    n = len(rows)
    if n == 0:
        return {"n": 0}
    answerable = [r for r in rows if r["answerable"]]
    out: Dict[str, Any] = {
        "n": n,
        "false_authorization_pct": 100.0 * sum(r["false_authorization"] for r in rows) / n,
        "utility": sum(r["utility"] for r in rows) / n,
        "emission_rate_pct": (100.0 * sum(r["stated"] for r in answerable) / len(answerable)) if answerable else float("nan"),
        "abstention_pct": 100.0 * sum(1 - r["stated"] for r in rows) / n,
    }
    with_actions = [r for r in rows if "premature" in r]
    if with_actions:
        m = len(with_actions)
        out["premature_pct"] = 100.0 * sum(r["premature"] for r in with_actions) / m
        out["evidence_value"] = sum(r["evidence_value"] for r in with_actions) / m
        out["evidence_recall_pct"] = 100.0 * sum(r["evidence_recall"] for r in with_actions) / m
        out["mean_reads"] = sum(r["reads"] for r in with_actions) / m
        out["mean_tool_calls"] = sum(r["tool_calls"] for r in with_actions) / m
        out["mean_distinct_calls"] = sum(r["distinct_calls"] for r in with_actions) / m
    text = [r for r in rows if "attestations_accepted" in r]
    if text:
        acc = sum(r["attestations_accepted"] for r in text)
        out["attestations_accepted"] = acc
        out["attestations_rejected"] = sum(r["attestations_rejected"] for r in text)
        out["resolver_error_pct"] = (100.0 * sum(r["attestations_wrong"] for r in text) / acc) if acc else float("nan")
        out["episodes_with_wrong_attestation_pct"] = 100.0 * sum(1 for r in text if r["attestations_wrong"]) / len(text)
    return out


def score(tasks: Dict[str, Task], predictions: Iterable[Dict[str, Any]],
          by: Optional[str] = None, missing: str = "abstain", strict: bool = False) -> Dict[str, Any]:
    """Score predictions against tasks. A task without a prediction counts as an
    abstention (``missing="abstain"``), raises (``missing="error"``), or is left out
    of the denominators (``missing="skip"``, the paper's treatment of episodes that
    failed to run, reported as ``n_missing``); a stated
    conclusion id the task does not define scores as false authorization, or raises
    with ``strict=True``. Returns ``{"overall": summary, "by_<group>": {...}, "rows": [...]}``."""
    preds: Dict[str, Dict[str, Any]] = {}
    for p in predictions:
        validate_prediction(p)
        if p["task_id"] in preds:
            raise PredictionError("duplicate prediction for task %s" % p["task_id"])
        preds[p["task_id"]] = p
    unknown = sorted(set(preds) - set(tasks))
    if unknown:
        raise PredictionError("predictions for unknown task ids, e.g. %s" % unknown[:3])
    rows = []
    n_missing = 0
    for tid, task in sorted(tasks.items()):
        p = preds.get(tid)
        if p is None:
            if missing == "error":
                raise PredictionError("no prediction for task %s" % tid)
            if missing == "skip":
                n_missing += 1
                continue
            p = {"task_id": tid, "stated": []}
        validate_prediction(p, task, strict=strict)
        actions = p.get("actions")
        if actions is None and p.get("reads") is not None:
            actions = [list(r) for r in p["reads"]]
        rows.append(score_task(task, list(p.get("stated") or []), actions))
    result: Dict[str, Any] = {"overall": summarize(rows), "rows": rows}
    result["overall"]["n_missing"] = n_missing
    if by in ("domain", "family", "topology"):
        groups = defaultdict(list)
        for r in rows:
            groups[r[by]].append(r)
        result["by_" + by] = {str(k): summarize(g) for k, g in sorted(groups.items(), key=lambda kv: str(kv[0]))}
    return result


def format_result(result: Dict[str, Any]) -> str:
    cols = [("n", "%d"), ("false_authorization_pct", "%.1f"), ("premature_pct", "%.1f"), ("utility", "%.1f"),
            ("evidence_value", "%.1f"), ("emission_rate_pct", "%.1f"), ("abstention_pct", "%.1f"),
            ("evidence_recall_pct", "%.1f"), ("mean_tool_calls", "%.2f"), ("mean_distinct_calls", "%.2f"),
            ("resolver_error_pct", "%.1f")]
    head = ["group"] + [c for c, _ in cols]
    lines = [head]
    groups = [("overall", result["overall"])]
    for key in ("by_domain", "by_family", "by_topology"):
        groups += sorted((result.get(key) or {}).items())
    for name, s in groups:
        lines.append([name] + [(fmt % s[c]) if c in s else "-" for c, fmt in cols])
    widths = [max(len(str(l[i])) for l in lines) for i in range(len(head))]
    return "\n".join("  ".join(str(v).rjust(w) for v, w in zip(l, widths)) for l in lines)


def paired_rows(result_a: Dict[str, Any], result_b: Dict[str, Any], key: str = "utility") -> List[Dict[str, Any]]:
    """Pair two scored results task by task for the family-level statistics in
    :mod:`obligationbench.stats` (rows with record, family, domain, topology, a, b)."""
    b = {r["task_id"]: r for r in result_b["rows"]}
    out = []
    for r in result_a["rows"]:
        if r["task_id"] in b:
            out.append({"record": r["record"], "family": r["family"], "domain": r["domain"],
                        "topology": r["topology"], "a": float(r[key]), "b": float(b[r["task_id"]][key])})
    return out
