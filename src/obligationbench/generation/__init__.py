"""The ObligationBench generators, vendored from the PRIME code (see each file's header
and docs/benchmark_generation.md).

``run_generator(name, args)`` runs one of them with the given command-line arguments:
``records`` (the primary corpus; with ``--locator-per-domain`` or
``--one-branch-per-domain`` the derived variants), ``text`` (the text-evidence split),
``harvest`` (live retrieval of source records; not reproducible). All read and write
under the directory named by OBLIGATIONBENCH_BENCH_DIR (default ./bench): harvest/
holds the source records, instances_v2/ the generated tasks.
"""
from __future__ import annotations

import sys
from typing import List


def run_generator(name: str, args: List[str]) -> int:
    if name == "records":
        from . import record_tasks as mod
    elif name == "text":
        from . import text_tasks as mod
    elif name == "harvest":
        from . import harvest as mod
    else:
        raise ValueError("unknown generator %r" % name)
    old = sys.argv
    sys.argv = [name] + list(args)
    try:
        return int(mod.main() or 0)
    finally:
        sys.argv = old
