---
license: cc-by-4.0
language:
- en
pretty_name: SUFFICE
size_categories:
- 1K<n<10K
task_categories:
- text-generation
tags:
- llm-agents
- tool-use
- evaluation
- evidence
- compliance
- benchmark
configs:
- config_name: default
  data_files:
  - split: balanced
    path: data/balanced.jsonl
  - split: natural
    path: data/natural.jsonl
  - split: dev
    path: data/dev.jsonl
  - split: val
    path: data/val.jsonl
- config_name: balanced
  data_files:
  - split: test
    path: data/balanced.jsonl
- config_name: natural
  data_files:
  - split: test
    path: data/natural.jsonl
- config_name: dev
  data_files:
  - split: test
    path: data/dev.jsonl
- config_name: val
  data_files:
  - split: test
    path: data/val.jsonl
- config_name: locator
  data_files:
  - split: test
    path: data/locator.jsonl
- config_name: onebranch
  data_files:
  - split: test
    path: data/onebranch.jsonl
- config_name: text
  data_files:
  - split: test
    path: data/text.jsonl
- config_name: fdaaa
  data_files:
  - split: test
    path: data/fdaaa.jsonl
---

# SUFFICE

SUFFICE tests whether an LLM agent completes the checks a conclusion requires before it states the conclusion. Each task gives the agent one real public record, a request about it, three conclusions of increasing strength, and the checks each conclusion needs. The agent reads fields of the record with tools and states the strongest conclusion it can justify. Which checks suffice for each conclusion is fixed in the task before any record is read, and the true value of every check is computed from the record, so scoring runs code: no language model or person judges an answer.

The benchmark accompanies the paper *PRIME: Towards Verifiable Evidence-Grounded Reasoning in LLM Agents* (under review). It is usable without PRIME: any agent that can read record fields and state conclusions can be scored, and the scorer makes no assumption about how the agent decided what to read or what to state.

**Generative.** Tasks are instantiated from 120 template families on real records by a deterministic generator (seed 20260801). The generator is released with the code repository; it regenerates the derived variants from the published corpus and generates further tasks from the same families on new records (see "Generation" below for what it does and does not reproduce).

| Domain | Source | One record is |
|---|---|---|
| `security` | GitHub Advisory Database, through OSV | a vulnerability advisory |
| `clinical` | ClinicalTrials.gov | a trial registration |
| `drugsafety` | openFDA drug enforcement reports | a drug recall |
| `financial` | SEC EDGAR XBRL company facts | a company's reported financial facts |

## Configurations

The **primary corpus** is 938 tasks in four splits. The **derived variants** are built from it for specific experiments and are not additional corpus tasks. The **fdaaa** configuration is an external standard applied to other records.

| Configuration | Tasks | Families | Kind | What it is |
|---|---|---|---|---|
| `balanced` | 480 | 60 | primary | the confirmatory set: 240 nested-route and 240 branching-route tasks, 120 per domain; 396 answerable, 84 with no supported conclusion; many tasks carry an engineered unsupported conclusion (a false check or unavailable evidence) |
| `natural` | 218 | 60 | primary | the same families with every conclusion supported (60 per domain; financial 38, the pool ran out) |
| `dev` | 192 | 48 | primary | development, families disjoint from the held-out ones |
| `val` | 48 | 12 | primary | validation, families disjoint from the held-out ones |
| `locator` | 480 | 60 | variant of `balanced` | each task is a copy of a balanced task (`parent_task_id`) in which every check withholds its field and instead gives a description and three candidate fields, the true one among them |
| `onebranch` | 240 | 40 | variant | new records on 40 branching families, in which exactly one of the two routes to the middle conclusion is degraded; the families were enumerated in a separate run, none coincides with a primary-corpus family, and their ids are local to this variant |
| `text` | 240 | 2 | variant | clinical and security tasks whose three upper checks are judgments on a free-text field, attested by the agent with a verbatim quote and scored against structured fields withheld from it |
| `fdaaa` | 319 | 124 | external standard | the U.S. results-reporting regulation (42 CFR Part 11), with the program written by an LLM coding assistant, applied to ClinicalTrials.gov registrations (domain `fdaaa_ctgov`; some checks have the reference value `U`, unresolved, when the registry holds no submission date) |

`default` exposes the four primary splits as one configuration (`balanced`, `natural`, `dev`, `val`).

```python
from datasets import load_dataset
ds = load_dataset("<namespace>/SUFFICE", "balanced", split="test")
```

Per-domain counts: balanced 120 per domain; natural 60/60/60/38 (security, clinical, drugsafety, financial); dev 48 per domain; val 12 per domain; locator 120 per domain; onebranch 60 per domain; text 120 clinical and 120 security; fdaaa 319 (domain `fdaaa_ctgov`).

## A row

Every row carries the complete task in its native format (`task_json`) plus flattened fields. Fields in **bold** are evaluator-only: never show them to an agent.

| Field | Meaning |
|---|---|
| `task_id`, `family_id`, `domain`, `topology` | identity; `topology` is `nested` (one route per conclusion, each extending the weaker one's) or `branching` (alternative routes for some conclusion) |
| `corpus_split`, `variant`, `parent_task_id` | `corpus_split` names the primary split (null for variants); `variant` is `none`, `locator`, `onebranch`, `text`, or `fdaaa`; `parent_task_id` links a locator task to its balanced source |
| `source_dataset`, `source_record_id` | where the record came from |
| `request`, `scope` | what the agent is asked and what evidence is in scope |
| `conclusions`, `conclusion_order` | `id`, `level` (1 weakest to 3 strongest), `text`; `[weaker, stronger]` pairs |
| `evidence_atoms` | each check: `id`, `available`, `tool` (`inspect_record` or `attest_atom`), `record_id`, `field_path` (or `candidate_fields` on locator tasks, or `text_source` and `description` on text tasks), `predicate` |
| `sufficient_routes` | for each conclusion, each minimal set of literals that suffices for it (`!E3` means check E3 must be false) |
| `constraints` | the constraint formula; empty in every task |
| `specification_view` | the agent-visible content above as one JSON object, what an agent given the rule sees |
| **`reference_atom_values`** | the value, `T` or `F`, of every check on this record |
| **`reference_supported_conclusions`**, **`strongest_supported_level`**, **`answerable`** | the conclusions the record supports under the intended standard |
| `record_json` | the frozen snapshot of the record; the agent reaches it only through the evidence actions |
| `generator_seed`, `generator_version`, `schema_version`, `task_sha256` | provenance; `manifest.json` lists every task's hash |
| `task_json` | the complete native task |

> **Evaluator-only fields.** Rows carry the hidden reference values (`reference_atom_values`, `reference_supported_conclusions`, `strongest_supported_level`, `answerable`), the complete native task with its labels (`task_json`), and the full record (`record_json`), because the scorer needs them. Never give a whole row to an evaluated agent: it would see the answers, and the evaluation of evidence acquisition would be void. Give it `specification_view`, which is exactly `RecordEnv(task).agent_view()`, or `suffice.export.agent_visible(row)`, and let it reach the record only through the evidence actions, which the scorer replays against the frozen record.

```python
import json
from datasets import load_dataset
from suffice import RecordEnv, score
from suffice.export import row_to_task

rows = load_dataset("<namespace>/SUFFICE", "balanced", split="test")
row = rows[0]
view = json.loads(row["specification_view"])   # show this to the agent: request, conclusions, checks, routes; no values
task = row_to_task(row)                        # evaluator side only: holds the labels
env = RecordEnv(task)                          # route the agent's tool calls through env
obs = env.inspect_record(view["checks"][0]["record_id"], view["checks"][0]["field_path"])
prediction = {"task_id": row["task_id"], "stated": ["C1"], "actions": env.actions}
print(score({task["id"]: task}, [prediction])["overall"])
```

Records change over time. Every task embeds the snapshot it was built from, so results do not depend on when the benchmark is run.

## Running an agent and scoring it

The `suffice/` package shipped in this directory needs only the Python standard library:

```python
from suffice import load_tasks, RecordEnv, score

tasks = load_tasks("data/balanced.jsonl")
env = RecordEnv(tasks["sec-v2-0114"])
env.agent_view()                                   # what the agent may see; no check values
env.inspect_record("GHSA-5pqf-rvm7-3wgw", "details")   # {"value": ...} or {"error": ...}
env.actions                                        # record these with the agent's answer
```

Write one JSON object per task and score:

```json
{"task_id": "sec-v2-0114", "stated": ["C1"], "actions": [{"inspect_record": ["GHSA-5pqf-rvm7-3wgw", "details"]}]}
```

```bash
python -m suffice evaluate --tasks data/balanced.jsonl --predictions my_agent.jsonl --by domain --output results.json
```

The scorer replays the actions against the record; it never relies on an agent's own account of what it checked. Endpoints: false authorization (a stated conclusion the record does not support), premature conclusions (stated before the agent's own actions established a route), supported utility (33.3, 66.7, or 100 for the strongest supported stated conclusion, 0 if none), evidence value (the utility the actions established, stated or not), emission rate on answerable tasks, evidence recall, tool calls, and, on text tasks, resolver error (accepted attestations whose value is wrong). The exact definitions are in `suffice/scoring.py`.

On text tasks the runtime accepts an attestation only when the source text was read and the quote occurs in it verbatim; acceptance does not mean the quote entails the asserted condition, and the reference value comes from a structured field the agent cannot see. There is no human-adjudicated entailment set.

## Generation

The generator (code repository, `suffice generate`) enumerates 30 families per domain (20 branching, 10 nested) from a per-domain pool of field probes, assigns families to dev/val/held-out splits (40/10/50, families held out whole), instantiates each family on records, degrades a route (a false check or unavailable evidence) to create unsupported conclusions, computes the reference values by running every check, and keeps a task only if its checks execute to the stored values. It regenerates every published task byte for byte (the 938 primary tasks and the `onebranch`, `locator`, and `text` variants, 1,898 in all) from the harvest of 2026-08-01, which the code repository ships reduced to the fields the generator reads (`scripts/reproduce_corpus.py`). An earlier version seeded its family enumeration with Python's per-process string hash, so separate runs drew different families; the seed offsets of the published runs were recovered and are pinned. The published task files, each with its record snapshot and SHA-256 hash, remain the artifact of record.

## Intended uses and limitations

Intended: evaluating tool-using LLM agents that must justify conclusions from checks; evidence-grounded decision making under a call budget; detecting unsupported conclusions; comparing enforcement and verification methods on identical tasks and scoring.

Limitations: the tasks are one generated review structure (three ordered conclusions, field predicates on one record) over four public-record domains; the conclusion hierarchies and reference standards are fixed by construction and are the benchmark's, not an organization's; the balanced split engineers unsupported conclusions and does not estimate their prevalence in deployed workloads; checks are mechanically decidable except on the text variant, where the model's interpretation of unstructured evidence can be wrong and is scored against a structured proxy; results do not transfer to arbitrary workflows; and a perfect score establishes compliance with the task's standard, not that the standard is correct. The benchmark does not show that any agent is clinically safe, financially compliant, or ready for deployment.

## Provenance and licensing

Records were retrieved on 1 August 2026 (FDAAA set: 3 August 2026) from the sources above; `NOTICE.md` gives each source's terms. The benchmark data are released under CC BY 4.0; the embedded records remain subject to their sources' terms (GitHub Advisory Database CC BY 4.0; openFDA public domain; ClinicalTrials.gov and SEC EDGAR public U.S. government information). The scoring code is MIT-licensed.

## Citation

The paper is under double-anonymous review; the citation will be added at publication.
