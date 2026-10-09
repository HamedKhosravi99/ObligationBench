import json
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from obligationbench.tasks import load_tasks  # noqa: E402

DATA = os.environ.get("OBLIGATIONBENCH_DATA", os.path.join(ROOT, "data"))
CONFIGS = ("balanced", "natural", "dev", "val", "locator", "onebranch", "text", "fdaaa")


def data_file(config: str) -> str:
    return os.path.join(DATA, "%s.jsonl" % config)


@pytest.fixture(scope="session")
def data_dir() -> str:
    if not os.path.exists(data_file("balanced")):
        pytest.skip("dataset files not built (run scripts/prepare_hf_dataset.py)")
    return DATA


@pytest.fixture(scope="session")
def rows(data_dir):
    out = {}
    for c in CONFIGS:
        p = data_file(c)
        if os.path.exists(p):
            with open(p, encoding="utf-8") as fh:
                out[c] = [json.loads(l) for l in fh if l.strip()]
    return out


@pytest.fixture(scope="session")
def tasks(data_dir):
    return {c: load_tasks(data_file(c)) for c in CONFIGS if os.path.exists(data_file(c))}


@pytest.fixture(scope="session")
def manifest(data_dir):
    with open(os.path.join(os.path.dirname(data_dir), "manifest.json") if os.path.exists(os.path.join(os.path.dirname(data_dir), "manifest.json")) else os.path.join(data_dir, "manifest.json"), encoding="utf-8") as fh:
        return json.load(fh)


@pytest.fixture
def toy_task():
    """A small hand-written task: three conclusions in a chain, four checks, a
    branching route to C2, one check with unavailable evidence (E5), and a
    text-evidence check (E6) whose reference value is T."""
    return {
        "id": "toy-0001", "domain": "security_v2", "seed": "REC-1", "variant": "base",
        "user_prompt": "Is the record ready?", "artifact": {"path": "", "kind": "record", "commit": ""},
        "scope": "The record REC-1.", "actions": ["inspect_record", "read_text", "attest_atom", "emit_claim"],
        "claims": [{"id": "C1", "level": 1, "text": "identified", "denotation": []},
                   {"id": "C2", "level": 2, "text": "ready", "denotation": []},
                   {"id": "C3", "level": 3, "text": "complete", "denotation": []}],
        "order": [["C1", "C2"], ["C2", "C3"]],
        "atoms": [
            {"id": "E1", "type": "record", "proposition": "", "gold_value": "T",
             "resolver": {"tool": "inspect_record", "params_schema": {"field_path": "str", "record_id": "str"},
                          "params": {"field_path": "title", "record_id": "REC-1"}, "attest": "record_predicate:exists:null"}},
            {"id": "E2", "type": "record", "proposition": "", "gold_value": "F",
             "resolver": {"tool": "inspect_record", "params_schema": {"field_path": "str", "record_id": "str"},
                          "params": {"field_path": "severity", "record_id": "REC-1"}, "attest": "record_predicate:equals:\"HIGH\""}},
            {"id": "E3", "type": "record", "proposition": "", "gold_value": "T",
             "resolver": {"tool": "inspect_record", "params_schema": {"field_path": "str", "record_id": "str"},
                          "params": {"field_path": "published", "record_id": "REC-1"}, "attest": "record_predicate:exists:null"}},
            {"id": "E4", "type": "record", "proposition": "", "gold_value": "T",
             "resolver": {"tool": "inspect_record", "params_schema": {"field_path": "str", "record_id": "str"},
                          "params": {"field_path": "references.0.url", "record_id": "REC-1"}, "attest": "record_predicate:exists:null"}},
            {"id": "E5", "type": "record", "proposition": "", "gold_value": "F", "resolver": None},
            {"id": "E6", "type": "text", "proposition": "", "gold_value": "T",
             "resolver": {"tool": "attest_atom", "params_schema": {"atom_id": "str", "value": "str", "quote": "str"},
                          "params": {"atom_id": "E6"}, "attest": "attested"},
             "spec_hint": {"what": "the details name a fixed version", "source": {"record_id": "REC-1", "field_path": "details"}}},
        ],
        "phi": [],
        "gold_licenses": {"C1": [["E1"]], "C2": [["E1", "E2"], ["E1", "E3", "E4"]], "C3": [["E1", "E3", "E4", "E5"], ["E1", "E3", "E4", "E6"]]},
        "decoys": [],
        "records": {"REC-1": {"title": "A record", "severity": "LOW", "published": "2024-01-01",
                              "references": [{"url": "https://example.org/x"}],
                              "details": "This issue was fixed in version 2.3.1 of the package."}},
        "notes_for_annotators": json.dumps({"family": "toy-branching-hom-00", "topology": "branching"}),
    }
