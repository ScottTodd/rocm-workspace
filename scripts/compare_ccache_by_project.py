#!/usr/bin/env python
"""Compare ccache hit rates per subproject across two log files.

Usage:
    python scripts/compare_ccache_by_project.py LINUX_LOG WINDOWS_LOG
"""

import re
import sys
from collections import Counter


def parse_by_project(log_file: str) -> dict:
    """Parse ccache log and return per-project hit/miss counts."""
    pid_data = {}

    with open(log_file, "r", errors="replace") as f:
        for line in f:
            m = re.match(r"\[.*? (\d+)\s*\]", line)
            if not m:
                continue
            pid = m.group(1)
            if pid not in pid_data:
                pid_data[pid] = {}

            if "Source file:" in line:
                mm = re.search(r"Source file: (.+)", line)
                if mm:
                    pid_data[pid]["source"] = mm.group(1).strip()
            elif "Compiler:" in line and "Compiler type" not in line:
                mm = re.search(r"Compiler: (.+)", line)
                if mm:
                    pid_data[pid]["compiler"] = mm.group(1).strip()
            elif "Result: direct_cache_hit" in line:
                pid_data[pid]["result"] = "hit"
            elif "Result: cache_miss" in line:
                if pid_data[pid].get("result") != "hit":
                    pid_data[pid]["result"] = "miss"

    # Aggregate by project
    projects = Counter()
    project_hits = Counter()

    for pid, d in pid_data.items():
        src = d.get("source", "")
        comp = d.get("compiler", "")
        result = d.get("result", "")
        if not src or not result:
            continue
        if "clang" not in comp:
            continue  # Only count clang compilations
        if "TryCompile" in src or "CMakeScratch" in src or "cmTC_" in src:
            continue  # Skip CMake probes

        project = extract_project(src)
        projects[project] += 1
        if result == "hit":
            project_hits[project] += 1

    return {p: (project_hits[p], projects[p]) for p in projects}


def extract_project(src: str) -> str:
    """Extract project name from source path."""
    src = src.replace("\\", "/")

    # Source tree: .../projects/{name}/...
    m = re.search(r"/projects/([^/]+)/", src)
    if m:
        return m.group(1).lower()

    # Build tree: .../math-libs/{group}/{name}/... or .../math-libs/{name}/...
    m = re.search(r"(?:math-libs|ml-libs)/(?:BLAS/)?([^/]+)/", src)
    if m:
        return m.group(1).lower()

    # Third-party
    m = re.search(r"third-party/([^/]+)/", src)
    if m:
        return "3p-" + m.group(1).lower()

    return "?"


def main():
    if len(sys.argv) != 3:
        print(f"Usage: {sys.argv[0]} LINUX_LOG WINDOWS_LOG")
        sys.exit(1)

    linux_log, windows_log = sys.argv[1], sys.argv[2]

    print("Parsing Linux log...", file=sys.stderr)
    linux = parse_by_project(linux_log)
    print("Parsing Windows log...", file=sys.stderr)
    windows = parse_by_project(windows_log)

    all_projects = sorted(set(linux.keys()) | set(windows.keys()))

    linux_total_hits = sum(h for h, t in linux.values())
    linux_total = sum(t for h, t in linux.values())
    win_total_hits = sum(h for h, t in windows.values())
    win_total = sum(t for h, t in windows.values())

    print(f"\n{'Project':<30s} {'Linux':>18s} {'Windows':>18s} {'Gap':>8s}")
    print(f"{'':<30s} {'hits/total   rate':>18s} {'hits/total   rate':>18s}")
    print("-" * 78)

    for proj in all_projects:
        lh, lt = linux.get(proj, (0, 0))
        wh, wt = windows.get(proj, (0, 0))
        lr = f"{100*lh/lt:.0f}%" if lt > 0 else "-"
        wr = f"{100*wh/wt:.0f}%" if wt > 0 else "-"
        gap = ""
        if lt > 0 and wt > 0:
            diff = (wh / wt - lh / lt) * 100
            gap = f"{diff:+.0f}%"
        ls = f"{lh}/{lt} {lr:>5s}" if lt > 0 else f"{'—':>12s}"
        ws = f"{wh}/{wt} {wr:>5s}" if wt > 0 else f"{'—':>12s}"
        print(f"  {proj:<28s} {ls:>18s} {ws:>18s} {gap:>8s}")

    print("-" * 78)
    lr = f"{100*linux_total_hits/linux_total:.1f}%" if linux_total > 0 else "-"
    wr = f"{100*win_total_hits/win_total:.1f}%" if win_total > 0 else "-"
    print(
        f"  {'TOTAL':<28s} {linux_total_hits}/{linux_total} {lr:>5s}"
        f"       {win_total_hits}/{win_total} {wr:>5s}"
    )


if __name__ == "__main__":
    main()
