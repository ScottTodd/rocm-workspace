# Branch Review: users/scotttodd/torch-manifest-2

* **Branch:** `users/scotttodd/torch-manifest-2`
* **Base:** `main`
* **Reviewed:** 2026-05-21
* **Commits:** 25 commits

---

## Summary

This branch adds upfront PyTorch manifest generation, manifest-driven checkout,
release-matrix manifest preparation, a reusable Linux multi-arch PyTorch build
workflow, per-cell quick-test dispatch, and related unit tests/docs.

**Net changes:** 3272 insertions, 302 deletions across 25 files.

Evidence checked:

- Local unit tests:
  `D:/projects/TheRock/.venv/Scripts/python.exe -m pytest github_actions/tests/generate_pytorch_manifest_upfront_test.py github_actions/tests/checkout_from_manifest_test.py github_actions/tests/prepare_pytorch_manifests_test.py github_actions/tests/configure_pytorch_test_matrix_test.py github_actions/tests/write_pytorch_manifest_versions_test.py github_actions/tests/publish_pytorch_to_release_bucket_test.py github_actions/tests/determine_version_test.py`
  passed: 44 tests.
- Workflow run
  https://github.com/ROCm/TheRock/actions/runs/26195227273 generated manifests
  and completed multiple build jobs. It failed in quick test jobs. I could see
  failed step names through `gh run view`, but GitHub denied log download with
  HTTP 403.

---

## Overall Assessment

**CHANGES REQUESTED** - The architecture is close, and the CI evidence is
useful, but one manifest-resolution behavior still violates the fail-fast
contract and should be fixed before review. The remaining workflow style/docs
items can be handled either before the workflow PR or explicitly scoped into
follow-up PRs.

**Strengths:**

- Clear separation between manifest preparation, checkout, build, publish, and
  test matrix code.
- Good focused unit coverage for the new Python helpers.
- The Linux workflow shape matches the desired release -> per-cell build ->
  per-cell quick-test flow.
- The linked run gives useful evidence that manifest generation, checkout, and
  wheel builds are broadly wired correctly.

**Issues:**

- BLOCKING: stable manifest generation can silently fall back to a branch when
  a required related commit pin is absent.
- IMPORTANT: the new reusable Linux workflow still contains substantial inline
  shell logic.
- IMPORTANT: reviewer/operator docs for the new multi-arch PyTorch workflows
  are not yet in `docs/development/github_actions_debugging.md`.

---

## Detailed Review

### 1. Manifest Generation

**BLOCKING: Missing related commit pins fall back to branches**

- In `build_tools/github_actions/generate_pytorch_manifest_upfront.py`,
  `resolve_sources()` still falls back to `config.nightly_branch or "main"` when
  a non-nightly project has a `related_commits_key` but that key is missing from
  `related_commits`:
  `fallback = config.nightly_branch or "main"` around line 283.
- That can generate a manifest using the current branch head for audio, vision,
  or apex instead of the version explicitly pinned by the selected ROCm PyTorch
  release branch.
- This is exactly the sort of unexpected fallback we wanted to avoid. A
  manifest is supposed to make source selection explicit and reproducible; if a
  stable branch lacks a required pin, the build should fail before checkout.
- The parser also only logs and skips malformed `related_commits` lines around
  line 132. For manifest generation, malformed pin data should be treated as
  invalid input unless there is a specific known reason to ignore that line.

**Required action:** replace the fallback branch with a `ValueError` that names
the missing project/key and PyTorch ref. Add a regression test that a stable
manifest errors when `related_commits` omits an expected pin. Consider making
malformed `related_commits` lines fail fast too.

### 2. Workflow Shape And Style

**IMPORTANT: New reusable workflow still has complex inline shell logic**

- `.github/workflows/multi_arch_build_portable_linux_pytorch_wheels.yml` still
  carries non-trivial logic in `run:` blocks:
  cache flag selection around lines 305-318, cache stats branching around
  lines 325-333, and wheel-splitting file choreography around lines 358-392.
- Some of this was copied from the existing release workflow, so it is not a
  new design mistake. However, the new workflow is the review target, and the
  direction for this task was to move path parsing, decision logic, and build
  mechanics into scripts where possible.
- The wheel-splitting block in particular is hard to unit test as workflow YAML
  and will be harder to share with Windows or CI variants.

**Recommendation:** before the workflow PR, extract at least the cache flag /
build invocation and split-wheel staging into one or two Python scripts, or
explicitly document in the PR that this is legacy workflow body being moved
unchanged and will be cleaned up separately. If split into multiple PRs, keep
the script extraction with the workflow PR, not the manifest-generator PR.

### 3. Documentation

**IMPORTANT: Missing developer docs for the new multi-arch workflow path**

- The current branch updates `external-builds/pytorch/README.md` with manifest
  checkout/generation details, but
  `docs/development/github_actions_debugging.md` still only documents the
  non-multi-arch PyTorch release workflow.
- The new workflow has developer-facing dispatch inputs that matter for safe
  testing: `python_versions`, `pytorch_git_refs`, `test_amdgpu_families`,
  `manifest_url`, package index expectations, and the distinction between direct
  build workflow runs and release-orchestrator runs.

**Recommendation:** add a section beside "Testing PyTorch release workflows"
covering:

1. How to trigger `multi_arch_release_linux_pytorch_wheels.yml` for a narrow
   dev run.
2. How to trigger `multi_arch_build_portable_linux_pytorch_wheels.yml` once it
   exists on the default branch.
3. Semicolon-separated examples, e.g. `python_versions=3.12`,
   `pytorch_git_refs=release/2.10`, `amdgpu_families=gfx950`,
   `test_amdgpu_families=auto` or `none`.
4. Where manifests are uploaded and how test jobs consume `manifest_url`,
   `torch_version`, and `package_index_url`.
5. Known runner/index caveats for interpreting test failures.

### 4. Tests

**SUGGESTION: Coverage is good, but add fail-fast pin tests**

- The changed unit suite is broad and fast. The tests cover release matrix
  generation, explicit manifest URLs, upload path construction, test matrix
  configuration, checkout command construction, Windows triton gating, and
  package version outputs.
- The main gap is the missing-pin behavior called out above. Without that test,
  a future fallback or warning path can re-enter unnoticed.
- If `generate_pytorch_manifest_upfront.py` remains documented as a developer
  entry point, consider aligning its list parsing with
  `prepare_pytorch_manifests.py` or documenting that the lower-level script
  still uses whitespace-only lists.

### 5. Windows Scope

**FUTURE WORK: Windows multi-arch PyTorch release still uses the legacy body**

- `.github/workflows/multi_arch_release_windows_pytorch_wheels.yml` still has
  the explicit matrix and branch-based checkout flow. That is consistent with
  the current task file, which says to defer Windows until the Linux path is
  passing and reviewed.
- Keep Windows out of the first workflow PR unless we decide the PR needs
  platform parity. A follow-up should mirror the Linux split: reusable per-cell
  Windows build workflow, upfront manifest generation, manifest checkout, and
  version/package outputs.

---

## PR Split Recommendation

1. **PR 1: Manifest scripts and tests**
   - `generate_pytorch_manifest_upfront.py`
   - `prepare_pytorch_manifests.py`
   - `checkout_from_manifest.py`
   - `write_pytorch_manifest_versions.py`
   - `manifest_utils.py`, GitHub API helpers, workflow output helper
   - related unit tests and PyTorch README manifest docs
   - include the fail-fast related-commit fix before opening

2. **PR 2: Test workflow manifest consumption and publish outputs**
   - `test_pytorch_wheels.yml`
   - `test_pytorch_wheels_full.yml`
   - `publish_pytorch_to_release_bucket.py` package index outputs
   - `configure_pytorch_test_matrix.py`
   - related tests

3. **PR 3: Linux multi-arch build/release workflow**
   - `multi_arch_build_portable_linux_pytorch_wheels.yml`
   - `multi_arch_release_linux_pytorch_wheels.yml`
   - `docs/development/github_actions_debugging.md`
   - linked workflow-dispatch evidence from dev runs

4. **PR 4: Windows parity**
   - reusable Windows multi-arch PyTorch build workflow
   - Windows release orchestrator changes
   - Windows triton policy kept explicit until validated

This split keeps the reusable scripts reviewable on their own, lets test
workflow consumers land before the large release workflow change, and avoids
holding the Linux path on Windows runner availability.

---

## Testing Recommendations

- Keep the focused local pytest command above in the PR description with
  duration.
- For the Linux workflow PR, include at least one successful build run with a
  narrow matrix: one Python version, one PyTorch release ref, one or two GPU
  families.
- Include the current evidence from run `26195227273` as partial validation:
  manifest generation and builds succeeded, quick tests fired, and failures
  were in runner/test setup paths rather than manifest/build setup.
- After fixing the fail-fast pin behavior, add a unit test that would have
  failed with the current fallback.

---

## Conclusion

**Approval Status: CHANGES REQUESTED**

The branch is close enough to start turning into reviewable PRs, but fix the
manifest fallback first. Then either trim the largest inline shell blocks before
the Linux workflow PR or explicitly make that a scoped follow-up, and add the
debugging docs so reviewers and release engineers can reproduce the narrow
workflow runs.
