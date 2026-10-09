# Methodology

ObligationBench measures one thing: whether an agent that must justify a conclusion from checks on a record states only conclusions its checks support, and how much useful, supported output it produces under a budget of checks.

## The task

A task is a record (a vulnerability advisory, a trial registration, a drug recall, or a company's financial facts), a request about it, three conclusions ordered by strength (`C1` weakest to `C3` strongest), a set of checks (yes-or-no conditions on fields of the record, each with a registered way of determining it), and, for each conclusion, its minimal sufficient routes: the sets of checks that suffice for it. A route holds when every literal in it holds; `E3` requires check E3 true, `!E3` requires it false (negated literals occur only on the text variant). A conclusion is supported by the record when some route of it holds on the record's reference values.

The strength order is a chain, and support is monotone: every route of a stronger conclusion contains a route of each weaker one (order coherence), so a record that supports `C3` supports `C2` and `C1`.

## Reference labels

The reference value of every check is computed by running its predicate on the stored field (the generator drops any task whose stored value is not reproduced by executing the check). On the text variant, the reference value of a text check comes from a structured field of the same record that the agent cannot read (for example the registration's minimum age for "enrollment is restricted to adults"). The reference labels never read any agent's output.

## What an agent sees

An agent given the rule sees the request, the scope, the conclusions and their order, each check's tool, parameters, and predicate, and the routes. An agent that must learn which evidence suffices sees the conclusions and checks but not the routes. An agent that must construct the standard sees only the request, scope, and tools. No agent sees reference values. `RecordEnv.agent_view()` returns the first view; drop `routes` for the second.

## What an agent does

Three evidence actions: `inspect_record(record_id, field_path)` returns a raw field value; on text tasks, `read_text` returns a free-text field and `attest_atom(atom_id, value, quote)` records the agent's own judgment of a text check, accepted only when the text was read and the quote occurs in it verbatim. The agent ends by stating zero or more conclusions.

## How it is scored

See docs/evaluation_protocol.md. The scorer replays the recorded actions, rebuilds the ledger of settled checks, and computes false authorization, premature conclusions, supported utility, evidence value, emission rate, evidence recall, tool calls, and resolver error. Truth under the intended standard (reference values), what the agent's actions established (the replayed ledger), and what the agent stated are kept separate; authorization under a supplied or learned program, the mechanism an enforcement method uses, is not a scoring input.

## Splits and variants

The primary corpus (938 tasks) is split by template family: 60 families are held out (balanced and natural splits), 48 are development, 12 are validation. The derived variants (locator, onebranch, text) are built for specific experiments from the frozen primary corpus or from new records and are not part of the 938. The fdaaa configuration applies a hand-compiled regulation to other records. See docs/data_schema.md for the fields and docs/benchmark_generation.md for how they were made.
