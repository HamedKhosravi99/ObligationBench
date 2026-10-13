#!/usr/bin/env python3
"""Reproduce the paper's per-agent endpoints on the 480 balanced tasks from the
reference predictions with the released scorer, and compare with the paper.

    python scripts/reproduce_scores.py [--data data] [--model qwen2.5-32b]

The reference predictions (data/reference_predictions/<model>/<agent>.jsonl) were
rebuilt from the paper's episode logs using only the stated conclusions and the
recorded reads. For the nine agents of the paper's information ladder (Section 6.1) the expected values
are those the paper prints (Table 1 and Figure 3); the six further baselines are
reference values from the released logs, which the paper does not report. The
script exits nonzero on any difference above 0.05.

Denominators. Every agent ran on all 480 tasks. An episode whose model calls
still timed out after the client's retries carries no measurement, has no
reference prediction, and is left out of the rates (24 episodes over the 15
agents, at most 6 for one agent). data/reference_predictions/<model>/EXCLUDED.json
lists them with the rule; the script reports, per agent, the tasks, the excluded
episodes, and the scored ones, and fails if any other task lacks a prediction."""
from __future__ import annotations

import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "src"))

from suffice.scoring import score  # noqa: E402
from suffice.tasks import load_tasks  # noqa: E402

# agent file -> (name in the paper, expected false authorization %, premature %, utility, emission %, evidence value)
EXPECTED = {
    "react": ("ReAct", 13.0, 56.9, 17.9, 59.0, None),
    "react_verify": ("ReAct +verify", 19.9, 47.6, 10.0, 49.6, None),
    "react_spec": ("ReAct +spec", 21.9, 37.9, 28.3, 92.2, None),
    "react_spec_verify": ("ReAct +spec+verify", 22.3, 33.8, 26.9, 89.9, None),
    "react_program": ("ReAct +program", 22.9, 30.2, 31.9, 99.7, None),
    "react_program_verify": ("ReAct +program+verify", 22.3, 25.2, 32.7, 98.5, None),
    "react_program_attested": ("Fully informed agent, unenforced", 26.7, 28.3, 38.0, 99.0, 43.5),
    "masked_reactive_v": ("PRIME without guidance", 0.0, 0.0, 30.1, 99.0, 30.1),
    "prime_guided": ("PRIME", 0.0, 0.0, 45.5, 100.0, 45.5),
    "static_contract": ("Static checklist", 0.4, 0.4, 2.5, 9.6, 3.1),
    "conformal": ("Conformal (uncalibrated)", 13.3, 55.6, 17.5, 59.1, 2.4),
    "cove": ("CoVe", 10.1, 32.1, 11.3, 35.0, 2.7),
    "reflexion": ("Reflexion", 9.7, 38.2, 13.4, 41.5, 2.9),
    "rubric": ("Rubric", 24.6, 58.8, 17.6, 61.6, 1.4),
    "direct": ("Direct", 42.1, 92.9, 30.3, 92.9, 0.0),
}
KEYS = ("false_authorization_pct", "premature_pct", "utility", "emission_rate_pct", "evidence_value")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--data", default=os.path.join(ROOT, "data"))
    ap.add_argument("--model", default="qwen2.5-32b")
    ap.add_argument("--tolerance", type=float, default=0.05)
    a = ap.parse_args(argv)
    tasks = load_tasks(os.path.join(a.data, "balanced.jsonl"))
    pred_dir = os.path.join(a.data, "reference_predictions", a.model)
    excl_path = os.path.join(pred_dir, "EXCLUDED.json")
    excluded = {}
    if os.path.exists(excl_path):
        with open(excl_path, encoding="utf-8") as fh:
            excluded = json.load(fh)["excluded"]
    bad, n, n_excl = [], 0, 0
    print("%-34s %5s %5s %4s %6s %6s %6s %6s %6s" % ("agent", "tasks", "excl", "n", "FA%", "prem%", "util", "emit%", "evid"))
    for agent, (name, *exp) in EXPECTED.items():
        p = os.path.join(pred_dir, agent + ".jsonl")
        if not os.path.exists(p):
            print("%-34s missing %s" % (name, p))
            bad.append(agent)
            continue
        with open(p, encoding="utf-8") as fh:
            preds = [json.loads(l) for l in fh if l.strip()]
        # the declared exclusions, and nothing else, may lack a prediction
        without = set(tasks) - {q["task_id"] for q in preds}
        declared = set(excluded.get(agent, ()))
        if without != declared:
            bad.append("%s: tasks without a prediction %s, declared exclusions %s"
                       % (name, sorted(without)[:5], sorted(declared)[:5]))
        n_excl += len(declared)
        got = score(tasks, preds, missing="skip")["overall"]
        vals = [got.get(k) for k in KEYS]
        print("%-34s %5d %5d %4d %6.1f %6.1f %6.1f %6.1f %6s" % (name, len(tasks), got["n_missing"], got["n"], *vals[:4],
                                                              ("%.1f" % vals[4]) if vals[4] is not None else "-"))
        n += 1
        for k, g, x in zip(KEYS, vals, exp):
            if x is None or g is None:
                continue
            if abs(g - x) > a.tolerance:
                bad.append("%s %s: got %.2f, expected %.1f" % (name, k, g, x))
    if bad:
        print("DIFFERENCES:"); [print(" ", b) for b in bad]
        return 1
    print("all %d agents match their reference values; %d episodes excluded as declared in EXCLUDED.json, "
          "no other prediction missing" % (n, n_excl))
    return 0


if __name__ == "__main__":
    sys.exit(main())
