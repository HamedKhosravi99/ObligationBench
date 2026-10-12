"""The benchmark's evidence handling agrees with the PRIME runtime.

``env.py`` and ``scoring.py`` re-implement what the PRIME runtime does with an
agent's evidence actions, so that scoring needs no part of PRIME. The fixture
``fixtures/prime_conformance.json.gz`` holds outcomes the runtime itself produced
(``bench/conformance.py`` in the PRIME code: its tool executor, gold-ledger
resolvers, four-valued ledger, and authorization check). Each test recomputes the
same outcomes here and compares:

* structured-field reads: the observation and the checks a read settles, for
  every resolver field, locator candidate, a missing field, and an unknown record
  of all 1,658 record tasks;
* authorization: the conclusions established by the reference state and 12 seeded
  check-value states of every task (weaker conclusions included);
* text attestations: acceptance and the check's state through a fixed sequence
  (before reading, a short quote, a quote not in the text, a bad value, another
  check, the verbatim quote, a repeat, a contradiction, which leaves the check
  conflicted) for every text-evidence check;
* logged episodes: for every completed episode of the 15 reference agents, the
  checks its reads settle, the conclusions they establish, and the distinct call
  classes (what PRIME's budget charges), replayed from the reference predictions.
"""
import gzip
import hashlib
import json
import os

import pytest

from obligationbench.env import RecordEnv
from obligationbench.scoring import established

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIXTURE = os.path.join(ROOT, "tests", "fixtures", "prime_conformance.json.gz")
PRED = os.path.join(ROOT, "data", "reference_predictions", "qwen2.5-32b")


@pytest.fixture(scope="module")
def fx():
    if not os.path.exists(FIXTURE):
        pytest.skip("no conformance fixture")
    with gzip.open(FIXTURE, "rt", encoding="utf-8") as fh:
        return json.load(fh)


@pytest.fixture(scope="module")
def all_tasks(tasks):
    out = {}
    for ts in tasks.values():
        out.update(ts)
    return out


def _digest(obs):
    if obs.get("error") is not None:
        return ["error", str(obs["error"])]
    return ["value", hashlib.sha1(json.dumps(obs.get("value"), sort_keys=True, default=str).encode("utf-8")).hexdigest()]


def _state(env, atom_id):
    return "C" if atom_id in env.conflicts else env.ledger.get(atom_id, "U")


def test_reads_agree(fx, all_tasks):
    n = 0
    for tid, rows in fx["reads"].items():
        task = all_tasks[tid]
        for rid, fp, dig, settled in rows:
            env = RecordEnv(task)
            obs = env.inspect_record(rid, fp)
            assert _digest(obs) == dig, (tid, rid, fp)
            assert env.ledger == settled, (tid, rid, fp, env.ledger, settled)
            n += 1
    assert len(fx["reads"]) == 1658 and n > 10000


def test_authorization_agrees(fx, all_tasks):
    for tid, rows in fx["auth"].items():
        task = all_tasks[tid]
        for state, auth in rows:
            assert sorted(established(task, state)) == auth, (tid, state)
    assert len(fx["auth"]) == 1898


def test_text_attestations_agree(fx, all_tasks):
    for tid, checks in fx["attest"].items():
        task = all_tasks[tid]
        for atom_id, steps in checks:
            env = RecordEnv(task)
            for name, args, accepted, state in steps:
                out = getattr(env, name)(*args)
                if name == "attest_atom":
                    assert out["accepted"] is accepted, (tid, atom_id, args)
                assert _state(env, atom_id) == state, (tid, atom_id, name, args)
    assert len(fx["attest"]) == 240


def test_logged_episodes_agree(fx, all_tasks):
    if not fx["episodes"]:
        pytest.skip("fixture built without episode logs")
    if not os.path.isdir(PRED):
        pytest.skip("no reference predictions")
    n = 0
    for agent, rows in fx["episodes"].items():
        with open(os.path.join(PRED, agent + ".jsonl"), encoding="utf-8") as fh:
            preds = {p["task_id"]: p for p in map(json.loads, fh)}
        assert set(preds) == set(rows), agent
        for tid, (settled, auth, charged, logged) in rows.items():
            assert settled == logged, (agent, tid)          # the runtime's replay matches the log
            env = RecordEnv(all_tasks[tid])
            env.replay(preds[tid]["reads"])
            assert env.ledger == settled, (agent, tid)
            assert sorted(established(all_tasks[tid], env.ledger)) == auth, (agent, tid)
            assert env.calls == charged, (agent, tid, env.calls, charged)
            n += 1
    assert n == 7176
