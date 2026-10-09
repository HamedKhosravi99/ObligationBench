#!/usr/bin/env python3
"""Upload the prepared dataset directory to a PRIVATE Hugging Face dataset repository.

    python scripts/publish_hf_private.py --dataset-dir dist/obligationbench-dataset \
        --repo <namespace>/ObligationBench --confirm

Without --confirm the script only checks the inputs and prints what it would do.
It never makes a repository public and never changes an existing repository's
visibility: it creates the repository with private=True if it does not exist,
refuses to continue if an existing repository is public, uploads the directory as
one commit, then verifies the visibility, the uploaded files and task counts, that
an authenticated load works, and that an unauthenticated request is refused. The
token comes from `hf auth login` or the HF_TOKEN environment variable and is never
printed."""
from __future__ import annotations

import argparse
import json
import os
import sys


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dataset-dir", required=True)
    ap.add_argument("--repo", required=True, help="<namespace>/ObligationBench")
    ap.add_argument("--confirm", action="store_true", help="actually upload; otherwise dry run")
    a = ap.parse_args(argv)

    d = a.dataset_dir
    required = ["README.md", "manifest.json", "LICENSE", "NOTICE.md"] + ["data/%s.jsonl" % c for c in
                ("balanced", "natural", "dev", "val", "locator", "onebranch", "text", "fdaaa")]
    missing = [f for f in required if not os.path.exists(os.path.join(d, f))]
    if missing:
        print("missing from the dataset directory:", missing)
        return 2
    man = json.load(open(os.path.join(d, "manifest.json"), encoding="utf-8"))
    counts = {c: info["tasks"] for c, info in man["configs"].items()}
    print("dataset directory ok; configurations:", counts)
    if not a.confirm:
        print("dry run: add --confirm to create the PRIVATE repository %s and upload" % a.repo)
        return 0

    try:
        from huggingface_hub import HfApi
        from huggingface_hub.utils import HfHubHTTPError
    except ImportError:
        print("huggingface_hub is not installed: pip install huggingface_hub")
        return 2
    api = HfApi()
    try:
        who = api.whoami()
    except Exception as exc:  # noqa: BLE001
        print("not logged in (run `hf auth login` or set HF_TOKEN):", type(exc).__name__)
        return 2
    print("authenticated as", who.get("name"))

    # create private, or verify an existing repository is private; never change visibility
    try:
        info = api.repo_info(a.repo, repo_type="dataset")
        if not info.private:
            print("repository %s exists and is PUBLIC; refusing to upload to it" % a.repo)
            return 3
        print("repository exists and is private")
    except HfHubHTTPError:
        api.create_repo(a.repo, repo_type="dataset", private=True, exist_ok=False)
        print("created PRIVATE repository", a.repo)

    commit = api.upload_folder(folder_path=d, repo_id=a.repo, repo_type="dataset",
                               commit_message="ObligationBench %s" % man.get("version", ""),
                               ignore_patterns=["__pycache__/*", "*.pyc", ".DS_Store"])
    rev = getattr(commit, "oid", None) or str(commit)
    print("uploaded; commit", rev)

    # verify
    info = api.repo_info(a.repo, repo_type="dataset")
    if not info.private:
        print("ERROR: repository is not private after upload")
        return 3
    files = set(api.list_repo_files(a.repo, repo_type="dataset"))
    absent = [f for f in required if f not in files]
    if absent:
        print("ERROR: files missing on the hub:", absent)
        return 3
    try:
        from datasets import load_dataset
        n = len(load_dataset(a.repo, "val", split="test"))
        print("authenticated load of configuration val: %d rows (expected %d)" % (n, counts["val"]))
        if n != counts["val"]:
            return 3
    except ImportError:
        print("datasets not installed; skipped the authenticated load check")
    # unauthenticated access must fail
    import urllib.request
    try:
        urllib.request.urlopen("https://huggingface.co/api/datasets/%s" % a.repo, timeout=20)
        print("ERROR: the repository metadata is readable without a token")
        return 3
    except Exception:  # noqa: BLE001
        print("unauthenticated access refused, as required")
    print("done: %s is private at revision %s" % (a.repo, rev))
    return 0


if __name__ == "__main__":
    sys.exit(main())
