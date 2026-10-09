# Benchmark generation

The generator is the authentic implementation, vendored from the PRIME code into `src/obligationbench/generation/`:

| Module | Origin | What it does |
|---|---|---|
| `record_tasks.py` | `pilot/bench/generate_record_instances.py` | the primary corpus: enumerates 30 families per domain (20 branching, 10 nested, crossed with a homogeneous/heterogeneous call-cost profile) from a per-domain pool of field probes; assigns families 40/10/50 to dev/val/held-out, families whole; instantiates families on harvested records (one family per record); targets the strongest-supported level by a fixed cycle (~30/30/25/15 for levels 3/2/1/0) and degrades a route by a false check (a required value taken from another record, or a date one year earlier) or by unavailable evidence; computes claim denotations and reference values; verify-or-drop. Also `--locator-per-domain N` (derives the locator variant from the balanced split) and `--one-branch-per-domain N` (the one-branch variant). |
| `text_tasks.py` | `pilot/bench/generate_text_instances.py` | the text-evidence variant: clinical and security tasks whose checks are judgments on a free-text field with structured twins withheld from the record |
| `harvest.py` | `pilot/bench/harvest_records.py` | live retrieval of source records with provenance (URL, timestamp, SHA-256); key-free public APIs |

Changes made for packaging are listed at the top of each file: import lines, the bench directory (`OBLIGATIONBENCH_BENCH_DIR`), and `verify()`, which executes resolvers with the package's `RecordEnv` instead of the PRIME runtime (same predicate code, same rule). The verify step was checked by validating every published task with it (`obligationbench validate`): all execute to their stored reference values.

## Running it

```bash
export OBLIGATIONBENCH_BENCH_DIR=/path/to/bench        # holds harvest/<domain>/records.jsonl; tasks go to instances_v2/
obligationbench generate records                          # primary corpus (default quotas: see configs/corpus.yaml)
obligationbench generate records -- --locator-per-domain 120
obligationbench generate records -- --one-branch-per-domain 60
obligationbench generate text
obligationbench generate harvest                          # live retrieval; not reproducible
```

Three distinct uses:

1. **Regenerating the published benchmark.** Not reproducible from the inputs available today; see below. The published files are the artifact.
2. **Regenerating the derived variants from the published primary corpus.** Reproducible: with the published `balanced`, `natural`, `dev`, and `val` tasks in place, `--locator-per-domain 120` reproduces all 480 locator tasks byte for byte and `generate text` reproduces all 240 text tasks (verified 2026-10-09). The one-branch variant is not reproduced (0 of 240) by any version of the generator on the current harvest.
3. **Generating additional tasks.** The same families on new records: harvest records into `harvest/<domain>/records.jsonl` (or supply your own in that format) and run the generator with `--records-offset` and `--seq-base` so that ids do not collide. The generator does not design new evidence standards; new template families require editing the probe pools in `record_tasks.py`.

## What regenerates and what does not (verified)

| Target | Generator version | Result |
|---|---|---|
| primary corpus (938 tasks, 2026-08-01) | current (`37b06f1b2`) on the current harvest | 0 of 938 identical; different records selected, different probes in some families |
| primary corpus | the version that produced it (`8b8c4ad23`, 2026-08-01) on the current harvest | 0 of 938 identical; different records selected |
| locator variant (480) | current, from the published primary corpus | 480 of 480 identical |
| text variant (240) | current, from the current harvest | 240 of 240 identical |
| one-branch variant (240, 2026-10-08) | current, `70d870987`, and `fc5af1289`, from the published primary corpus | 0 of 240 identical; different records selected |

Cause: the harvested record files (`harvest/<domain>/records.jsonl`) were not under version control, and at least the financial pool was extended (340 CIKs added) after the corpus was frozen; the record order the generator shuffles from has changed, so the same seed selects different records. The generator itself is deterministic (two runs on the same harvest and seed give identical files; tested). The published tasks embed their record snapshots and are listed with SHA-256 hashes in `manifest.json`; they are what the paper's experiments used.

Families: 120 in the primary corpus (30 per domain). Family ids look like `clinical-nested-hom-05`: domain, topology, cost profile, index.
