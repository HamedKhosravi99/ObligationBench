#!/usr/bin/env python3
"""Example C: walk through one text-evidence task: read the source text, attest a
check with a quote, and see what the ledger records, including a wrong attestation
being accepted (the resolver-error term)."""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from obligationbench import RecordEnv, load_tasks, score_task, supported  # noqa: E402

tasks = load_tasks(os.path.join(ROOT, "data", "text.jsonl"))
task = next(t for t in tasks.values() if t["domain"].startswith("clinical"))
env = RecordEnv(task)
print("task", task["id"], "-", task["user_prompt"])
for a in task["atoms"]:
    hint = a.get("spec_hint") or {}
    print("  check %s: %s" % (a["id"], hint.get("what") or (a["resolver"] or {}).get("params")))
src = next(a for a in task["atoms"] if (a.get("resolver") or {}).get("tool") == "attest_atom")["spec_hint"]["source"]
text = env.read_text(src["record_id"], src["field_path"])["text"]
print("\nsource text (%d chars): %s..." % (len(text), text[:160].replace("\n", " ")))

quote = " ".join(text.split()[:6])
print("\nattest E2 = T with the quote %r" % quote)
print(" ->", env.attest_atom("E2", "T", quote))
print("attest E2 = T with a quote not in the text ->", env.attest_atom("E2", "T", "this sentence is not there"))
print("ledger:", env.ledger)
print("reference values (evaluator-only):", {a["id"]: a["gold_value"] for a in task["atoms"]},
      "| supported:", sorted(c for c, ok in supported(task).items() if ok))
row = score_task(task, ["C2"], env.actions)
print("\nscore if the agent now states C2:", json.dumps({k: row[k] for k in ("false_authorization", "premature", "utility", "attestations_accepted", "attestations_wrong")}))
