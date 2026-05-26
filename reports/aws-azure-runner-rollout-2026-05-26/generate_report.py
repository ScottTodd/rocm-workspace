#!/usr/bin/env python3
"""Generate the AWS/Azure runner rollout report artifacts.

Inputs are the public GitHub Actions metadata snapshots cached under
D:/scratch/codex from the 2026-05-26 investigation.
"""

from __future__ import annotations

import csv
import json
import shutil
import statistics
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPORT_DIR = Path(__file__).resolve().parent
RUNNER_CACHE_DIR = Path("D:/scratch/codex/therock_runner_history_cache")
CCACHE_CACHE_DIR = Path("D:/scratch/codex/therock_ccache_sample_cache")

RUNNER_HISTORY_CSV = RUNNER_CACHE_DIR / "runner_history.csv"
RUNS_PAGE_JSON = RUNNER_CACHE_DIR / "runs_page_1.json"
SCATTER_SVG = RUNNER_CACHE_DIR / "runner_history_scatter.svg"
SCATTER_HTML = RUNNER_CACHE_DIR / "runner_history_scatter.html"
CCACHE_JSON = CCACHE_CACHE_DIR / "ccache_sample.json"

AWS = "aws-linux-scale-rocm-prod"
AZURE = "azure-linux-scale-rocm"
NO_LINUX = "no-linux-build-jobs"
RUNNER_LABELS = {AWS: "AWS", AZURE: "Azure", NO_LINUX: "No Linux build jobs"}


def parse_utc(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def format_pct(value: float) -> str:
    return f"{value * 100:.1f}%"


def format_float(value: float | None, digits: int = 2) -> str:
    return "n/a" if value is None else f"{value:.{digits}f}"


def median(values: list[float]) -> float | None:
    return statistics.median(values) if values else None


def mean(values: list[float]) -> float | None:
    return statistics.mean(values) if values else None


def load_commits() -> dict[int, str]:
    if not RUNS_PAGE_JSON.exists():
        return {}
    data = json.loads(RUNS_PAGE_JSON.read_text(encoding="utf-8"))
    return {
        int(run["id"]): run.get("head_sha", "")
        for run in data.get("workflow_runs", [])
        if "id" in run
    }


def load_rows() -> list[dict[str, Any]]:
    commits = load_commits()
    rows: list[dict[str, Any]] = []
    with RUNNER_HISTORY_CSV.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            seconds_sum = int(row["linux_build_job_seconds_sum"])
            seconds_max = int(row["linux_build_job_seconds_max"] or 0)
            run_id = int(row["run_id"])
            enriched = {
                **row,
                "run_id": run_id,
                "run_number": int(row["run_number"]),
                "created_at": row["created_at"],
                "created_at_epoch": int(parse_utc(row["created_at"]).timestamp()),
                "head_sha": commits.get(run_id, ""),
                "head_sha_short": commits.get(run_id, "")[:7],
                "linux_build_job_count": int(row["linux_build_job_count"]),
                "linux_build_job_seconds_sum": seconds_sum,
                "linux_build_job_hours_sum": round(seconds_sum / 3600.0, 3),
                "linux_build_job_seconds_max": seconds_max,
                "linux_build_job_minutes_max": round(seconds_max / 60.0, 2) if seconds_max else "",
                "is_build_bearing_runner": row["runner"] in {AWS, AZURE} and int(row["linux_build_job_count"]) > 0,
                "is_completed": row["status"] == "completed",
            }
            rows.append(enriched)
    rows.sort(key=lambda row: (row["created_at"], row["run_number"]))
    return rows


def summarize_perf(rows: list[dict[str, Any]], min_hours: float = 0.0) -> dict[str, dict[str, Any]]:
    by_runner: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if not row["is_build_bearing_runner"] or not row["is_completed"]:
            continue
        if row["linux_build_job_hours_sum"] < min_hours:
            continue
        by_runner[row["runner"]].append(row)

    summary: dict[str, dict[str, Any]] = {}
    for runner in [AWS, AZURE]:
        runner_rows = by_runner[runner]
        hours = [float(row["linux_build_job_hours_sum"]) for row in runner_rows]
        longest_minutes = [
            float(row["linux_build_job_minutes_max"])
            for row in runner_rows
            if row["linux_build_job_minutes_max"] != ""
        ]
        summary[runner] = {
            "label": RUNNER_LABELS[runner],
            "n": len(runner_rows),
            "seconds_sum_mean_hours": mean(hours),
            "seconds_sum_median_hours": median(hours),
            "seconds_sum_min_hours": min(hours) if hours else None,
            "seconds_sum_max_hours": max(hours) if hours else None,
            "longest_job_mean_minutes": mean(longest_minutes),
            "longest_job_median_minutes": median(longest_minutes),
        }
    return summary


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def write_ccache_artifacts() -> list[dict[str, Any]]:
    if not CCACHE_JSON.exists():
        return []
    ccache_data = json.loads(CCACHE_JSON.read_text(encoding="utf-8"))
    shutil.copyfile(CCACHE_JSON, REPORT_DIR / "ccache_sample.json")

    rows = []
    for run_id, data in sorted(ccache_data.items()):
        rows.append(
            {
                "run_id": run_id,
                "runner": data["runner"],
                "runner_label": RUNNER_LABELS.get(data["runner"], data["runner"]),
                "hits": data["hits"],
                "misses": data["misses"],
                "hit_rate": data["hit_rate"],
                "hit_rate_percent": round(data["hit_rate"] * 100, 2),
            }
        )
    write_csv(
        REPORT_DIR / "ccache_sample_summary.csv",
        rows,
        ["run_id", "runner", "runner_label", "hits", "misses", "hit_rate", "hit_rate_percent"],
    )
    return rows


def write_readme(rows: list[dict[str, Any]], ccache_rows: list[dict[str, Any]], summary: dict[str, Any]) -> None:
    start = rows[0]["created_at"]
    end = rows[-1]["created_at"]
    runner_counts = Counter(row["runner"] for row in rows)
    build_rows = [row for row in rows if row["is_build_bearing_runner"]]
    job_counts = Counter()
    for row in build_rows:
        job_counts[row["runner"]] += row["linux_build_job_count"]

    perf_all = summary["performance_all_completed"]
    perf_substantial = summary["performance_completed_ge_6h"]

    aws_all = perf_all[AWS]
    azure_all = perf_all[AZURE]
    aws_sub = perf_substantial[AWS]
    azure_sub = perf_substantial[AZURE]

    lines = [
        "# AWS/Azure Runner Rollout Snapshot",
        "",
        "This folder captures the data used to evaluate the TheRock `multi_arch_ci.yml`",
        "main-branch runner split after the AWS runner weight was raised from 10% to 20%",
        "and before PR #5451 proposed raising it to 50%.",
        "",
        "## Scope",
        "",
        f"- Workflow: `ROCm/TheRock` `multi_arch_ci.yml`, workflow id `210763103`.",
        "- Workflow history: https://github.com/ROCm/TheRock/actions/workflows/multi_arch_ci.yml?query=branch%3Amain",
        "- PR #5318: https://github.com/ROCm/TheRock/pull/5318",
        "- PR #5451: https://github.com/ROCm/TheRock/pull/5451",
        f"- Window: `{start}` through `{end}` UTC.",
        "- Start event: PR #5318 merged on 2026-05-18 at 17:51:16 UTC.",
        "- End event: PR #5451 was opened on 2026-05-26 at 21:42:34 UTC.",
        "- Runner classification source: GitHub Actions build-job metadata labels.",
        "- Build time metric: `linux_build_job_seconds_sum`, the sum of Linux build job durations in each workflow run.",
        "- Wall-time proxy: `linux_build_job_seconds_max`, the longest Linux build job duration in each workflow run.",
        "",
        "## Files",
        "",
        "- `runner_history_enriched.csv`: one row per workflow run in the sampled window.",
        "- `build_time_points.csv`: AWS/Azure build-bearing rows used by the scatterplot.",
        "- `runner_summary.json`: computed counts and performance summaries.",
        "- `runner_history_scatter.svg`: static scatterplot with trend lines.",
        "- `runner_history_scatter.html`: self-contained HTML wrapper with clickable/hoverable SVG points.",
        "- `ccache_sample_summary.csv`: preliminary ccache comparison for one Azure run and one AWS run.",
        "- `ccache_sample.json`: detailed parsed ccache sample by run and stage.",
        "- `generate_report.py`: regenerates the tabular summaries and report from the cached GitHub metadata snapshots.",
        "",
        "## Runner Mix",
        "",
        "| Runner class | Runs | Share of all runs | Linux build jobs | Share of Linux build jobs |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    total_runs = len(rows)
    total_jobs = sum(job_counts.values())
    for runner in [AWS, AZURE, NO_LINUX]:
        run_count = runner_counts[runner]
        jobs = job_counts[runner]
        job_share = format_pct(jobs / total_jobs) if total_jobs and jobs else "n/a"
        lines.append(
            f"| {RUNNER_LABELS[runner]} | {run_count} | {format_pct(run_count / total_runs)} | {jobs} | {job_share} |"
        )

    build_bearing_runs = len(build_rows)
    aws_build_bearing = runner_counts[AWS]
    aws_build_bearing_share = format_pct(aws_build_bearing / build_bearing_runs)
    aws_job_share = format_pct(job_counts[AWS] / total_jobs)
    lines.extend(
        [
            "",
            (
                f"AWS represented `{aws_build_bearing}/{build_bearing_runs}` build-bearing runs "
                f"({aws_build_bearing_share}) and `{job_counts[AWS]}/{total_jobs}` Linux build jobs "
                f"({aws_job_share})."
            ),
            "",
            "## Build Duration",
            "",
            "These summaries use completed AWS/Azure build-bearing workflow runs only.",
            "",
            "| Runner | n | Mean seconds-sum (h) | Median seconds-sum (h) | Median longest job (min) |",
            "| --- | ---: | ---: | ---: | ---: |",
            (
                f"| AWS | {aws_all['n']} | {format_float(aws_all['seconds_sum_mean_hours'])} | "
                f"{format_float(aws_all['seconds_sum_median_hours'])} | "
                f"{format_float(aws_all['longest_job_median_minutes'], 1)} |"
            ),
            (
                f"| Azure | {azure_all['n']} | {format_float(azure_all['seconds_sum_mean_hours'])} | "
                f"{format_float(azure_all['seconds_sum_median_hours'])} | "
                f"{format_float(azure_all['longest_job_median_minutes'], 1)} |"
            ),
            "",
            "A couple of AWS runs failed very early. Filtering to completed runs with at least 6 hours",
            "of summed Linux build time gives this less outlier-sensitive view:",
            "",
            "| Runner | n | Mean seconds-sum (h) | Median seconds-sum (h) | Median longest job (min) |",
            "| --- | ---: | ---: | ---: | ---: |",
            (
                f"| AWS | {aws_sub['n']} | {format_float(aws_sub['seconds_sum_mean_hours'])} | "
                f"{format_float(aws_sub['seconds_sum_median_hours'])} | "
                f"{format_float(aws_sub['longest_job_median_minutes'], 1)} |"
            ),
            (
                f"| Azure | {azure_sub['n']} | {format_float(azure_sub['seconds_sum_mean_hours'])} | "
                f"{format_float(azure_sub['seconds_sum_median_hours'])} | "
                f"{format_float(azure_sub['longest_job_median_minutes'], 1)} |"
            ),
            "",
            "![Scatterplot of Linux build duration by runner](runner_history_scatter.svg)",
            "",
            "## Interpretation",
            "",
            "The observed build-duration data does not yet show a clear 10-20% AWS speedup.",
            "On the summed build-job duration metric, the completed-run medians are effectively",
            "tied. The longest-job proxy gives AWS a modest advantage, but still below the",
            "expected range and based on only 12 completed AWS build-bearing runs.",
            "",
            "This should be treated as an early signal, not a final benchmark. The sample is",
            "small, most build-bearing workflow conclusions in this window are failures, and",
            "run-to-run commit changes can dominate small infrastructure effects.",
            "",
        ]
    )

    if ccache_rows:
        lines.extend(
            [
                "## Ccache Sample",
                "",
                "| Run | Runner | Hits | Misses | Hit rate |",
                "| --- | --- | ---: | ---: | ---: |",
            ]
        )
        for row in ccache_rows:
            lines.append(
                f"| {row['run_id']} | {row['runner_label']} | {row['hits']} | {row['misses']} | {format_pct(row['hit_rate'])} |"
            )
        lines.extend(
            [
                "",
                "This is only a two-run sample, but it is important context: the sampled AWS run",
                "had a much colder ccache profile than the sampled Azure run. If that pattern is",
                "real across more runs, cache behavior could be masking runner hardware or S3",
                "locality gains.",
                "",
            ]
        )

    lines.extend(
        [
            "## Evidence Expectations For Future Rollout PRs",
            "",
            "For future runner migration or weight-change PRs, authors should include:",
            "",
            "- Actual observed runner split by run and by job, with date range and exclusions.",
            "- Build duration distributions by runner, not only averages.",
            "- Outlier handling, especially early-aborted workflow runs.",
            "- Ccache hit-rate distributions by runner and by major build stage.",
            "- Artifact download/upload timing by runner, if S3 locality is part of the argument.",
            "- A plain statement of whether the observed effect matches the expected effect size.",
            "",
            "## Reproduction Notes",
            "",
            "The public GitHub REST API exposed workflow run and job metadata, including runner",
            "labels and job timestamps. GitHub's workflow-jobs documentation says public job logs",
            "can be downloaded without authentication, but during this investigation unauthenticated",
            "`curl` still returned HTTP 403 for the setup-job log endpoint, including with the",
            "`X-GitHub-Api-Version: 2026-03-10` header. Because of that observed behavior, the",
            "first collection pass classified runner type from build-job labels instead of parsing",
            "the setup job's `Configuring CI options` log step.",
            "",
            "An authenticated `gh` session can fetch setup-job logs for this repository. For example,",
            "`gh api --verbose repos/ROCm/TheRock/actions/jobs/77902236703/logs` returns a 302",
            "to a signed log blob, and that log contains the same Linux `build_runs_on` value",
            "shown by the Linux build-job labels. A future parser can use those setup logs directly",
            "when authenticated `gh` credentials are available.",
            "",
        ]
    )

    (REPORT_DIR / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    rows = load_rows()
    ccache_rows = write_ccache_artifacts()

    enriched_fields = [
        "created_at",
        "created_at_epoch",
        "run_number",
        "run_id",
        "head_sha_short",
        "head_sha",
        "runner",
        "linux_build_job_count",
        "linux_build_job_seconds_sum",
        "linux_build_job_hours_sum",
        "linux_build_job_seconds_max",
        "linux_build_job_minutes_max",
        "status",
        "conclusion",
        "is_build_bearing_runner",
        "is_completed",
        "html_url",
        "title",
    ]
    write_csv(REPORT_DIR / "runner_history_enriched.csv", rows, enriched_fields)

    build_points = [row for row in rows if row["is_build_bearing_runner"]]
    write_csv(REPORT_DIR / "build_time_points.csv", build_points, enriched_fields)

    summary = {
        "source_cache_dir": str(RUNNER_CACHE_DIR),
        "ccache_cache_dir": str(CCACHE_CACHE_DIR),
        "window_start_utc": rows[0]["created_at"],
        "window_end_utc": rows[-1]["created_at"],
        "runner_counts": dict(Counter(row["runner"] for row in rows)),
        "linux_build_job_counts": {
            runner: sum(
                row["linux_build_job_count"]
                for row in rows
                if row["runner"] == runner and row["is_build_bearing_runner"]
            )
            for runner in [AWS, AZURE]
        },
        "performance_all_completed": summarize_perf(rows),
        "performance_completed_ge_6h": summarize_perf(rows, min_hours=6.0),
    }
    (REPORT_DIR / "runner_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    if SCATTER_SVG.exists():
        shutil.copyfile(SCATTER_SVG, REPORT_DIR / "runner_history_scatter.svg")
    if SCATTER_HTML.exists():
        shutil.copyfile(SCATTER_HTML, REPORT_DIR / "runner_history_scatter.html")

    write_readme(rows, ccache_rows, summary)

    print(f"Wrote report artifacts to {REPORT_DIR}")


if __name__ == "__main__":
    main()
