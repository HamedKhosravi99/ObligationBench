#!/usr/bin/env python3
"""Example B: a minimal rule-following agent with no LLM, its prediction records, and
the evaluator.

The agent reads, in order, every check on the routes of the strongest conclusion
first, stops when it can no longer afford a read (budget of 20), and states the
strongest conclusion its own reads established. Because it only states what its
reads established, its false-authorization and premature rates are zero; its utility
is bounded by what 20 reads can establish. Compare it with an agent of your own by
writing the same prediction format."""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from obligationbench import RecordEnv, established, load_tasks, score  # noqa: E402
from obligationbench.scoring import format_result  # noqa: E402
from obligationbench.tasks import levels  # noqa: E402

BUDGET = 20


def run_agent(task):
    env = RecordEnv(task)
    lv = levels(task)
    # the agent sees the routes (supplied-standard setting); it visits the strongest conclusion's routes first
    for c in sorted(lv, key=lambda c: -lv[c]):
        for route in task["gold_licenses"][c]:
            for lit in route:
                if len(env.actions) >= BUDGET:
                    break
                atom = next(a for a in task["atoms"] if a["id"] == lit.lstrip("!"))
                r = atom.get("resolver")
                if not r or r["tool"] != "inspect_record" or atom["id"] in env.ledger:
                    continue
                env.inspect_record(r["params"]["record_id"], r["params"]["field_path"])
    est = established(task, env.ledger)
    stated = [max(est, key=lambda c: lv[c])] if est else []
    return {"task_id": task["id"], "stated": stated, "actions": env.actions, "agent": "route-reader"}


tasks = load_tasks(os.path.join(ROOT, "data", "val.jsonl"))
preds = [run_agent(t) for t in tasks.values()]
out = os.path.join(ROOT, "examples", "route_reader_val.jsonl")
with open(out, "w", encoding="utf-8") as fh:
    for p in preds:
        fh.write(json.dumps(p) + "\n")
print("wrote %d predictions to %s\n" % (len(preds), out))
result = score(tasks, preds, by="domain")
print(format_result(result))
print("\nsame thing from the command line:\n  obligationbench evaluate --tasks data/val.jsonl --predictions examples/route_reader_val.jsonl --by domain")
