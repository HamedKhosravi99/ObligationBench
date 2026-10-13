#!/usr/bin/env python3
"""Example A: load a configuration and inspect a task, separating what an agent may
see from the evaluator-only labels.

Works from the local data files (no network). With the `datasets` library
installed, the same rows load from the Hugging Face hub once the dataset is
published: load_dataset("<namespace>/SUFFICE", "balanced", split="test")."""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from suffice import RecordEnv, agent_visible, load_tasks  # noqa: E402
from suffice.tasks import iter_rows  # noqa: E402

path = os.path.join(ROOT, "data", "balanced.jsonl")
rows = list(iter_rows(path))
print("configuration balanced: %d rows" % len(rows))
row = next(r for r in rows if r["task_id"] == "sec-v2-0114")

print("\n# agent-visible fields")
for k, v in agent_visible(row).items():
    if k in ("specification_view", "evidence_atoms", "sufficient_routes", "conclusions"):
        continue
    print("  %-28s %s" % (k, json.dumps(v)[:90]))
print("  conclusions:")
for c in row["conclusions"]:
    print("    %s (level %d): %s" % (c["id"], c["level"], c["text"][:80]))
print("  checks:")
for a in row["evidence_atoms"]:
    where = a["field_path"] or ("candidates %s" % a["candidate_fields"]) or ("text %s" % a["text_source"])
    print("    %s available=%s %s %s" % (a["id"], a["available"], where, a["predicate"] or a["description"] or ""))
print("  routes:")
for r in row["sufficient_routes"]:
    print("    %s <- %s" % (r["conclusion"], " & ".join(r["literals"])))

print("\n# evaluator-only labels (never show these to an agent)")
print("  reference values:", {x["id"]: x["value"] for x in row["reference_atom_values"]})
print("  supported conclusions:", row["reference_supported_conclusions"], "| strongest level:", row["strongest_supported_level"])

print("\n# the same through the environment, from the native task")
tasks = load_tasks(path)
env = RecordEnv(tasks["sec-v2-0114"])
print("  agent_view keys:", sorted(env.agent_view()))
print("  inspect_record(details) ->", json.dumps(env.inspect_record("GHSA-5pqf-rvm7-3wgw", "details"))[:100])
print("  ledger after that read:", env.ledger)
