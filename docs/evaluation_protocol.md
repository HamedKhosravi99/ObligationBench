# Evaluation protocol

## Prediction format

One JSON object per task:

```json
{"task_id": "sec-v2-0114",
 "stated": ["C1"],
 "actions": [{"inspect_record": ["GHSA-5pqf-rvm7-3wgw", "details"]},
             {"inspect_record": ["GHSA-5pqf-rvm7-3wgw", "database_specific.github_reviewed"]}]}
```

* `stated`: the conclusion ids the agent stated; `[]` is an abstention. For an enforced agent whose runtime states the final conclusion, that conclusion goes here too.
* `actions`: the evidence actions in the order they were made: `{"inspect_record": [record_id, field_path]}`, `{"read_text": [record_id, field_path]}`, `{"attest_atom": [atom_id, value, quote]}`. The legacy key `reads`, a list of `[record_id, field_path]` pairs, is accepted for `inspect_record` reads only.
* Other keys (`agent`, `model`, `budget`, `calls`, `note`) are kept for bookkeeping and ignored by the scorer.

Malformed records (missing `task_id`, `stated` not a list, unknown conclusion ids, duplicate task ids, predictions for tasks not in the file) raise `PredictionError`; the CLI exits with status 2. A task without a prediction counts as an abstention by default (`--missing error` makes it an error).

## Scoring

```bash
obligationbench evaluate --tasks data/balanced.jsonl --predictions predictions.jsonl --by domain --output results.json
```

For every task the scorer replays the actions through `RecordEnv`, which settles a check only when the agent read the check's true field (the predicate is evaluated on the returned value) or, on text tasks, when an attestation was accepted. It never uses an agent's own account of its evidence.

| Endpoint | Definition |
|---|---|
| false authorization (%) | tasks on which some stated conclusion is not supported by the record (no route of it holds on the reference values) |
| premature (%) | tasks on which some stated conclusion was not established by the replayed ledger, directly or through a stronger established conclusion |
| utility | supported utility: 100 x level of the strongest supported stated conclusion / 3 (33.3, 66.7, 100); 0 when nothing supported was stated; averaged over tasks |
| evidence value | utility of the strongest conclusion the replayed ledger establishes, stated or not |
| emission rate (%) | answerable tasks (some conclusion is supported) on which the agent stated anything |
| abstention (%) | tasks with no stated conclusion |
| evidence recall (%) | checks on the task's routes that the actions settled |
| mean tool calls, mean reads | per task |
| resolver error (%) | text tasks: accepted attestations whose value differs from the reference value; also the share of episodes with at least one such attestation |

The per-task rows (`--rows`) carry `record`, `family`, `domain`, `topology`, and every endpoint, so family-level contrasts can be computed with `obligationbench.stats` (see below).

## Text-evidence tasks

An attestation is accepted when the check's source text was read earlier in the episode and the quote, whitespace-normalized and case-insensitive, occurs in it and has at least eight characters. Acceptance checks occurrence, not meaning: an accepted quote need not entail the asserted condition. The attested value is recorded as given and scored against the reference value, which comes from a structured field withheld from the agent. The gap between "the quote occurs", "the quote supports the assertion", and "the assertion agrees with the reference field" is the resolver-error term; there is no human-adjudicated entailment set.

## Settings an agent can be run in

The scorer is the same for all; what differs is what the agent is shown.

| Setting | Agent sees | Routes |
|---|---|---|
| supplied standard | `specification_view` | given |
| learned sufficiency (S2) | `specification_view` without `routes` | the agent infers them before acting |
| constructed standard (S1) | request, scope, tools | the agent proposes conclusions, checks, and routes |

Document which setting a reported number used; the paper's main results use the supplied standard.

## Statistics

The unit of inference is the template family. `obligationbench.stats` (the paper's implementation) provides family-mean paired differences, a sign-flip randomization test stratified by domain and topology, a hierarchical bootstrap interval (families, then records), the exact McNemar sensitivity test, TOST equivalence, and Holm correction. `obligationbench.scoring.paired_rows(result_a, result_b, key)` pairs two scored results for these functions. Pooled rates in the tables are not the family-mean contrasts.
