# PR Review: ROCm/TheRock#5368

* **PR:** https://github.com/ROCm/TheRock/pull/5368
* **Issue Context:** https://github.com/ROCm/TheRock/issues/5347
* **Head:** `3f8944b467d27b3bd7a56cbd88f7a59a1d76a1b3`
* **Base:** `bf2a9c03ea9402047d972ff68334a716ea210f16`
* **Reviewed:** 2026-05-20
* **Scope:** Comprehensive review, focused on the `rocm` sdist metadata race/debugging context

---

## Summary

This PR addresses the root issue from #5347 by making the Linux and Windows multi-arch Python package builds feed a common cross-platform GPU-family view into the `rocm` sdist, then using PEP 508 `sys_platform` markers for platform-exclusive device targets. That approach matches the debugging conclusion: keep `rocm` as an sdist for install-time selection, but make the platform-neutral source archive content-identical across the two platform jobs.

**Net changes:** +999 / -22 across 15 files.

---

## Overall Assessment

**CHANGES REQUESTED** - The packaging direction is sound, but the new release parity workflow currently reads from the wrong artifact bucket for release runs, and pre-commit is failing.

**Blocking issues:**

1. `verify_rocm_sdist_parity.yml` hard-codes `therock-ci-artifacts`, but `multi_arch_release.yml` package uploads use release-type-specific artifact buckets.
2. The PR fails the required pre-commit job because `black` reformats two changed Python files.

---

## Detailed Findings

### [BLOCKING] Parity workflow downloads from the wrong bucket for release runs

The new parity workflow downloads from hard-coded `s3://therock-ci-artifacts/${{ github.run_id }}-linux/python/` and the corresponding Windows prefix:

* [`verify_rocm_sdist_parity.yml`](https://github.com/ROCm/TheRock/blob/3f8944b467d27b3bd7a56cbd88f7a59a1d76a1b3/.github/workflows/verify_rocm_sdist_parity.yml#L61-L70)

That is not where `multi_arch_release.yml` uploads Python packages for `release_type: dev`, `nightly`, or `prerelease`. The package build workflows set `RELEASE_TYPE` from the reusable workflow input:

* [`build_portable_linux_python_packages.yml`](https://github.com/ROCm/TheRock/blob/3f8944b467d27b3bd7a56cbd88f7a59a1d76a1b3/.github/workflows/build_portable_linux_python_packages.yml#L111-L116)
* [`build_windows_python_packages.yml`](https://github.com/ROCm/TheRock/blob/3f8944b467d27b3bd7a56cbd88f7a59a1d76a1b3/.github/workflows/build_windows_python_packages.yml#L107-L111)

`upload_python_packages.py` then calls `WorkflowOutputRoot.from_workflow_run(...)` without overriding `release_type`, so it reads `RELEASE_TYPE` from the environment:

* [`upload_python_packages.py`](https://github.com/ROCm/TheRock/blob/3f8944b467d27b3bd7a56cbd88f7a59a1d76a1b3/build_tools/github_actions/upload_python_packages.py#L76-L83)
* [`s3_buckets.py`](https://github.com/ROCm/TheRock/blob/3f8944b467d27b3bd7a56cbd88f7a59a1d76a1b3/build_tools/_therock_utils/s3_buckets.py#L194-L195)

For non-empty release types, the helper selects `therock-{release_type}-artifacts`, not `therock-ci-artifacts`:

* [`s3_buckets.py`](https://github.com/ROCm/TheRock/blob/3f8944b467d27b3bd7a56cbd88f7a59a1d76a1b3/build_tools/_therock_utils/s3_buckets.py#L97-L104)

Impact: the new parity check is aimed at the release workflows, but in actual dev/nightly/prerelease runs it will look in the CI bucket instead of the bucket that received the sdists. It will either fail with "No rocm-*.tar.gz" or check the wrong location, so it will not provide the release regression signal this PR intends.

**Required action:** Compute the Linux/Windows Python package source locations the same way the upload/publish path does, preferably via `WorkflowOutputRoot.from_workflow_run(run_id=..., platform=..., release_type=inputs.release_type)` in a small Python helper or by passing the resolved bucket/prefix from setup. This should also preserve external-repo prefix handling instead of hard-coding the bucket and root prefix.

### [BLOCKING] pre-commit fails because `black` reformats changed files

The PR's `pre-commit` check is failing:

* CI job: https://github.com/ROCm/TheRock/actions/runs/26176453523/job/77007698321

The log shows `black` reformatted:

* [`build_tools/_therock_utils/py_packaging.py`](https://github.com/ROCm/TheRock/blob/3f8944b467d27b3bd7a56cbd88f7a59a1d76a1b3/build_tools/_therock_utils/py_packaging.py#L157-L163)
* [`build_tools/tests/py_packaging_test.py`](https://github.com/ROCm/TheRock/blob/3f8944b467d27b3bd7a56cbd88f7a59a1d76a1b3/build_tools/tests/py_packaging_test.py#L1048-L1051)

Impact: required CI is red, and the diff in the pre-commit log is mechanical formatting only.

**Required action:** Run `pre-commit run --all-files` or apply the `black` formatting diff and rerun pre-commit.

---

## Notes

The core metadata design looks aligned with the issue: both platforms should produce a `rocm` sdist that advertises the union of device extras, and platform-only targets such as Linux `gfx942`/`gfx950` are guarded by `sys_platform` markers instead of being omitted from the sdist entirely.

One behavior to be aware of: with platform markers, a Windows user asking for a Linux-only extra like `rocm[device-gfx950]` will get a recognized extra whose requirement is skipped by marker evaluation, not the old "does not provide the extra" warning. That is probably the practical tradeoff for one shared sdist, but it is worth keeping in mind for docs and tests.

The parity workflow is also explicitly post-publish, not a publish gate. The PR documents that limitation; a pre-publish collision guard remains separate future work if we want to prevent a bad sdist from reaching the public index.

---

## CI Evidence

* Unit tests are passing in the PR checks.
* `pre-commit` is failing on formatting.
* The large multi-arch PR run still has pending jobs; the listed Windows compiler-runtime failure is a cancelled build step, not evidence of a code failure from this diff.
* The linked dev-mode release run in `ROCm/rockrel` was still in progress when reviewed, so it has not yet validated the new parity job end to end.

---

## Recommendation

Fix the bucket/source-location mismatch in the parity workflow and the black formatting failure, then rerun:

1. `pre-commit run --all-files`
2. `pytest build_tools/tests/py_packaging_test.py`
3. `pytest build_tools/github_actions/tests/configure_multi_arch_ci_test.py`
4. A dev-mode `multi_arch_release.yml` dispatch that reaches `verify_sdist_parity` and proves it downloads from the release-type-specific artifact bucket.

