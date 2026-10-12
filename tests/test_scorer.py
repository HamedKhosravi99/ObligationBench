"""The scorer on a hand-written task: every endpoint, every edge case."""
import pytest

from obligationbench.env import RecordEnv
from obligationbench.scoring import (PredictionError, established, holds, score, score_task,
                                     supported, summarize, validate_prediction)


def test_reference_support(toy_task):
    s = supported(toy_task)
    assert s == {"C1": True, "C2": True, "C3": True}   # C2 via E1,E3,E4; C3 via E1,E3,E4,E6


def test_fully_supported_statement(toy_task):
    row = score_task(toy_task, ["C2"], [["REC-1", "title"], ["REC-1", "published"], ["REC-1", "references.0.url"]])
    assert row["false_authorization"] == 0 and row["premature"] == 0
    assert row["utility"] == pytest.approx(200 / 3)
    assert row["evidence_value"] == pytest.approx(200 / 3)


def test_unsupported_statement_is_false_authorization(toy_task):
    toy_task["atoms"][2]["gold_value"] = "F"   # E3 false: C2 only via E1,E2 which is false -> C2 unsupported
    row = score_task(toy_task, ["C2"], [])
    assert row["false_authorization"] == 1 and row["utility"] == 0


def test_premature_without_evidence(toy_task):
    row = score_task(toy_task, ["C2"], [["REC-1", "title"]])
    assert row["false_authorization"] == 0        # supported by the record
    assert row["premature"] == 1                   # but not established by the reads
    assert row["evidence_value"] == pytest.approx(100 / 3)


def test_partial_evidence_and_alternative_route(toy_task):
    # the E2 route to C2 fails on the record (severity LOW), the E3,E4 route holds
    env = RecordEnv(toy_task)
    env.inspect_record("REC-1", "title"); env.inspect_record("REC-1", "severity")
    assert env.ledger == {"E1": "T", "E2": "F"}
    assert established(toy_task, env.ledger) == {"C1"}
    env.inspect_record("REC-1", "published"); env.inspect_record("REC-1", "references.0.url")
    assert established(toy_task, env.ledger) == {"C1", "C2"}


def test_abstention_scores_zero_without_false_authorization(toy_task):
    row = score_task(toy_task, [], [])
    assert row == {**row, "false_authorization": 0, "utility": 0.0, "stated": 0, "premature": 0}


def test_unavailable_evidence_never_establishes(toy_task):
    env = RecordEnv(toy_task)
    for fp in ("title", "severity", "published", "references.0.url"):
        env.inspect_record("REC-1", fp)
    assert "E5" not in env.ledger
    assert "C3" not in established(toy_task, env.ledger)      # E5 route dead, E6 route needs an attestation


def test_failed_read_establishes_nothing(toy_task):
    env = RecordEnv(toy_task)
    assert "error" in env.inspect_record("REC-1", "no.such.field")
    assert "error" in env.inspect_record("REC-9", "title")
    assert env.ledger == {}


def test_negative_literals():
    assert holds(["E1", "!E2"], {"E1": "T", "E2": "F"})
    assert not holds(["E1", "!E2"], {"E1": "T", "E2": "T"})
    assert not holds(["E1", "!E2"], {"E1": "T"})         # unsettled satisfies neither polarity


def test_attestation_rules(toy_task):
    env = RecordEnv(toy_task)
    r = env.attest_atom("E6", "T", "fixed in version 2.3.1")
    assert not r["accepted"] and "read the source text" in r["reason"]
    env.read_text("REC-1", "details")
    assert not env.attest_atom("E6", "T", "short")["accepted"]                 # under 8 characters
    assert not env.attest_atom("E6", "T", "not in the text at all")["accepted"]
    assert not env.attest_atom("E6", "maybe", "fixed in version 2.3.1")["accepted"]
    assert not env.attest_atom("E1", "T", "fixed in version 2.3.1")["accepted"]  # not a text check
    ok = env.attest_atom("E6", "F", "FIXED IN   version 2.3.1")               # case and whitespace normalized
    assert ok["accepted"] and env.ledger["E6"] == "F"                           # recorded as given, even if wrong


def test_wrong_attestation_is_resolver_error_and_can_authorize(toy_task):
    toy_task["atoms"][5]["gold_value"] = "F"   # the text does not establish E6
    actions = [{"inspect_record": ["REC-1", "title"]}, {"inspect_record": ["REC-1", "published"]},
               {"inspect_record": ["REC-1", "references.0.url"]}, {"read_text": ["REC-1", "details"]},
               {"attest_atom": ["E6", "T", "fixed in version 2.3.1"]}]
    row = score_task(toy_task, ["C3"], actions)
    assert row["attestations_accepted"] == 1 and row["attestations_wrong"] == 1
    assert row["premature"] == 0            # the agent's own (wrong) ledger established C3
    assert row["false_authorization"] == 1  # the record does not support it


def test_invalid_predictions(toy_task):
    with pytest.raises(PredictionError):
        validate_prediction({"stated": ["C1"]})
    with pytest.raises(PredictionError):
        validate_prediction({"task_id": "toy-0001", "stated": "C1"})
    with pytest.raises(PredictionError):
        validate_prediction({"task_id": "toy-0001", "stated": ["C9"]}, toy_task, strict=True)
    # a conclusion id the task does not define is an unsupported statement, not an error
    r = score({"toy-0001": toy_task}, [{"task_id": "toy-0001", "stated": ["C9"]}])
    assert r["rows"][0]["false_authorization"] == 1 and r["rows"][0]["invalid_conclusion_ids"] == ["C9"]
    with pytest.raises(PredictionError):
        score({"toy-0001": toy_task}, [{"task_id": "toy-0001", "stated": ["C9"]}], strict=True)
    with pytest.raises(PredictionError):
        score({"toy-0001": toy_task}, [{"task_id": "toy-0001", "stated": []}, {"task_id": "toy-0001", "stated": []}])
    with pytest.raises(PredictionError):
        score({"toy-0001": toy_task}, [{"task_id": "nope", "stated": []}])


def test_missing_prediction_policy(toy_task):
    r = score({"toy-0001": toy_task}, [])
    assert r["overall"]["n"] == 1 and r["overall"]["abstention_pct"] == 100.0
    with pytest.raises(PredictionError):
        score({"toy-0001": toy_task}, [], missing="error")


def test_summary_endpoints(toy_task):
    rows = [score_task(toy_task, ["C1"], [["REC-1", "title"]]), score_task(toy_task, [], None)]
    s = summarize(rows)
    assert s["n"] == 2 and s["emission_rate_pct"] == 50.0 and s["abstention_pct"] == 50.0
    assert s["utility"] == pytest.approx((100 / 3) / 2)
    assert s["premature_pct"] == 0.0 and s["evidence_recall_pct"] > 0


def test_legacy_reads_and_actions_agree(toy_task):
    reads = [["REC-1", "title"], ["REC-1", "published"], ["REC-1", "references.0.url"]]
    a = score_task(toy_task, ["C2"], reads)
    b = score_task(toy_task, ["C2"], [{"inspect_record": r} for r in reads])
    assert {k: v for k, v in a.items()} == {k: v for k, v in b.items()}


def test_conflicting_attestations_settle_nothing(toy_task):
    """As in PRIME's four-valued ledger: T then F leaves the check conflicted and
    unsettled; a repeated identical value changes nothing."""
    env = RecordEnv(toy_task)
    env.read_text("REC-1", "details")
    assert env.attest_atom("E6", "T", "fixed in version 2.3.1")["accepted"]
    assert env.attest_atom("E6", "T", "fixed in version 2.3.1")["accepted"]
    assert env.ledger["E6"] == "T" and not env.conflicts
    assert env.attest_atom("E6", "F", "fixed in version 2.3.1")["accepted"]
    assert "E6" not in env.ledger and env.conflicts == {"E6"}
    env.attest_atom("E6", "T", "fixed in version 2.3.1")
    assert "E6" not in env.ledger                       # stays conflicted


def test_distinct_calls_count_call_classes(toy_task):
    actions = [{"inspect_record": ["REC-1", "title"]}, {"inspect_record": ["REC-1", "title"]},
               {"inspect_record": ["REC-1", "published"]}]
    row = score_task(toy_task, ["C1"], actions)
    assert row["tool_calls"] == 3 and row["distinct_calls"] == 2


def test_attestation_classes_depend_on_the_source_being_read(toy_task):
    """As in PRIME's executor: an attestation made before the source text was read
    and the same one made after it are two call classes; a later repeat is not."""
    env = RecordEnv(toy_task)
    assert not env.attest_atom("E6", "T", "fixed in version 2.3.1")["accepted"]
    env.read_text("REC-1", "details")
    assert env.attest_atom("E6", "T", "fixed in version 2.3.1")["accepted"]
    env.attest_atom("E6", "T", "fixed in version 2.3.1")
    assert env.calls == 3 and len(env.actions) == 4
