# SUFFICE

A benchmark of evidence-based review tasks for LLM agents, with a deterministic scorer and the generator that built it. It accompanies the paper *PRIME: Towards Verifiable Evidence-Grounded Reasoning in LLM Agents* (under review) and is usable without PRIME.

Each task gives an agent one real public record (a vulnerability advisory, a trial registration, a drug recall, or a company's financial facts), a request, three conclusions of increasing strength, and the checks each conclusion requires. The agent reads fields of the record through tools and states the strongest conclusion it can justify. Which checks suffice is fixed before any record is read, and every check's true value is computed from the record, so scoring runs code: no model or person judges an answer.

| | |
|---|---|
| Primary corpus | 938 tasks: balanced 480, natural 218, dev 192, val 48; 120 template families; four domains |
| Derived variants | locator 480 (fields withheld, three candidates), onebranch 240, text 240 (free-text evidence judged by the agent) |
| External standard | fdaaa 319 (42 CFR Part 11, program written by an LLM coding assistant, on ClinicalTrials.gov registrations) |
| Scoring | false authorization, premature conclusions, supported utility, evidence value, emission, evidence recall, tool calls, resolver error |
| Needs | Python 3.9+, standard library only; `datasets` optional for Hugging Face loading |

## Install

```bash
pip install -e .            # the package and the suffice command
pip install -e .[dev]       # plus pytest, datasets, huggingface_hub
```

## Use

```python
from suffice import load_tasks, RecordEnv, score

tasks = load_tasks("data/balanced.jsonl")          # {task_id: task}
task = tasks["sec-v2-0114"]
env = RecordEnv(task)
view = env.agent_view()                            # request, conclusions, checks, routes; no check values
env.inspect_record("GHSA-5pqf-rvm7-3wgw", "details")
env.ledger                                         # {"E1": "T"}: what the reads settled

predictions = [{"task_id": "sec-v2-0114", "stated": ["C1"], "actions": env.actions}]
print(score(tasks, predictions)["overall"])
```

```bash
suffice evaluate --tasks data/balanced.jsonl --predictions predictions.jsonl --by domain --output results.json
suffice validate --split heldout_balanced=data/balanced.jsonl --split heldout_natural=data/natural.jsonl
suffice inspect --tasks data/balanced.jsonl sec-v2-0114 --labels
suffice generate records -- --help
```

Prediction format and endpoint definitions: [docs/evaluation_protocol.md](docs/evaluation_protocol.md). Row schema: [docs/data_schema.md](docs/data_schema.md). Examples in [examples/](examples/): load and inspect a task, evaluate a baseline agent, regenerate tasks.

## Layout

| Path | Contents |
|---|---|
| `src/suffice/` | `tasks.py` (loading), `env.py` (the evidence actions and the ledger), `scoring.py` (endpoints), `stats.py` (family-level statistics), `export.py` (native task <-> dataset row), `validate.py` (integrity checks), `cli.py`; `predicates.py`, `instance_schema.py`, `closure.py` (original PRIME modules, vendored); `generation/` (the generators, vendored) |
| `data/` | the dataset files (`balanced.jsonl`, `natural.jsonl`, `dev.jsonl`, `val.jsonl`, `locator.jsonl`, `onebranch.jsonl`, `text.jsonl`, `fdaaa.jsonl`), `manifest.json` with every task's SHA-256, `reference_predictions/`, `LICENSE` (CC BY 4.0), `NOTICE.md` (source terms) |
| `inputs/` | the harvest of 2026-08-01 that the generators read, reduced to the fields they use (`harvest/`, 10 MB, with SHA-256 sums of the full and reduced files), and the generator's manifest of families and splits |
| `configs/` | `corpus.yaml` (the generator's settings, for reference), `evaluation.yaml` (the scoring definitions) |
| `scripts/` | `prepare_hf_dataset.py`, `validate_corpus.py`, `reproduce_corpus.py`, `reduce_harvest.py`, `reproduce_scores.py`, `check_anonymity.py`, `publish_hf_private.py`, `prepare_anonymous_package.sh` |
| `tests/` | dataset integrity, benchmark semantics, scorer, reproducibility (the corpus regenerates; the reference scores reproduce), conformance with the PRIME runtime (`fixtures/prime_conformance.json.gz`), publication hygiene |
| `docs/` | methodology, data schema, benchmark generation, evaluation protocol, reproducibility, limitations, provenance and licensing, anonymous package, release checklist, the Hugging Face dataset card |

## Reproducibility

Two kinds, both checked by the tests and by the continuous-integration workflow:

* **Scoring reproducibility.** `python scripts/validate_corpus.py` checks every task's structure, hash, and reference labels. `python scripts/reproduce_scores.py` scores the paper's reference predictions and compares them with the paper. It also accounts for every episode: 24 episodes, whose model calls timed out, are declared exclusions, and nothing else may be missing.
* **Generator reproducibility.** `python scripts/reproduce_corpus.py` regenerates all 1,898 tasks of the primary corpus and of the one-branch, locator, and text variants from `inputs/harvest/`, and compares each with the published file byte for byte. The FDAAA set is built by the PRIME code from a third-party table.

[docs/reproducibility.md](docs/reproducibility.md) has the details, and [docs/benchmark_generation.md](docs/benchmark_generation.md) what the generator does and why earlier versions did not reproduce the corpus.

## Licenses and provenance

Code: MIT. Data: CC BY 4.0, with the embedded records under their sources' terms (`data/NOTICE.md`). Details and open questions: [docs/provenance_and_licensing.md](docs/provenance_and_licensing.md).

## Status

Under double-anonymous review. Author names, the citation, and links are withheld and will be filled in at publication (see `CITATION.cff` and [docs/release_checklist.md](docs/release_checklist.md)).
