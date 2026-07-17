# Branch Review: users/scotttodd/remove-xfail

* **Branch:** `users/scotttodd/remove-xfail`
* **Base:** `main`
* **Reviewed:** 2026-06-17
* **Commits:** 1 commit (`f72d219b4 Remove defunct expect_[pytorch_]failure properties`)
* **Prior context:** ROCm/TheRock#4500 was a broader draft that mixed `expect_failure` cleanup with `expect_pytorch_failure` changes and later conflicted. Its only issue comment notes the gfx906 PyTorch run unexpectedly succeeded and that the work should likely be split smaller.

---

## Summary

This branch removes multi-arch `expect_failure` / `expect_pytorch_failure` plumbing from generated build configs, generated workflow inputs, and package target output metadata.

The narrow claim that the YAML test filters are useless after a failed build is mostly correct: jobs with `needs: build_multi_arch_stages` and `if: ${{ !failure() && !cancelled() }}` will not run after an upstream build failure. The unsafe part is that the same removed field also affected downstream job generation after successful `host-asan` builds.

**Net changes:** +14 / -46 across 9 files.

---

## Overall Assessment

**CHANGES REQUESTED** - The cleanup is directionally reasonable, but this branch changes post-build behavior for `host-asan` runs without an explicit guard, test, or CI evidence. I would not merge it as-is if the intended change is only to remove dead xfail filtering.

**Strengths:**

- The workflow schema cleanup is internally consistent for local TheRock callers.
- The removed `expect_failure` input was unused by `multi_arch_build_portable_linux.yml` and `multi_arch_build_windows.yml`.
- Targeted unit tests and pre-commit checks pass.

**Blocking Issues:**

- `host-asan` push runs now enable native package and PyTorch jobs that were previously suppressed by `expect_failure`.

---

## Detailed Review

### 1. Multi-Arch Build Config Safety

**BLOCKING: Removing `expect_failure` also enables downstream `host-asan` jobs**

`multi_arch_ci_asan.yml` runs on `push` to `main` and passes `build_variant: "asan"` into setup. In `configure_multi_arch_ci.py`, push ASAN is remapped to `host-asan`, whose suffix is `"host-asan"` in `amdgpu_family_matrix.py`. With this branch, the generated config sets:

```text
push host-asan host-asan linux-release-host-asan True True
```

That means `build_native_linux` and `build_pytorch` are both true for postsubmit `host-asan`. Those booleans directly gate the Linux native package jobs and PyTorch wheel job in `multi_arch_ci_linux.yml`.

On `main`, `host-asan` had `expect_failure: True`. Even though that did not make the build workflow tolerate failures, it did suppress downstream artifact validation, Python package, native package, and PyTorch work after a successful build. This branch removes that suppression. The tests assert the push remap to `linux-release-host-asan`, but they do not assert the downstream job booleans for that case.

Impact: a postsubmit ASAN run that previously stopped after the host-ASAN ROCm build can now attempt native packages, Python packages, and PyTorch wheels from host-ASAN artifacts. That is a real CI behavior change, not just deletion of dead filtering. It may be desirable, but it is not proven here.

Evidence:

- `multi_arch_ci_asan.yml:7` enables push runs, and `multi_arch_ci_asan.yml:56` passes `build_variant: "asan"`.
- `configure_multi_arch_ci.py:992` remaps push ASAN to `host-asan`.
- `amdgpu_family_matrix.py:107` defines `host-asan`; `amdgpu_family_matrix.py:109` gives it suffix `"host-asan"`.
- `configure_multi_arch_ci.py:965` and `configure_multi_arch_ci.py:966` only suppress native/PyTorch jobs when suffix equals `"asan"`.
- `multi_arch_ci_linux.yml:156`, `multi_arch_ci_linux.yml:171`, and `multi_arch_ci_linux.yml:299` consume those booleans.

Required action: either keep the old downstream suppression for `host-asan` explicitly, or make the new behavior intentional and covered. At minimum, add a test for push ASAN/host-ASAN that asserts the intended `build_native_linux` and `build_pytorch` values. If the intended behavior is to start running packages/PyTorch for `host-asan`, link successful CI evidence for a push-equivalent ASAN workflow run.

### 2. Workflow Cleanup

**SUGGESTION: Remove stale comments that still refer to expected build failures**

Several workflow jobs now have conditions that only check upstream status, but the preceding comments still say the condition is for expected build failures.

Examples:

- `multi_arch_ci_linux.yml:120`
- `multi_arch_ci_linux.yml:133`
- `multi_arch_ci_windows.yml:118`
- `multi_arch_ci_windows.yml:131`

Recommendation: replace those comments with a status-based explanation, or remove them if the condition is self-explanatory.

---

## Recommendations

### REQUIRED

1. Decide and encode the intended `host-asan` downstream behavior. Do not let removing `expect_failure` accidentally start native/PyTorch/package jobs.

### Recommended

1. Add a regression test for push ASAN after remapping to `host-asan`, covering `build_native_linux`, `build_pytorch`, and the test runner behavior.
2. If external repositories can call `multi_arch_build_portable_linux.yml` or `multi_arch_build_windows.yml` directly, verify they do not pass `expect_failure`; removed reusable workflow inputs are validation-breaking for stale callers.

### Consider

1. Clean up stale workflow comments mentioning expected failures.

---

## Verification

Commands run:

```powershell
D:/projects/TheRock/.venv/Scripts/python.exe -m pytest -p no:cacheprovider github_actions/tests/configure_multi_arch_ci_test.py
D:/projects/TheRock/.venv/Scripts/python.exe -m pytest -p no:cacheprovider github_actions/tests/amdgpu_family_matrix_test.py
D:/projects/TheRock/.venv/Scripts/python.exe -m pytest -p no:cacheprovider github_actions/tests/fetch_package_targets_test.py
pre-commit run --files .github/workflows/multi_arch_build_portable_linux.yml .github/workflows/multi_arch_build_windows.yml .github/workflows/multi_arch_ci_linux.yml .github/workflows/multi_arch_ci_windows.yml build_tools/github_actions/amdgpu_family_matrix.py build_tools/github_actions/configure_multi_arch_ci.py build_tools/github_actions/fetch_package_targets.py build_tools/github_actions/new_amdgpu_family_matrix.py build_tools/github_actions/tests/configure_multi_arch_ci_test.py
```

Results:

- `configure_multi_arch_ci_test.py`: 73 passed, 1 skipped.
- `amdgpu_family_matrix_test.py`: 3 passed.
- `fetch_package_targets_test.py`: 10 passed.
- `pre-commit run --files ...`: passed, including YAML validation, Black, and GitHub Actions workflow linting.

Limitations:

- `gh pr view` failed with `HTTP 401` in this shell, so I used public GitHub REST endpoints for PR #4500 metadata/comments. No authenticated CI check inventory was available.
- GitHub code search also required authentication, so I could only verify local TheRock callers of the removed reusable workflow inputs.

---

## Conclusion

**Approval Status: CHANGES REQUESTED**

Your reasoning about the test-job filters after a failed build is sound. The unsafe part is broader: deleting `expect_failure` changes what happens after successful `host-asan` builds. Guard or explicitly test that behavior before merging.

Generated by Codex.
