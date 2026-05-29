# PR Review: TheRock #5481

* **PR:** https://github.com/ROCm/TheRock/pull/5481
* **Title:** Make CI release type explicit and limit workflow_dispatch inputs to [ci, dev]
* **Branch:** `users/scotttodd/release-type-dispatch`
* **Base:** `main`
* **Reviewed:** 2026-05-27
* **Net changes:** +273 / -170 across 49 files

---

## Summary

This PR makes `ci` an explicit artifact release type instead of treating an
empty string as CI, updates bucket/version helpers accordingly, and restricts
TheRock manual `workflow_dispatch` `release_type` inputs to either `dev` or
`ci`/`dev` depending on workflow purpose. `workflow_call` paths still accept
nightly/prerelease values for rockrel and scheduled release use.

## Overall Assessment

**APPROVED** - I did not find a blocking code or workflow correctness issue.
The release type flow is internally consistent, all current
`workflow_dispatch.release_type` inputs are `choice` inputs with only `dev` or
`ci`/`dev`, and the targeted local tests pass.

## Findings

### SUGGESTION: Clarify That Scheduled Nightly Release Paths Remain

The PR description says nightly/prerelease releases should be triggered in
rockrel, which is directionally right for manual developer dispatch, but
[`release_portable_linux_packages.yml`](https://github.com/ROCm/TheRock/blob/0ede2d655cf59e8e2d6394abcc31254831d6e00c/.github/workflows/release_portable_linux_packages.yml#L63-L77)
and
[`release_windows_packages.yml`](https://github.com/ROCm/TheRock/blob/0ede2d655cf59e8e2d6394abcc31254831d6e00c/.github/workflows/release_windows_packages.yml#L70-L84)
still intentionally map scheduled runs to `nightly`.

**Recommendation:** Add one sentence that this PR restricts manual
`workflow_dispatch` choices in TheRock, while preserving existing scheduled
nightly behavior and broad `workflow_call` inputs.

### SUGGESTION: Add A Policy Test For `workflow_dispatch.release_type`

I verified with the existing workflow YAML helpers that every current
`workflow_dispatch.release_type` input is `type: choice` and only offers
`['dev']` or `['ci', 'dev']`. That is the main policy this PR establishes, but
the PR does not add a test that enforces it.

**Recommendation:** Consider adding a concise test under
`build_tools/github_actions/tests/` using `workflow_utils.load_workflow()` to
assert this policy for all workflows. This is not required for correctness
today, but it would keep the policy from drifting.

## Non-Issues Checked

* The code-quality bot comment about mixing `import unittest` with
  `from unittest import mock` does not match the local test style. Several
  existing `build_tools` tests use that pattern, including
  `tests/s3_buckets_test.py`, `tests/artifact_backend_test.py`, and
  `github_actions/tests/upload_pytorch_manifest_test.py`.
* The required pre-commit and unit test checks are already represented in CI;
  the PR body does not need to repeat local `pre-commit` or `pytest` commands.
* The `Generated with Codex` footer matches the current workspace preference
  for tool-specific AI footers.

## Verification

* `gh pr checks` shows pre-commit, Linux/Windows unit tests, Python analysis,
  and CI summary passing; two multi-arch stage jobs were still pending during
  review.
* `pre-commit run --from-ref main --to-ref HEAD` passed locally.
* Targeted pytest run:
  `tests/s3_buckets_test.py tests/compute_rocm_package_version_test.py github_actions/tests/write_artifacts_bucket_info_test.py`
  passed: 50 passed.
* Additional workflow/helper pytest run:
  `github_actions/tests/workflow_dispatch_inputs_test.py github_actions/tests/fetch_package_targets_test.py github_actions/tests/configure_multi_arch_ci_test.py github_actions/tests/github_actions_api_test.py`
  passed: 123 passed, 7 skipped.
* Programmatic workflow scan found no `workflow_dispatch.release_type` inputs
  outside the allowed choice sets.
