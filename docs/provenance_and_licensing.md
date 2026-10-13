# SUFFICE provenance and licensing report

## Source records

| Domain | Source | Retrieval | Sampling frame | Terms |
|---|---|---|---|---|
| security | GitHub Advisory Database, PyPI ecosystem, through the OSV bulk export (`PyPI/all.zip`, SHA-256 `f9f53e19...aaa5`) | 2026-08-01 | lexicographic prefix of all 24,635 advisories, 1,200 retained with `affected[]` and summary/details | CC BY 4.0; attribution "Contains advisories from the GitHub Advisory Database, licensed under CC BY 4.0" |
| clinical | ClinicalTrials.gov API v2 (`/studies?pageSize=1000`) | 2026-08-01 | API default order, first pages; 1,200 retained with `nctId` and `overallStatus` | public registry data under the ClinicalTrials.gov terms and conditions |
| drugsafety | openFDA drug enforcement endpoint | 2026-08-01 | endpoint default order from offset 0; 1,200 retained with `recall_number` and `classification` | public domain (CC0 1.0); not to be relied on for decisions about medical care |
| financial | SEC EDGAR XBRL company facts | 2026-08-01 | a frozen alphabetical large-cap CIK list (60), extended the same day by the first 420 unique CIKs of `company_tickers.json` (340 added) | public information; retrieved under the SEC fair-access policy with a declared User-Agent |
| fdaaa (clinical) | ClinicalTrials.gov | 2026-08-03 | registrations subject to 42 CFR Part 11 by the compiled rule: 319 of 5,519 classified | as clinical |

Every task embeds only the fields of its record that the task can read (`records` in the native task), not the full source record. Original record identifiers are kept (`source_record_id`).

## Redistribution

The embedded snapshots are redistributed under the sources' terms above, which permit it with attribution (GitHub Advisory Database), without restriction (openFDA, SEC), or as public registry data (ClinicalTrials.gov). No source endorses the dataset. The FDAAA TrialsTracker table used in the paper to compare the compiled rule's verdicts is third-party data and is not part of the release.

## Licenses

| Work | License |
|---|---|
| the benchmark data (task files, manifest, reference predictions) | CC BY 4.0 (`data/LICENSE`) |
| the embedded records | their sources' terms (`data/NOTICE.md`) |
| the code (generator, scorer, scripts, tests, docs) | MIT (`LICENSE`) |

The predicate grammar, task schema, closure, and statistics modules are the original PRIME code files, also MIT.

## Open questions for the authors

* The authors' names, affiliations, and contact go into `CITATION.cff`, `data/LICENSE`, the dataset card, and the README at publication; they are withheld now for double-anonymous review.
* Whether to request permission to redistribute the FDAAA TrialsTracker table (Bennett Institute, University of Oxford); without it, the FDAAA comparison in the paper is not reproducible from this release.
