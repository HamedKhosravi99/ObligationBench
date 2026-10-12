# Limitations

These are the limitations the paper acknowledges, restated for users of the benchmark alone.

* **One review structure.** Every task has three conclusions in a chain and checks that are single-field predicates on one record (or, on the text variant, judgments on one free-text field). Workflows with other structures are not represented.
* **Benchmark-fixed standards.** Which checks suffice for each conclusion is fixed by the generator's template families. The reference standard is the benchmark's, not an organization's; a perfect score establishes compliance with the task's standard, not that the standard is right.
* **Engineered difficulty.** The balanced split degrades routes deliberately (a false check or unavailable evidence) so that unsupported conclusions occur. It does not estimate how often they arise in deployed workloads; the natural split, with every conclusion supported, gives one point of comparison.
* **Mechanically decidable checks.** Outside the text variant, every check is decided by code on a stored field. The text variant scores the model's judgment of unstructured evidence against a structured proxy; an accepted quotation does not guarantee that it entails the assertion, and no human-adjudicated entailment set exists.
* **Four domains, public records.** Security advisories, trial registrations, drug recalls, and financial facts from public databases, retrieved once and frozen. Results do not transfer to arbitrary records or workflows.
* **Two families per domain on the text variant, one family per domain in some analyses.** Family-level statistics on the text variant rest on two clusters; record-level intervals are reported there.
* **Enforcement versus correctness.** The benchmark separates enforcing a standard from determining whether the standard is correct; it measures the former. Obtaining a correct standard (learning which evidence suffices, or constructing the standard) remains the hard part, and the benchmark does not test it.
* **Not a safety certificate.** Nothing here shows that an agent is clinically safe, financially compliant, or ready for deployment.
