"""Publication hygiene: the dataset card's metadata, no credentials, no identifying strings."""
import os
import re

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

TOKEN_PATTERNS = [r"hf_[A-Za-z0-9]{20,}", r"ghp_[A-Za-z0-9]{20,}", r"github_pat_[A-Za-z0-9_]{20,}",
                  r"sk-[A-Za-z0-9]{20,}", r"AKIA[0-9A-Z]{16}", r"-----BEGIN [A-Z ]*PRIVATE KEY-----"]
IDENTITY_PATTERNS = [r"/Users/[a-z]", r"/home/[a-z]", r"/storage/home", r"[a-z0-9._-]+@(?!example\.)[a-z0-9.-]+\.(edu|com|org)"]
_private = os.environ.get("ANONYMITY_PRIVATE_PATTERNS")
if _private and os.path.exists(_private):
    IDENTITY_PATTERNS += [l.strip() for l in open(_private, encoding="utf-8") if l.strip() and not l.startswith("#")]
TEXT_EXT = (".py", ".md", ".txt", ".toml", ".yaml", ".yml", ".cff", ".jsonl", ".json", ".cfg", ".ini")


def _files(root):
    for d, _, fs in os.walk(root):
        if any(x in d for x in (".git", "__pycache__", ".pytest_cache", "dist")):
            continue
        for f in fs:
            if f.endswith(TEXT_EXT):
                yield os.path.join(d, f)


def test_dataset_card_metadata():
    card = os.path.join(ROOT, "docs", "dataset_card.md")
    if not os.path.exists(card):
        pytest.skip("no dataset card")
    text = open(card, encoding="utf-8").read()
    assert text.startswith("---\n")
    front = text.split("---\n")[1]
    for key in ("license:", "pretty_name:", "configs:", "task_categories:", "language:"):
        assert key in front, key
    for cfg in ("balanced", "natural", "dev", "val", "locator", "onebranch", "text", "fdaaa"):
        assert "config_name: %s" % cfg in front, cfg
        assert "data/%s.jsonl" % cfg in front, cfg


def test_no_embedded_tokens():
    for f in _files(ROOT):
        text = open(f, encoding="utf-8", errors="replace").read()
        for pat in TOKEN_PATTERNS:
            assert not re.search(pat, text), (f, pat)


def test_no_identifying_strings_in_release_text():
    """Code and docs must not name the authors, their machines, accounts, or clusters.
    Data files are scanned by scripts/check_anonymity.py, which exempts the public
    records' own text (advisories quote paths and e-mail addresses)."""
    for f in _files(ROOT):
        if f.endswith(".jsonl") or os.path.basename(f) in ("test_publication.py", "check_anonymity.py"):
            continue  # data files are checked by scripts/check_anonymity.py; the two files define the patterns
        text = open(f, encoding="utf-8", errors="replace").read()
        for pat in IDENTITY_PATTERNS:
            assert not re.search(pat, text, flags=re.I), (f, pat)


def test_no_publishing_without_a_flag():
    """The upload script must require explicit confirmation and never make a repository public."""
    p = os.path.join(ROOT, "scripts", "publish_hf_private.py")
    if not os.path.exists(p):
        pytest.skip("no publish script")
    text = open(p, encoding="utf-8").read()
    assert "private=True" in text
    assert "--confirm" in text
    assert "update_repo_visibility" not in text and "private=False" not in text


def test_env_example_has_no_values():
    p = os.path.join(ROOT, ".env.example")
    if os.path.exists(p):
        for line in open(p, encoding="utf-8"):
            if "=" in line and not line.startswith("#"):
                assert line.split("=", 1)[1].strip() in ("", '""'), line
