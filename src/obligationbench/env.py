"""The evidence actions an agent may take on a task, and the ledger they establish.

``RecordEnv`` wraps one task. It offers the three evidence actions of the benchmark
and records, as a *ledger*, which checks the agent's actions have settled:

``inspect_record(record_id, field_path)``
    returns the raw value stored at ``field_path`` of the record (or an error). A
    check whose resolver reads exactly this field is settled by evaluating the
    check's predicate on the value; the agent never sees the verdict, only the value.
    On the locator-uncertain tasks the check names candidate fields; a read of a
    candidate that is not the check's true field returns the value but settles
    nothing. A failed read settles nothing.

``read_text(record_id, field_path)``
    returns the full text of a free-text field (text-evidence tasks) and remembers
    that the text was read.

``attest_atom(atom_id, value, quote)``
    the agent's own judgment of a text-evidence check: accepted only when the
    check's source text was read in this episode and ``quote`` occurs in it
    verbatim (whitespace-normalized, case-insensitive, at least eight characters);
    the value is then recorded as the agent gave it, right or wrong.

Checks whose evidence is unavailable in the task (no resolver) can never be
settled. The acceptance rules are those of the PRIME runtime's tool executor
(``runner/arms.py``), ported here so that scoring needs no part of PRIME.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Tuple

from .predicates import evaluate_predicate, parse_predicate_rule
from .tasks import Task, resolve_field_path

MIN_QUOTE_CHARS = 8


class RecordEnv:
    def __init__(self, task: Task) -> None:
        self.task = task
        self.ledger: Dict[str, str] = {}          # atom id -> "T" | "F"
        self.reads: List[Tuple[str, str]] = []     # (record_id, field_path) of inspect_record
        self.texts_read: Dict[Tuple[str, str], str] = {}
        self.attestations: List[Dict[str, Any]] = []
        self.actions: List[Dict[str, Any]] = []

    # ------------------------------------------------------------ actions
    def inspect_record(self, record_id: str, field_path: str) -> Dict[str, Any]:
        record_id, field_path = str(record_id), str(field_path)
        self.reads.append((record_id, field_path))
        self.actions.append({"inspect_record": [record_id, field_path]})
        obs: Dict[str, Any] = {"record_id": record_id, "field_path": field_path}
        records = self.task.get("records") or {}
        if record_id not in records:
            obs["error"] = "record not found"
            return obs
        value, found = resolve_field_path(records[record_id], field_path)
        if not found:
            obs["error"] = "field not found"
            return obs
        obs["value"] = value
        params = {"record_id": record_id, "field_path": field_path}
        for atom in self.task.get("atoms", []):
            r = atom.get("resolver")
            if not r or r.get("tool") != "inspect_record":
                continue
            if r.get("params") and not all(params.get(k) == v for k, v in r["params"].items()):
                continue
            parsed = parse_predicate_rule(r.get("attest", ""))
            if parsed is None:
                continue
            result = evaluate_predicate(parsed[0], parsed[1], value)
            if result is not None:
                self.ledger[atom["id"]] = "T" if result else "F"
        return obs

    def read_text(self, record_id: str, field_path: str) -> Dict[str, Any]:
        record_id, field_path = str(record_id), str(field_path)
        self.actions.append({"read_text": [record_id, field_path]})
        records = self.task.get("records") or {}
        rec = records.get(record_id)
        if rec is None:
            return {"record_id": record_id, "field_path": field_path, "error": "unknown record"}
        value, ok = resolve_field_path(rec, field_path)
        if not ok or not isinstance(value, str):
            return {"record_id": record_id, "field_path": field_path, "error": "no text at this field"}
        self.texts_read[(record_id, field_path)] = value
        return {"record_id": record_id, "field_path": field_path, "text": value}

    def attest_atom(self, atom_id: str, value: str, quote: str) -> Dict[str, Any]:
        atom_id = str(atom_id)
        value = str(value).strip().upper()
        quote = " ".join(str(quote).split())
        self.actions.append({"attest_atom": [atom_id, value, quote]})
        atom = next((a for a in self.task.get("atoms", []) if a["id"] == atom_id), None)
        hint = (atom or {}).get("spec_hint") or {}
        src = hint.get("source") or {}
        r = (atom or {}).get("resolver")
        if atom is None or not r or r.get("tool") != "attest_atom":
            out = {"atom_id": atom_id, "accepted": False, "reason": "not a text-evidence atom"}
        elif value not in ("T", "F"):
            out = {"atom_id": atom_id, "accepted": False, "reason": "value must be T or F"}
        else:
            key = (str(src.get("record_id", "")), str(src.get("field_path", "")))
            text = self.texts_read.get(key)
            if text is None:
                out = {"atom_id": atom_id, "accepted": False,
                       "reason": "read the source text first (read_text %s %s)" % key}
            elif len(quote) < MIN_QUOTE_CHARS or quote.lower() not in " ".join(text.split()).lower():
                out = {"atom_id": atom_id, "accepted": False,
                       "reason": "the quote must occur verbatim in the source text"}
            else:
                out = {"atom_id": atom_id, "accepted": True, "value": value, "quote": quote}
                self.ledger[atom_id] = value
        self.attestations.append(dict(out))
        return out

    # ------------------------------------------------------------ replay
    def replay(self, actions: Sequence[Any]) -> None:
        """Execute a recorded action list in order. Each item is either a bare
        ``[record_id, field_path]`` pair (an ``inspect_record`` read, the legacy
        prediction format) or a one-key dict ``{"inspect_record": [rid, fp]}``,
        ``{"read_text": [rid, fp]}``, ``{"attest_atom": [atom_id, value, quote]}``."""
        for item in actions:
            if isinstance(item, dict):
                if len(item) != 1:
                    raise ValueError("an action is a one-key object, got %r" % (item,))
                (name, args), = item.items()
                if name == "inspect_record":
                    self.inspect_record(*args)
                elif name == "read_text":
                    self.read_text(*args)
                elif name == "attest_atom":
                    self.attest_atom(*args)
                else:
                    raise ValueError("unknown action %r" % name)
            else:
                rid, fp = item
                self.inspect_record(rid, fp)

    # ------------------------------------------------------------ views
    def agent_view(self) -> Dict[str, Any]:
        """What an agent given the rule may see: the request, the scope, the
        conclusions with their order, and each check's tool, parameters, and
        predicate (or, on locator-uncertain tasks, its description and candidate
        fields; on text-evidence tasks, its description and source text). Never a
        check's value."""
        t = self.task
        checks = []
        for a in t.get("atoms", []):
            r = a.get("resolver") or {}
            c: Dict[str, Any] = {"id": a["id"], "available": bool(r)}
            if r:
                c["tool"] = r.get("tool")
                hint = a.get("spec_hint") or {}
                if hint:
                    c["what"] = hint.get("what")
                    if hint.get("candidates"):
                        c["record_id"] = (r.get("params") or {}).get("record_id")
                        c["candidate_fields"] = list(hint["candidates"])
                    if hint.get("source"):
                        c["source"] = dict(hint["source"])
                else:
                    c.update({k: v for k, v in (r.get("params") or {}).items()})
                    c["predicate"] = r.get("attest")
            checks.append(c)
        return {
            "task_id": t["id"], "request": t.get("user_prompt"), "scope": t.get("scope"),
            "conclusions": [{"id": c["id"], "level": int(c["level"]), "text": c["text"]} for c in t["claims"]],
            "order": [list(p) for p in t.get("order", [])],
            "checks": checks,
            "routes": {c: [list(r) for r in rs] for c, rs in t["gold_licenses"].items()},
            "actions": list(t.get("actions", [])),
        }
