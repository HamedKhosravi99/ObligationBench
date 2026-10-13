#!/usr/bin/env python3
"""Scan a directory (or archives) of the SUFFICE release for identifying strings and credentials.

    python scripts/check_anonymity.py PATH [PATH ...] [--allow REGEX ...]

Flags local paths (/Users/..., /home/..., /storage/home), e-mail addresses, cluster
and institution names, user accounts, and credential-like tokens, in every text file
and inside .zip and .tar.gz archives. Exits nonzero if anything is found. Inside
task files (.jsonl) only the author, institution, cluster, account, and credential
patterns apply, because public records themselves contain paths and e-mail addresses
(security advisories quote both); those are the records' content, not ours."""
from __future__ import annotations

import argparse
import io
import os
import re
import sys
import tarfile
import zipfile

PATTERNS = [
    ("local path", r"/Users/[A-Za-z0-9_]+/"), ("local path", r"/home/[A-Za-z0-9_]+/"), ("cluster path", r"/storage/home/"),
    ("e-mail", r"[A-Za-z0-9._%+-]+@(?!example\.)[A-Za-z0-9.-]+\.(?:edu|com|org|net|gov)"),
    ("token", r"hf_[A-Za-z0-9]{20,}"), ("token", r"ghp_[A-Za-z0-9]{20,}"), ("token", r"github_pat_[A-Za-z0-9_]{20,}"),
    ("token", r"sk-[A-Za-z0-9]{20,}"), ("token", r"AKIA[0-9A-Z]{16}"), ("key", r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
]
# The authors' names, accounts, institution, and cluster names are not written here (this
# file is part of the release). They are read, one regular expression per line, from the
# file named by --private-patterns or the ANONYMITY_PRIVATE_PATTERNS environment variable,
# which is kept outside the repository, and are applied everywhere, record text included.
TEXT_EXT = (".py", ".md", ".txt", ".toml", ".yaml", ".yml", ".cff", ".jsonl", ".json", ".cfg", ".ini", ".sh", ".tex", ".bib", ".csv")


RECORD_LABELS = {"private", "token", "key"}   # what still counts inside record data


def scan_text(name: str, text: str, allow, record_data: bool = False) -> list:
    hits = []
    for label, pat in PATTERNS:
        if record_data and label not in RECORD_LABELS:
            continue   # a public record's own text may contain paths and e-mail addresses (advisory texts do)
        for m in re.finditer(pat, text, flags=re.I):
            s = m.group(0)
            if any(re.search(al, s, flags=re.I) for al in allow):
                continue
            hits.append((name, label, s[:60]))
            if len(hits) > 50:
                return hits
    return hits


def scan_path(path: str, allow) -> list:
    hits = []
    if os.path.isdir(path):
        for d, _, fs in os.walk(path):
            if any(x in d for x in (".git", "__pycache__", ".pytest_cache")):
                continue
            for f in fs:
                p = os.path.join(d, f)
                if f == os.path.basename(__file__):
                    continue   # this file lists the generic patterns it searches for
                if f.endswith(TEXT_EXT):
                    with open(p, encoding="utf-8", errors="replace") as fh:
                        hits += scan_text(p, fh.read(), allow, record_data=f.endswith(".jsonl"))
                elif f.endswith((".zip", ".tar.gz", ".tgz")):
                    hits += scan_path(p, allow)
    elif path.endswith(".zip"):
        with zipfile.ZipFile(path) as z:
            for n in z.namelist():
                if n.endswith(TEXT_EXT) and os.path.basename(n) != os.path.basename(__file__):
                    hits += scan_text(path + "::" + n, z.read(n).decode("utf-8", "replace"), allow, record_data=n.endswith(".jsonl"))
    elif path.endswith((".tar.gz", ".tgz")):
        with tarfile.open(path) as t:
            for m in t.getmembers():
                if m.isfile() and m.name.endswith(TEXT_EXT):
                    hits += scan_text(path + "::" + m.name, t.extractfile(m).read().decode("utf-8", "replace"), allow, record_data=m.name.endswith(".jsonl"))
    else:
        with open(path, encoding="utf-8", errors="replace") as fh:
            hits += scan_text(path, fh.read(), allow, record_data=path.endswith(".jsonl"))
    return hits


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("paths", nargs="+")
    ap.add_argument("--allow", action="append", default=[], help="regex for matches to ignore (repeatable)")
    ap.add_argument("--private-patterns", default=os.environ.get("ANONYMITY_PRIVATE_PATTERNS"),
                    help="file with one regex per line naming the authors, accounts, institution, cluster (kept outside the repository)")
    a = ap.parse_args(argv)
    if a.private_patterns:
        with open(a.private_patterns, encoding="utf-8") as fh:
            PATTERNS.extend(("private", line.strip()) for line in fh if line.strip() and not line.startswith("#"))
    else:
        print("note: no private patterns file given (--private-patterns); only generic patterns apply", file=sys.stderr)
    hits = []
    for p in a.paths:
        hits += scan_path(p, a.allow)
    if hits:
        print("%d identifying or credential-like string(s):" % len(hits))
        for name, label, s in hits[:60]:
            print("  %-12s %s  in %s" % (label, s, name))
        return 1
    print("clean: no identifying string or credential found in", ", ".join(a.paths))
    return 0


if __name__ == "__main__":
    sys.exit(main())
