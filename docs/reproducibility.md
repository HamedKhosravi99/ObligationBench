# Reproducibility

Two different claims are checked:
- **Scoring reproducibility.** Anyone can recompute the benchmark's labels and the paper's scores from the released tasks.
- **Generator reproducibility.** Anyone can rebuild the released tasks themselves from the source records.

Both hold for every task except the FDAAA set, whose builder lives in the PRIME code and needs a third-party table. A third level, rerunning the agents, needs the PRIME code and a GPU.

## 1. Scoring reproducibility (CPU, seconds)

```bash
pip install -e .[dev]
python scripts/validate_corpus.py      # counts, structure, hashes, and reference labels of data/*.jsonl
python scripts/reproduce_scores.py     # the paper's reference predictions, scored and compared with the paper
pytest                                 # every test, including the two below
```

`validate_corpus.py` re-executes every check of every task on its stored record and compares the result with the stored reference value. It also recomputes each task's SHA-256 and compares it with `data/manifest.json`.

`reproduce_scores.py` scores the reference predictions (`data/reference_predictions/<model>/<agent>.jsonl`): one file per agent of the paper's enforcement ladder and per comparator, on the 480 balanced tasks. The predictions were rebuilt from the paper's episode logs using only the stated conclusions and the recorded reads, never an agent's own account of its evidence. The script compares false authorization, premature conclusions, supported utility, emission rate, and evidence value with the paper's values and exits nonzero on any difference above 0.05.

It also checks the denominators. Every agent ran on all 480 tasks. An episode whose model calls still timed out after the client's retries carries no measurement and has no prediction. `EXCLUDED.json` declares these episodes: 24 over the 15 agents, at most 6 for one agent. The script reports, per agent, the tasks, the exclusions, and the scored episodes, and it fails if any other prediction is missing.

`tests/test_conformance.py` checks that this package's evidence handling agrees with the PRIME runtime. It compares against outcomes the runtime produced (`tests/fixtures/prime_conformance.json.gz`, written by the PRIME code's `bench/conformance.py`):
- the observation and settled checks of every read of every record task;
- the authorized conclusions for seeded check-value states;
- the acceptance and state of text attestations through a fixed sequence;
- for the 7,176 completed reference episodes, the settled checks, the established conclusions, and the distinct call classes charged.

## 2. Generator reproducibility (CPU, seconds)

```bash
python scripts/reproduce_corpus.py            # --what all (default) | primary | variants
```

The script regenerates, into a temporary directory, the primary corpus (938 tasks) and then the one-branch (240), locator (480), and text (240) variants, in the order they were made. It compares every task with the published one byte for byte and exits nonzero unless all 1,898 are identical. They are.

The input is `inputs/harvest/`: the records harvested on 2026-08-01, in their original order, reduced by `scripts/reduce_harvest.py` to the 55 record paths the generators read. The full harvest is 2.3 GB, almost all of it SEC company facts that no check reads. `inputs/harvest/SHA256SUMS.json` gives the hashes of the full and the reduced files, and every published task also regenerates from the full harvest. Four credential-like strings quoted in advisories' proofs of concept are masked in the reduced files, and no published task contains them.

The generator is deterministic. Earlier versions were not: they seeded each domain's family enumeration with Python's string hash, which is randomized per process, so a rerun enumerated different families. The offsets the published runs drew were recovered by matching the enumerated families against the published files, and they are now pinned; [benchmark_generation.md](benchmark_generation.md) has the details. `tests/test_reproducibility.py` regenerates the corpus in fresh interpreters under two different hash seeds.

The FDAAA set (319 tasks) is built by the PRIME code (`bench/fdaaa/build_fdaaa_instances.py`). Its inputs are a ClinicalTrials.gov snapshot and the FDAAA TrialsTracker table of 3 August 2026, which belongs to the Bennett Institute for Applied Data Science and is not redistributed. Both are pinned by SHA-256.

## 3. Episode replay and live inference (GPU)

The paper's episode logs, the agents, and the PRIME runtime are in the PRIME code repository, together with:
- a script that regenerates every table of the paper from the logs, which reproduces each one byte for byte;
- a record of the software and hardware of the runs.

Re-running agents needs that repository and a served model; the paper used Qwen2.5-32B-Instruct with vLLM. Nothing in this repository needs a GPU.

## Statistical reproduction

`suffice.stats` is the paper's statistics code:
- `paired_rows` pairs two scored results per task;
- `template_cluster_randomization` gives the family-level sign-flip test;
- `hierarchical_cluster_bootstrap` gives the 95% interval;
- `holm` gives the correction.

`configs/evaluation.yaml` holds the paper's minimum effect for guidance (6.16 utility points) and its multiplicity groups.
