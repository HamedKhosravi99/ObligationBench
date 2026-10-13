# Data schema (schema version 1.0)

Two representations exist. The **native task** is the JSON object the generator writes and the scorer reads (`src/suffice/task_schema.json` gives its JSON Schema; `instance_schema.py` validates it). The **dataset row** is the flattened record published on Hugging Face and in `data/*.jsonl`; it carries the native task verbatim in `task_json`, so `suffice.export.row_to_task(row)` recovers it exactly and `task_to_row(task, split)` produces the row (round trips are tested).

## Native task

| Key | Content |
|---|---|
| `id` | task id, for example `sec-v2-0114` (locator copies: `sec-v2-6114`; one-branch: `sec-v2-9001`; text: `cli-v2-7002`; fdaaa: `fdaaa-NCT...`) |
| `domain` | `security_v2`, `clinical_v2`, `drugsafety_v2`, `financial_v2` (`clinical` for fdaaa) |
| `seed` | the record identifier |
| `user_prompt`, `scope` | the request and the scope statement |
| `actions` | the tools the agent may call |
| `claims` | the conclusions: `id`, `level`, `text`, `denotation` (a machine-readable rendering of what the sentence asserts) |
| `order` | `[weaker, stronger]` pairs |
| `atoms` | the checks: `id`, `type`, `gold_value` (reference value), `resolver` (`tool`, `params`, `params_schema`, `attest` rule) or `null` when the evidence is unavailable; `spec_hint` on locator tasks (`what`, `candidates`) and text tasks (`what`, `source`) |
| `phi` | the constraint formula; empty |
| `gold_licenses` | the routes: conclusion id -> list of routes, each a list of literals |
| `decoys` | unused |
| `records` | record id -> the frozen record snapshot (only the fields the task can read) |
| `notes_for_annotators` | generator metadata as a JSON string: `family`, `topology`, `cost`, `target_level`, `false_mech`, and for text tasks `truths` and `twins` |
| `variant`, `artifact` | generator bookkeeping |

The check predicate grammar (`attest` rules of the form `record_predicate:<type>:<json value>`) has ten types: `exists`, `equals`, `not_equals`, `in`, `contains`, `numeric_ge`, `numeric_le`, `date_after`, `date_before`, `version_in_range`; `predicates.py` documents and implements them. Text checks use the rule `attested`.

## Dataset row

| Field | Type | Agent-visible | Content |
|---|---|---|---|
| `task_id` | string | yes | native `id` |
| `family_id` | string | yes | template family |
| `domain` | string | yes | `security`, `clinical`, `drugsafety`, `financial` |
| `corpus_split` | string or null | yes | `balanced`, `natural`, `dev`, `val`; null for variants |
| `variant` | string | yes | `none`, `locator`, `onebranch`, `text`, `fdaaa` |
| `parent_task_id` | string or null | yes | locator tasks: the balanced task they derive from |
| `topology` | string | yes | `nested` or `branching` |
| `source_dataset`, `source_record_id` | string | yes | provenance of the record |
| `request`, `scope` | string | yes | |
| `conclusions` | list of {id, level, text} | yes | |
| `conclusion_order` | list of [weaker, stronger] | yes | |
| `evidence_atoms` | list | yes | per check: `id`, `available`, `tool`, `record_id`, `field_path`, `candidate_fields`, `text_source`, `description`, `predicate` |
| `sufficient_routes` | list of {conclusion, literals} | yes (rule-supplied setting) | |
| `constraints` | list | yes | empty |
| `specification_view` | JSON string | yes | the agent view as `RecordEnv.agent_view()` produces it |
| `reference_atom_values` | list of {id, value} | **no** | the reference value of every check |
| `reference_supported_conclusions` | list of string | **no** | |
| `strongest_supported_level` | int | **no** | 0 when nothing is supported |
| `answerable` | bool | **no** | |
| `generator_seed` | int | yes | 20260801 |
| `generator_version`, `schema_version` | string | yes | |
| `task_sha256` | string | yes | SHA-256 of the sorted-key JSON of the native task; `manifest.json` lists every one |
| `record_json` | JSON string | through tools | the record snapshot |
| `task_json` | JSON string | contains labels | the native task; strip `gold_value` before showing it to an agent, or use `specification_view` |

`suffice.export.agent_visible(row)` drops the evaluator-only fields and the record.

## Prediction record

One JSON object per task; see docs/evaluation_protocol.md.
