#!/usr/bin/env python3
# Copyright Advanced Micro Devices, Inc.
# SPDX-License-Identifier: MIT

"""Validate request syntax and format PR text from the original commits."""

import os
from pathlib import Path
import re
import subprocess
import sys


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], text=True, encoding="utf-8").strip()


def generate_pr_body(repository: str, release: str, commits: list[str]) -> str:
    lines = [f"Cherry-picks into `{release}`.", ""]
    if reason := os.environ.get("RELEASE_REASON", "").strip():
        lines.extend([reason, ""])
    if ticket := os.environ.get("JIRA_ID", "").strip():
        lines.extend([f"JIRA ID: {ticket}", ""])
    for commit in commits:
        original_message = git("show", "-s", "--format=%B", commit)
        lines.extend(
            [
                f"### {git('show', '-s', '--format=%s', commit)}",
                f"Source: https://github.com/ROCm/{repository}/commit/{commit}",
                "",
                "<details><summary>Original commit message</summary>",
                "",
                *[f"> {line}" for line in original_message.splitlines()],
                "",
                "</details>",
                "",
            ]
        )
    lines.extend(
        [
            "Release-branch validation: review the checks on this PR.",
            "",
            f"Requested by @{os.environ['GITHUB_ACTOR']} via {os.environ['WORKFLOW_RUN_URL']}.",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    release = os.environ["RELEASE_BRANCH"]
    if not re.fullmatch(
        r"release/(?:therock-\d+\.\d+|bkc/therock-\d+\.\d+-\d{8})", release
    ):
        raise ValueError("Expected a regular or BKC release branch")
    ticket = os.environ.get("JIRA_ID", "").strip()
    if ticket and not re.fullmatch(r"[A-Z][A-Z0-9_]*-[1-9]\d*", ticket):
        raise ValueError("Invalid JIRA key")
    if not ticket and not release.startswith("release/bkc/"):
        raise ValueError("A JIRA key is required for regular releases")
    specs = os.environ["COMMITS"].replace(",", " ").split()
    if not specs or any(not re.fullmatch(r"[0-9a-fA-F]{7,40}", spec) for spec in specs):
        raise ValueError("Supply one or more commit SHAs (7–40 hex characters)")
    commits = list(
        dict.fromkeys(
            git("rev-parse", "--verify", f"{spec}^{{commit}}") for spec in specs
        )
    )
    title = (
        git("show", "-s", "--format=%s", commits[0])
        if len(commits) == 1
        else f"Cherry-pick {len(commits)} commits"
    )
    output = Path(sys.argv[1])
    (output / "commits.txt").write_text(
        "\n".join(commits) + "\n", encoding="utf-8", newline="\n"
    )
    (output / "title.txt").write_text(
        f"[{release.removeprefix('release/')}] {title}", encoding="utf-8", newline="\n"
    )
    (output / "body.md").write_text(
        generate_pr_body(os.environ["REPOSITORY"], release, commits),
        encoding="utf-8",
        newline="\n",
    )


if __name__ == "__main__":
    main()
