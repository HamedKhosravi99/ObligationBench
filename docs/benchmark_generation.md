# Benchmark generation

The generator is the authentic implementation, vendored from the PRIME code into `src/obligationbench/generation/`:

| Module | Origin | What it does |
|---|---|---|
| `record_tasks.py` | `bench/generate_record_instances.py` | the primary corpus: enumerates 30 families per domain (20 branching, 10 nested, crossed with a homogeneous/heterogeneous call-cost profile) from a per-domain pool of field probes; assigns families 40/10/50 to dev/val/held-out, families whole; instantiates families on harvested records (one family per record); targets the strongest-supported level by a fixed cycle (~30/30/25/15 for levels 3/2/1/0) and degrades a route by a false check (a required value taken from another record, or a date one year earlier) or by unavailable evidence; computes claim denotations and reference values; verify-or-drop. Also `--locator-per-domain N` (derives the locator variant from the balanced split) and `--one-branch-per-domain N` (the one-branch variant). |
| `text_tasks.py` | `bench/generate_text_instances.py` | the text-evidence variant: clinical and security tasks whose checks are judgments on a free-text field with structured twins withheld from the record |
| `harvest.py` | `bench/harvest_records.py` | live retrieval of source records with provenance (URL, timestamp, SHA-256); key-free public APIs |

Changes made for packaging are listed at the top of each file: import lines, the bench directory (`OBLIGATIONBENCH_BENCH_DIR`), and `verify()`, which executes resolvers with the package's `RecordEnv` instead of the PRIME runtime (same predicate code, same rule). The verify step was checked by validating every published task with it (`obligationbench validate`): all execute to their stored reference values.

## Running it

```bash
export OBLIGATIONBENCH_BENCH_DIR=/path/to/bench        # holds harvest/<domain>/records.jsonl; tasks go to instances_v2/
obligationbench generate records                          # primary corpus (default quotas: see configs/corpus.yaml)
obligationbench generate records -- --one-branch-per-domain 60 --seq-base 9000
obligationbench generate records -- --locator-per-domain 120
obligationbench generate text
obligationbench generate harvest                          # live retrieval; not reproducible
```

Three distinct uses:

1. **Regenerating the published benchmark.** Reproducible: `python scripts/reproduce_corpus.py` regenerates all 1,898 tasks (primary corpus and the one-branch, locator, and text variants) byte for byte from `inputs/harvest/`.
2. **Regenerating only the derived variants from the published primary corpus.** `python scripts/reproduce_corpus.py --what variants`, with the generator manifest of `inputs/generator_manifest.json`.
3. **Generating additional tasks.** The same families on new records: harvest records into `harvest/<domain>/records.jsonl` (or supply your own in that format) and run the generator with `--records-offset` and `--seq-base` so that ids do not collide. The generator does not design new evidence standards; new template families require editing the probe pools in `record_tasks.py`.

## What regenerates (verified 2026-10-11)

| Target | Input | Result |
|---|---|---|
| primary corpus (938 tasks, 2026-08-01) | `inputs/harvest/` or the full harvest | 938 of 938 identical |
| one-branch variant (240, 2026-10-08) | the same, after the primary corpus | 240 of 240 identical |
| locator variant (480) | the same, after the one-branch variant | 480 of 480 identical |
| text variant (240) | the same | 240 of 240 identical |

Every row holds under any `PYTHONHASHSEED`; the test suite regenerates the corpus under two.

**Why earlier versions did not regenerate the corpus.** The generator seeded each domain's family enumeration with `random.Random(SEED + hash(domain) % 1000)`. Python randomizes string hashes in every process, so each run drew its own offset per domain and enumerated different families, which then selected and built different tasks. Two runs in one process agree, which is why an earlier determinism test passed.

Enumerating the families for each of the 1,000 possible offsets and comparing them with the published files identifies one offset per domain:
- for the primary corpus, run on 2026-08-01: security 472, clinical 363, drugsafety 94, financial 382;
- for the one-branch variant, run on 2026-10-08: security 965, clinical 547, drugsafety 464, financial 866.

`record_tasks.py` now pins both sets of offsets (`FAMILY_SEED_OFFSET`, `ONE_BRANCH_FAMILY_SEED_OFFSET`). A new domain gets a stable offset derived from its name.

The harvest itself was intact: every record the published tasks use is in it, and the harvest files predate the corpus. An earlier version of this document blamed an extension of the financial pool. That extension happened on 2026-08-01 before the corpus was generated, so it is not the cause.

One more difference was fixed: the generator now writes the note key `one_branch` only on one-branch tasks, as the generator of 2026-08-01 did.

**One-branch family ids.** The one-branch run enumerated its own families, so a one-branch family id (for example `clinical-branching-hom-17`) names a different probe set than the same id in the primary corpus. None of the 40 one-branch families coincides with a primary-corpus family, by routes or by probe set, so the variant is held out from every primary split. Treat its family ids as local to the variant.

Families: 120 in the primary corpus (30 per domain). Family ids look like `clinical-nested-hom-05`: domain, topology, cost profile, index.
