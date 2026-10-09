# Reproducibility

Three levels, which need different resources.

## 1. Deterministic benchmark and scoring reproduction (CPU, seconds to minutes)

```bash
pip install -e .[dev]
python scripts/validate_corpus.py                 # counts, structure, reference labels of data/*.jsonl
python scripts/reproduce_scores.py                # score the paper's reference predictions, compare with the paper
pytest                                            # all tests; set OBLIGATIONBENCH_BENCH_DIR for the original-file comparison
```

`reproduce_scores.py` scores the reference predictions (`data/reference_predictions/<model>/<agent>.jsonl`, one per agent of the paper's enforcement ladder and comparators on the 480 balanced tasks) with the released scorer and compares false authorization, premature conclusions, supported utility, emission rate, and evidence value with the values printed in the paper; it exits nonzero on any difference above 0.05. The reference predictions were rebuilt from the paper's episode logs using only the stated conclusions and the recorded reads.

## 2. Corpus regeneration (CPU, minutes)

```bash
python scripts/reproduce_corpus.py --bench /path/to/bench --what variants   # locator and text from the published primary corpus
python scripts/reproduce_corpus.py --bench /path/to/bench --what primary    # the primary corpus from the harvest (does not reproduce; see below)
```

The script regenerates into a temporary directory and reports, per split, how many tasks are byte-identical to the published files. See docs/benchmark_generation.md for what reproduces (locator 480/480, text 240/240) and what does not (the 2026-08-01 primary corpus and the one-branch variant, because the harvest changed and was not versioned).

## 3. Episode replay and live inference (GPU)

The paper's episode logs, the agents, and the PRIME runtime are in the PRIME code repository, not here. Replaying logged episodes or re-running agents needs that repository and a served model (the paper used Qwen2.5-32B-Instruct with vLLM). Nothing in this repository needs a GPU.

## Statistical reproduction

`obligationbench.stats` is the paper's statistics code. Given two scored results, `paired_rows` pairs them per task; `template_cluster_randomization` gives the family-level sign-flip test, `hierarchical_cluster_bootstrap` the 95% interval, `holm` the correction. The paper's minimum effect for guidance (6.16 utility points) and multiplicity groups are in `configs/evaluation.yaml`.
