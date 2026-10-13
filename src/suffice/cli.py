"""Command-line interface: ``suffice <command>`` or ``python -m suffice``.

evaluate   score a predictions file against a task file or dataset split
validate   check a corpus (counts, structure, reference labels)
inspect    print a task as the agent sees it, and separately its reference labels
export     convert native task files to dataset rows (.jsonl)
generate   run the benchmark generator (see docs/benchmark_generation.md)
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from typing import List, Optional

from . import __version__
from .env import RecordEnv
from .export import task_to_row
from .scoring import PredictionError, format_result, score, supported
from .tasks import load_tasks
from .validate import validate_corpus, validate_tasks

log = logging.getLogger("suffice")


def _cmd_evaluate(a: argparse.Namespace) -> int:
    tasks = load_tasks(a.tasks)
    with open(a.predictions, encoding="utf-8") as fh:
        preds = [json.loads(l) for l in fh if l.strip()]
    try:
        result = score(tasks, preds, by=a.by, missing=a.missing, strict=a.strict)
    except PredictionError as exc:
        log.error("invalid predictions: %s", exc)
        return 2
    print(format_result(result))
    if a.output:
        out = dict(result)
        if not a.rows:
            out.pop("rows", None)
        with open(a.output, "w", encoding="utf-8") as fh:
            json.dump(out, fh, indent=2, sort_keys=True)
        log.info("wrote %s", a.output)
    return 0


def _cmd_validate(a: argparse.Namespace) -> int:
    by_split = {}
    for spec in a.split:
        name, _, path = spec.partition("=")
        if not path:
            log.error("--split takes NAME=PATH, got %r", spec)
            return 2
        by_split[name] = load_tasks(path)
    fdaaa = load_tasks(a.fdaaa) if a.fdaaa else None
    problems = 0
    for name, tasks in list(by_split.items()) + ([("fdaaa", fdaaa)] if fdaaa else []):
        bad = validate_tasks(tasks.values(), schema=not a.no_schema)
        for tid, probs in sorted(bad.items()):
            for p in probs:
                print("%s %s: %s" % (name, tid, p))
        problems += len(bad)
        print("%-18s %5d tasks, %d with problems" % (name, len(tasks), len(bad)))
    corpus = validate_corpus(by_split, fdaaa) if by_split else []
    for p in corpus:
        print("corpus: %s" % p)
    problems += len(corpus)
    print("OK" if problems == 0 else "%d problem(s)" % problems)
    return 0 if problems == 0 else 1


def _cmd_inspect(a: argparse.Namespace) -> int:
    tasks = load_tasks(a.tasks)
    task = tasks.get(a.task_id)
    if task is None:
        log.error("no task %s in %s", a.task_id, a.tasks)
        return 2
    view = RecordEnv(task).agent_view()
    print("# agent view")
    print(json.dumps(view, indent=1, sort_keys=True))
    if a.labels:
        print("# evaluator-only labels (never show these to an agent)")
        print(json.dumps({"reference_atom_values": {x["id"]: x["gold_value"] for x in task["atoms"]},
                          "supported_conclusions": sorted(c for c, ok in supported(task).items() if ok)},
                         indent=1, sort_keys=True))
    return 0


def _cmd_export(a: argparse.Namespace) -> int:
    tasks = load_tasks(a.tasks)
    with open(a.output, "w", encoding="utf-8") as fh:
        for tid in sorted(tasks):
            fh.write(json.dumps(task_to_row(tasks[tid], a.split), sort_keys=True) + "\n")
    log.info("wrote %d rows to %s", len(tasks), a.output)
    return 0


def _cmd_generate(a: argparse.Namespace) -> int:
    from .generation import run_generator
    return run_generator(a.generator, a.args)


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(prog="suffice", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--version", action="version", version="suffice %s" % __version__)
    ap.add_argument("-v", "--verbose", action="store_true")
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("evaluate", help="score a predictions file")
    s.add_argument("--tasks", required=True, help="a .jsonl dataset file, a task .json file, or a directory of task files")
    s.add_argument("--predictions", required=True, help="predictions .jsonl (see docs/evaluation_protocol.md)")
    s.add_argument("--by", choices=["domain", "family", "topology"], default=None)
    s.add_argument("--missing", choices=["abstain", "error", "skip"], default="abstain",
                   help="a task without a prediction counts as an abstention, is an error, or is left out (skip)")
    s.add_argument("--strict", action="store_true",
                   help="treat a stated conclusion id the task does not define as an error (default: it scores as false authorization)")
    s.add_argument("--output", default=None, help="write the result as JSON")
    s.add_argument("--rows", action="store_true", help="include the per-task rows in --output")
    s.set_defaults(func=_cmd_evaluate)

    s = sub.add_parser("validate", help="check a corpus")
    s.add_argument("--split", action="append", default=[], metavar="NAME=PATH",
                   help="native split name and its file or directory, repeatable "
                        "(heldout_balanced, heldout_natural, dev, val, heldout_locator, heldout_onebranch, heldout_text)")
    s.add_argument("--fdaaa", default=None, help="the FDAAA task file or directory")
    s.add_argument("--no-schema", action="store_true", help="skip the structural schema validation")
    s.set_defaults(func=_cmd_validate)

    s = sub.add_parser("inspect", help="print one task")
    s.add_argument("--tasks", required=True)
    s.add_argument("task_id")
    s.add_argument("--labels", action="store_true", help="also print the evaluator-only labels")
    s.set_defaults(func=_cmd_inspect)

    s = sub.add_parser("export", help="native task files -> dataset rows")
    s.add_argument("--tasks", required=True)
    s.add_argument("--split", required=True, help="native split name of these tasks")
    s.add_argument("--output", required=True, help="output .jsonl")
    s.set_defaults(func=_cmd_export)

    s = sub.add_parser("generate", help="run the generator (record tasks, text tasks, harvest)")
    s.add_argument("generator", choices=["records", "text", "harvest"])
    s.add_argument("args", nargs=argparse.REMAINDER, help="arguments passed to the generator script")
    s.set_defaults(func=_cmd_generate)

    a = ap.parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if a.verbose else logging.INFO, format="%(levelname)s %(message)s")
    return a.func(a)


if __name__ == "__main__":
    sys.exit(main())
