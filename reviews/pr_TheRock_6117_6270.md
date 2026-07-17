# PR Stack Review: ROCm/TheRock #6117 and #6270

* **PRs:** https://github.com/ROCm/TheRock/pull/6117 and https://github.com/ROCm/TheRock/pull/6270
* **Reviewed:** 2026-06-30
* **Base relationship:** #6270 is based on #6117
* **Scope:** Comprehensive review of workflow, Python, tests, CI status, and caller propagation

---

## Summary

PR #6117 adds an optional JAX release build toggle, threads `python_version`
into the JAX release workflow, and moves the JAX release matrix into
`configure_jax_release_matrix.py`. PR #6270 builds on that by making setup
compute and report the JAX build matrix so release workflows can gate the JAX
dispatch from setup-produced build configuration.

**Net changes:** #6117 reports +169/-21 across 5 files. #6270 reports +127/-11
across 9 files.

---

## Overall Assessment

**APPROVED** - I did not find blocking or important code-review findings in
the stack. The workflow input propagation, Python matrix generation, summary
formatting, and tests are coherent with the existing patterns.

**Blocking issues:** None.

**Notes:**

* PR #6117 has a failing `therock-pr-bot` check about Conventional Commits
  title format. I am not treating that as a review finding because the linked
  ROCm `CONTRIBUTING.md` does not require Conventional Commits titles.
* PR #6270 still had release build jobs pending during the latest check.

---

## Detailed Review

### 1. PR Hygiene

No findings.

The ROCm `CONTRIBUTING.md` pull request guidance requires clear testing
evidence, successful builds/tests, and tests for new functionality. It does not
state a Conventional Commits PR-title requirement, so the #6117 bot failure is
not counted as a review issue here.

### 2. Workflow Input Propagation

No code findings.

I checked the TheRock reusable-workflow chain for `setup_multi_arch.yml`,
`multi_arch_release.yml`, `multi_arch_release_asan.yml`,
`multi_arch_release_linux.yml`, `multi_arch_ci.yml`, and
`multi_arch_ci_asan.yml`. The new `build_jax` input is propagated through the
callers that need it, CI and ASAN keep JAX disabled, and the Linux release JAX
dispatch is gated on both the explicit input and the setup-generated
`build_config.build_jax` flag in #6270.

The sibling `rockrel` caller also appears to have a matching follow-up,
ROCm/rockrel#70, adding `python_version` to its JAX release wrapper.

### 3. Python Matrix Code

No code findings.

`configure_jax_release_matrix.py` follows the existing PyTorch matrix generator
pattern: local constants, a small split helper, pure matrix generation, and
`gha_set_output` at the CLI boundary. The workflow step that runs it checks out
the same repository/ref that downstream jobs use, and the script imports only
stdlib plus local build-tools code, so I do not see a missing dependency issue.

### 4. Tests

No code findings.

The new/changed tests cover the new JAX matrix generation, `BUILD_JAX` input
parsing, decision wiring, Linux-only matrix expansion, skipped JAX behavior,
serialization, and summary formatting. The tests are behavior-oriented and fit
the existing `*_test.py` convention.

---

## CI Evidence

### PR #6117

* `Unit Tests :: ubuntu-24.04`: pass
* `Unit Tests :: windows-2022`: pass
* `pre-commit`: pass
* `gitleaks / Gitleaks scan`: pass
* `therock-pr-bot`: fail due to a Conventional Commits title policy; ignored
  for this review because it is not in `CONTRIBUTING.md`
* PR is labeled `ci:skip`, so normal multi-arch CI jobs are skipped

### PR #6270

* `Unit Tests :: ubuntu-24.04`: pass
* `Unit Tests :: windows-2022`: pass
* `pre-commit`: pass
* `gitleaks / Gitleaks scan`: pass
* `Multi-Arch CI ASAN`: pass
* Release build jobs were still pending at review time

---

## Testing Recommendations

Before merging the stack:

1. Wait for the pending #6270 release build jobs to complete.
2. Keep the linked manual/dev release runs in the PR descriptions, because they
   are the best evidence for the workflow-dispatch paths changed here.

---

## Conclusion

**Approval Status: APPROVED**

The code changes look ready from this review pass. The remaining risk is CI
completion for the release build jobs that were still pending on #6270.

Assisted-by: Codex
