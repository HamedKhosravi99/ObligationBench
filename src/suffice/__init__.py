"""SUFFICE: a benchmark of evidence-based review tasks for LLM agents.

Load tasks, let an agent act on them through ``RecordEnv``, and score its stated
conclusions against the intended standard with executable predicates, with no
LLM judge. See ``suffice --help`` and the docs/ directory.
"""
from __future__ import annotations

__version__ = "1.0.0"

from .env import RecordEnv  # noqa: E402,F401
from .export import agent_visible, row_to_task, task_to_row  # noqa: E402,F401
from .scoring import (PredictionError, established, score, score_task,  # noqa: E402,F401
                      summarize, supported)
from .tasks import load_tasks  # noqa: E402,F401
from .validate import validate_corpus, validate_tasks  # noqa: E402,F401

__all__ = ["RecordEnv", "PredictionError", "agent_visible", "established", "load_tasks", "row_to_task",
           "score", "score_task", "summarize", "supported", "task_to_row", "validate_corpus", "validate_tasks",
           "__version__"]
