# PR Review: TheRock #4908

* **PR:** https://github.com/ROCm/TheRock/pull/4908
* **Title:** [CI] Auto-generate manifest-diff report from multi-arch CI on PR/push
* **Author:** `amd-hsivasun`
* **Branch:** `amd/hsivasun/bump-pr-blamelist`
* **Base:** `main`
* **Reviewed:** 2026-06-01
* **Head:** `f2171c5d87ed9e819fdb380c374d06c58e414f13`
* **Net changes:** +396 / -87 across 9 files

---

## Summary

This PR wires the manifest-diff reusable workflow into multi-arch CI, expands
its ref-resolution modes, updates the manifest-diff Python helper, adds path
filter coverage, and documents the new report.

CI evidence checked:

* `Manifest Diff / Generate Manifest Diff Report` passed in run `26650189072`
  in 38s.
* `pre-commit`, Linux unit tests, and Windows unit tests passed.
* The current multi-arch CI summary is failing because multiple component test
  jobs failed. I did not find evidence tying those failures to this
  manifest-diff change; `gh run view --job --log` could not retrieve two
  sampled failing logs (`zip: not a valid zip file`).

## Overall Assessment

**CHANGES REQUESTED** - the workflow currently interpolates manual/call inputs
directly into Bash, and one newly advertised trigger path is not covered by
end-to-end evidence.

## Detailed Findings

### BLOCKING: Workflow inputs are interpolated directly into Bash

[`manifest-diff.yml`](https://github.com/ROCm/TheRock/blob/f2171c5d87ed9e819fdb380c374d06c58e414f13/.github/workflows/manifest-diff.yml#L121-L129)
passes `inputs.end_ref`, `inputs.start_ref`, `inputs.find_last_run`,
`inputs.pr_base_ref`, and `inputs.branch` directly into a `run:` script:

```yaml
--end "${{ inputs.end_ref || ... }}" \
--start "${{ inputs.start_ref || ... }}" \
--find-last-run "${{ inputs.find_last_run }}" \
--pr-base-ref "${{ inputs.pr_base_ref || ... }}" \
--branch "${{ inputs.branch }}" \
```

GitHub expressions are expanded before Bash parses the script, so an input
containing a quote can terminate the quoted argument and append another shell
command. These are the workflow's manual `workflow_dispatch` input surface, and
future `workflow_call` callers can also route values into the same script. This
job runs on ROCm CI runners and has `id-token: write`, so the values must be
treated as data, not shell source.

**Required action:** Resolve the expressions into step `env:` variables and
reference them as quoted shell variables, e.g. `--end "$END_REF"`. Keep the
optional `--workflow-mode` token controlled by the boolean expression only, or
move the invocation into a small Python wrapper so all inputs are passed as
structured arguments.

### BLOCKING: The new push path has no end-to-end coverage

The new multi-arch CI job explicitly runs for both PR and push events in
[`multi_arch_ci.yml`](https://github.com/ROCm/TheRock/blob/f2171c5d87ed9e819fdb380c374d06c58e414f13/.github/workflows/multi_arch_ci.yml#L118-L123),
and the reusable workflow derives push refs through `github.event.before` and
`github.sha` in
[`manifest-diff.yml`](https://github.com/ROCm/TheRock/blob/f2171c5d87ed9e819fdb380c374d06c58e414f13/.github/workflows/manifest-diff.yml#L123-L124).
The PR description explicitly says the `push` / explicit `--start` path is not
covered by the linked end-to-end runs.

This is a separate workflow path from the tested PR-base and manual-dispatch
paths. Push events are also where `github.event.before` can be unusual, such as
branch creation or rewritten history, so the expression wiring and local git
history assumptions need real CI evidence before this is enabled on push.

**Required action:** Add a successful push-triggered run for a CI-relevant
branch that produces the manifest report, or remove the push arm from this PR
and land it separately once it has coverage.

### IMPORTANT: No-match behavior is documented as exit 0 but implemented as exit 1

The file header says that when no usable start ref can be derived, the script
logs the reason and
[`exits 0`](https://github.com/ROCm/TheRock/blob/f2171c5d87ed9e819fdb380c374d06c58e414f13/build_tools/generate_manifest_diff_report.py#L26-L27).
The `resolve_commits()` docstring also says the no-match case is a graceful
empty result and that the caller
[`should exit 0`](https://github.com/ROCm/TheRock/blob/f2171c5d87ed9e819fdb380c374d06c58e414f13/build_tools/generate_manifest_diff_report.py#L256-L258).
However, `main()` treats that same case as a failure and
[`returns 1`](https://github.com/ROCm/TheRock/blob/f2171c5d87ed9e819fdb380c374d06c58e414f13/build_tools/generate_manifest_diff_report.py#L1486-L1492).

That mismatch matters because `workflow_dispatch` is intentionally strict in
this PR. A first-ever `--find-last-run` case will be red even though the script
documentation describes it as a successful empty result.

**Recommendation:** Choose the intended contract and make the code, comments,
and tests agree. If no-match should be non-zero to suppress uploads, update the
docstrings/PR-facing docs and add a `main()` test for that behavior. If it
should be graceful, return 0 and gate upload on report existence instead of
step failure.

## Non-Issues Checked

* The manifest-diff script and upload script dependencies appear to be present
  in the new container job: `git`, `curl`, and `unzip` are installed before
  checkout/script execution, Python 3.12 is set up, and AWS CLI is installed
  before `upload_test_report_script.py` calls `aws s3 cp`.
* The new reusable workflow has only one current in-repo caller,
  `multi_arch_ci.yml`, and that caller does not introduce new required inputs.
* The new path filter entry for `manifest-diff.yml` is consistent with the
  workflow-only CI trigger intent.

## Verification

* Fetched PR metadata and changed-file list via GitHub REST.
* Reviewed the full PR diff with `gh pr diff`.
* Checked `gh pr checks`; `gh pr view` was unavailable because the local GitHub
  CLI is not authenticated for GraphQL.
* Read the ROCm review guidelines for GitHub Actions, tests, documentation,
  security, PR hygiene, and PR patterns.
* Downloaded PR-head copies of the changed workflow/script/docs files into
  `D:/scratch/codex/pr4908` for line-numbered inspection.

---

Generated by Codex.
