# Anonymous supplementary package for ARR/NAACL

ARR submissions are double-anonymous. A private GitHub or Hugging Face URL is not usable as supplementary material: the repository name, its owner, and its history identify the authors, and a private link cannot be opened by reviewers. The supplementary material is therefore two archives uploaded with the submission.

## Build

```bash
scripts/prepare_anonymous_package.sh dist/suffice-dataset dist/anonymous
```

produces

* `anonymous/suffice-code.zip`: this repository (code, tests, docs, examples, scripts) without `.git`, with `CITATION.cff` and the licenses carrying "authors withheld", and with every URL to an identity-linked repository removed;
* `anonymous/suffice-data.zip`: the dataset directory (data, manifest, card, licenses, the scoring package, reference predictions).

The script then scans both archives with `scripts/check_anonymity.py` and refuses to finish if any author name, e-mail, local path, cluster name, account, or token survives.

## Rules observed

* no author names, affiliations, acknowledgments, grant numbers, or contact addresses;
* no links to personal or institutional pages, private repositories, or prior non-anonymous versions;
* the paper's text refers to "the anonymized package accompanying the submission", not to a URL;
* the archives contain only public-record data and code;
* the FDAAA TrialsTracker table, which is third-party data, is not included.

At acceptance, the public repositories replace the archives and the citation record is filled in (docs/release_checklist.md).
