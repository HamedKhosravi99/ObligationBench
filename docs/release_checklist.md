# Release checklist

Both repositories stay **private** until the authorized milestone. No step here changes visibility.

## Before any upload

- [ ] `python scripts/validate_corpus.py` passes
- [ ] `python scripts/reproduce_scores.py` prints "all agents match the paper"
- [ ] `pytest` passes (with `OBLIGATIONBENCH_BENCH_DIR` set for the original-file comparison)
- [ ] `python scripts/check_anonymity.py` finds no identifying string, path, account, or token in the dataset directory and the code
- [ ] `git log` and tracked files contain no secrets (`git grep -I -E 'hf_[A-Za-z0-9]{20,}|ghp_[A-Za-z0-9]{20,}'` is empty)
- [ ] `data/NOTICE.md` lists every source and its terms; the FDAAA TrialsTracker table is absent
- [ ] the dataset card's YAML lists every configuration and every file exists

## Private Hugging Face dataset

- [ ] `hf auth login` done by the owner; `HF_NAMESPACE` set in the environment
- [ ] `python scripts/publish_hf_private.py --dataset-dir dist/obligationbench-dataset --repo <namespace>/ObligationBench --confirm` (creates the repository private, uploads, verifies visibility, counts, authenticated load, and unauthenticated refusal, prints the commit id)
- [ ] the dataset viewer shows the eight configurations

## Private GitHub code repository

- [ ] `gh repo create <owner>/obligationbench --private --source . --push` from the code directory (ask before creating)
- [ ] no release, tag, or DOI yet

## Anonymous review package (ARR/NAACL)

- [ ] built by `scripts/prepare_anonymous_package.sh`: a software archive and a data archive without authors, affiliations, paths, accounts, or links to identity-linked repositories
- [ ] the paper cites no identity-linked URL

## Public release (after the authorized milestone)

- [ ] fill in authors, citation, DOI in `CITATION.cff`, `data/LICENSE`, the dataset card, and the README
- [ ] tag `v1.0.0`, write release notes (contents, counts, what regenerates), attach nothing that contains private data
- [ ] make the Hugging Face dataset public in its settings, then the GitHub repository (explicit, manual actions)
- [ ] verify from a clean clone: `pip install -e .`, `python scripts/validate_corpus.py`, `python scripts/reproduce_scores.py`
