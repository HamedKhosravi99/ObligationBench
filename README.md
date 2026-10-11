# ObligationBench

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
pip install -e .            # the package and the obligationbench command
pip install -e .[dev]       # plus pytest, datasets, huggingface_hub
```

## Use

```python
from obligationbench import load_tasks, RecordEnv, score

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
obligationbench evaluate --tasks data/balanced.jsonl --predictions predictions.jsonl --by domain --output results.json
obligationbench validate --split heldout_balanced=data/balanced.jsonl --split heldout_natural=data/natural.jsonl
obligationbench inspect --tasks data/balanced.jsonl sec-v2-0114 --labels
obligationbench generate records -- --help
```

Prediction format and endpoint definitions: [docs/evaluation_protocol.md](docs/evaluation_protocol.md). Row schema: [docs/data_schema.md](docs/data_schema.md). Examples in [examples/](examples/): load and inspect a task, evaluate a baseline agent, regenerate tasks.

## Layout

| Path | Contents |
|---|---|
| `src/obligationbench/` | `tasks.py` (loading), `env.py` (the evidence actions and the ledger), `scoring.py` (endpoints), `stats.py` (family-level statistics), `export.py` (native task <-> dataset row), `validate.py` (integrity checks), `cli.py`; `predicates.py`, `instance_schema.py`, `closure.py` (original PRIME modules, vendored); `generation/` (the generators, vendored) |
| `data/` | the dataset files (`balanced.jsonl`, `natural.jsonl`, `dev.jsonl`, `val.jsonl`, `locator.jsonl`, `onebranch.jsonl`, `text.jsonl`, `fdaaa.jsonl`), `manifest.json` with every task's SHA-256, `reference_predictions/`, `LICENSE` (CC BY 4.0), `NOTICE.md` (source terms) |
| `configs/` | `corpus.yaml` (the generator's settings, for reference), `evaluation.yaml` (the scoring definitions) |
| `scripts/` | `prepare_hf_dataset.py`, `validate_corpus.py`, `reproduce_corpus.py`, `reproduce_scores.py`, `check_anonymity.py`, `publish_hf_private.py`, `prepare_anonymous_package.sh` |
| `tests/` | dataset integrity, benchmark semantics, scorer, reproducibility, publication hygiene |
| `docs/` | methodology, data schema, benchmark generation, evaluation protocol, reproducibility, limitations, provenance and licensing, anonymous package, release checklist, the Hugging Face dataset card |

## Reproducibility

`python scripts/validate_corpus.py` checks the corpus; `python scripts/reproduce_scores.py` scores the paper's reference predictions and compares with the paper; `pytest` runs the tests. What the generator reproduces and what it does not is stated in [docs/benchmark_generation.md](docs/benchmark_generation.md): the derived locator and text variants regenerate byte for byte from the published primary corpus; the 2026-08-01 primary corpus itself does not regenerate from the harvest available today, because the harvest files were extended after the corpus was frozen and were not versioned. The published task files, each with its record snapshot and hash, are the artifact of record.

## Licenses and provenance

Code: MIT. Data: CC BY 4.0, with the embedded records under their sources' terms (`data/NOTICE.md`). Details and open questions: [docs/provenance_and_licensing.md](docs/provenance_and_licensing.md).

## Status

Private, under double-anonymous review. Author names, citation, and links are withheld and will be filled in at publication (see `CITATION.cff` and [docs/release_checklist.md](docs/release_checklist.md)).
