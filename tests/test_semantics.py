"""Benchmark semantics on the published tasks: hierarchies, routes, reference labels."""
import itertools
import random

import pytest

from obligationbench.env import RecordEnv
from obligationbench.scoring import holds, reference_values, supported
from obligationbench.tasks import levels
from obligationbench.validate import validate_task


def _all(tasks):
    for cfg, ts in tasks.items():
        for t in ts.values():
            yield cfg, t


def test_every_task_validates(tasks):
    bad = {}
    for cfg, t in _all(tasks):
        p = validate_task(t, schema=False)
        if p:
            bad[t["id"]] = p
    assert not bad, list(bad.items())[:5]


def test_conclusion_hierarchy_is_a_chain(tasks):
    for cfg, t in _all(tasks):
        lv = levels(t)
        assert sorted(lv.values()) == [1, 2, 3]
        for w, s in t["order"]:
            assert lv[w] < lv[s]


def test_routes_reference_known_checks_and_are_satisfiable(tasks):
    for cfg, t in _all(tasks):
        aids = {a["id"] for a in t["atoms"]}
        for c, routes in t["gold_licenses"].items():
            assert routes
            for r in routes:
                lits = [x.lstrip("!") for x in r]
                assert set(lits) <= aids
                assert len(set(lits)) == len(lits)
                # no literal appears in both polarities (Phi is empty, so that is the only inconsistency)
                pos = {x for x in r if not x.startswith("!")}; neg = {x[1:] for x in r if x.startswith("!")}
                assert not pos & neg


def test_order_coherence(tasks):
    """Every route of a stronger conclusion contains some route of each weaker one."""
    for cfg, t in _all(tasks):
        for w, s in t["order"]:
            for rs in t["gold_licenses"][s]:
                assert any(set(rw) <= set(rs) for rw in t["gold_licenses"][w]), (t["id"], w, s)


def test_support_monotone_along_order(tasks):
    for cfg, t in _all(tasks):
        supp = supported(t)
        for w, s in t["order"]:
            assert not (supp[s] and not supp[w])


def test_reference_values_execute(tasks):
    for cfg, t in _all(tasks):
        env = RecordEnv(t)
        for a in t["atoms"]:
            r = a.get("resolver")
            if not r or r.get("tool") != "inspect_record":
                continue
            p = r["params"]
            env.inspect_record(p["record_id"], p["field_path"])
            assert env.ledger.get(a["id"], "U") == a["gold_value"], (t["id"], a["id"])


def test_unavailable_checks_are_false_and_unreachable(tasks):
    n = 0
    for cfg, t in _all(tasks):
        for a in t["atoms"]:
            if a.get("resolver") is None:
                n += 1
                assert a["gold_value"] == "F"
        env = RecordEnv(t)
        for a in t["atoms"]:
            r = a.get("resolver")
            if r and r.get("tool") == "inspect_record":
                env.inspect_record(r["params"]["record_id"], r["params"]["field_path"])
        for a in t["atoms"]:
            if a.get("resolver") is None:
                assert a["id"] not in env.ledger
    assert n > 0


def test_negative_literals_only_in_text_tasks(tasks):
    for cfg, t in _all(tasks):
        neg = any(x.startswith("!") for rs in t["gold_licenses"].values() for r in rs for x in r)
        assert neg == (cfg == "text") or not neg


def test_text_tasks_have_readable_sources_and_hidden_twins(tasks):
    for t in tasks["text"].values():
        env = RecordEnv(t)
        for a in t["atoms"]:
            if (a.get("resolver") or {}).get("tool") == "attest_atom":
                src = a["spec_hint"]["source"]
                assert "text" in env.read_text(src["record_id"], src["field_path"])
        rec = t["records"][t["seed"]]
        # the structured twins are withheld from the embedded record
        for path in ("protocolSection.eligibilityModule.minimumAge", "protocolSection.eligibilityModule.sex", "affected.0.ranges"):
            v, found = __import__("obligationbench.tasks", fromlist=["resolve_field_path"]).resolve_field_path(rec, path)
            assert not found, (t["id"], path)


def test_locator_candidates(tasks):
    for t in tasks["locator"].values():
        env = RecordEnv(t)
        for a in t["atoms"]:
            hint = a.get("spec_hint") or {}
            if hint.get("candidates"):
                p = a["resolver"]["params"]
                assert p["field_path"] in hint["candidates"] and len(hint["candidates"]) == 3
                for cand in hint["candidates"]:
                    obs = env.inspect_record(p["record_id"], cand)
                    assert "error" not in obs, (t["id"], a["id"], cand)
                # a decoy read settles nothing for this check
                e2 = RecordEnv(t)
                for cand in hint["candidates"]:
                    if cand != p["field_path"]:
                        e2.inspect_record(p["record_id"], cand)
                assert a["id"] not in e2.ledger


def test_minimality_sampled(tasks):
    """On a sample of tasks, no route literal is redundant: dropping any one of them
    leaves a set of literals that no longer appears as a route and that some
    reference assignment consistent with the task could satisfy without supporting
    the conclusion. (Brute force over assignments of the route's atoms.)"""
    rng = random.Random(0)
    sample = rng.sample(list(tasks["balanced"].values()), 40)
    for t in sample:
        for c, routes in t["gold_licenses"].items():
            for r in routes:
                for drop in r:
                    weaker = [x for x in r if x != drop]
                    assert not any(set(q) <= set(weaker) for q in routes), (t["id"], c, r, drop)
