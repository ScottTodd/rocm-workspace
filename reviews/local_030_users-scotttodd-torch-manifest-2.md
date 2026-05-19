# Branch Review: users/scotttodd/torch-manifest-2

* **Branch:** `users/scotttodd/torch-manifest-2`
* **Base:** `main` (`c1541981de974c981f626d753b67ca70b8846c4c`)
* **Reviewed:** 2026-05-19
* **Commits:** 21 commits

---

## Summary

This branch adds upfront PyTorch manifest generation, manifest-driven source
checkout, a reusable Linux multi-arch PyTorch build workflow, a release
orchestrator that freezes manifests before matrix expansion, and per-cell quick
test orchestration through `test_pytorch_wheels.yml`.

**Net changes:** +3210 / -395 across 29 files.

---

## Planned Step Check

Steps 1-9 in `tasks/active/multi-arch-pytorch-testing.md` are implemented in
the branch. In particular:

- Legacy non-multi-arch workflow churn was reverted.
- Manifest generation, upload, matrix output, and checkout-from-manifest are
  consolidated into user-facing scripts.
- Unit tests cover manifest generation, manifest checkout, manifest matrix
  preparation, package version extraction, and quick-test matrix generation.
- `multi_arch_release_linux_pytorch_wheels.yml` now generates manifests once
  and calls `multi_arch_build_portable_linux_pytorch_wheels.yml` per
  Python/PyTorch cell.
- The reusable build workflow publishes wheels, emits `package_index_url`, and
  calls `test_pytorch_wheels.yml` with `multi_arch=true` and the build cell's
  manifest URL.

Remaining planned work is correctly still pending:

- Step 10: real workflow-dispatch validation.
- Step 11: decide parent release workflow ergonomics for developer profiles.
- Step 12: add separate full-test dispatch following PR #4499 shape.
- Step 13: repeat the split for Windows after Linux validation.

One note: the high-level "Goals" checklist still shows "Test matrix script" and
"Add test jobs to multi-arch release workflows" unchecked even though step 9 is
implemented. That is documentation cleanup, not a code blocker.

---

## Overall Assessment

**CHANGES REQUESTED** - The branch is close to workflow validation for narrow
direct runs, but the default `auto` quick-test path can fail for broad
nightly/prerelease release builds that include nightly-only GPU families.

**Strengths:**

- The build/test data flow is much cleaner: manifest URL, package versions, and
  package index URL are explicit workflow outputs instead of being reconstructed
  downstream.
- The release workflow now freezes manifests before matrix expansion, so
  parallel Python-version jobs use the same PyTorch ecosystem commits.
- Tests exercise the main Python units and can be run locally without network
  access.
- `test_package_index_url` was avoided; package index URL is emitted by the
  publish helper.

**Issues:**

- `BLOCKING`: `auto` quick tests fail for nightly-only build families.
- `IMPORTANT`: Windows nightly triton fallback catches all exceptions and can
  hide GitHub API failures.
- `IMPORTANT`: The new reusable workflow still carries complex inline Bash in
  build/split steps.

---

## Detailed Review

### 1. Quick Test Matrix

**BLOCKING: `auto` quick tests fail for broad release family sets**

`configure_pytorch_test_matrix.py` resolves test families against only the
presubmit and postsubmit family matrices:

`build_tools/github_actions/configure_pytorch_test_matrix.py:47`

```python
matrix = get_all_families_for_trigger_types(["presubmit", "postsubmit"])
```

That is fine for the narrow `gfx950` direct validation path, but release
workflows can build broader family sets. The main multi-arch setup code uses
`["presubmit", "postsubmit", "nightly"]` for scheduled/full coverage, and
`multi_arch_release_linux.yml` passes `dist_amdgpu_families` through to the
PyTorch release workflow. With `test_amdgpu_families` defaulting to `auto`, the
quick-test script tries to resolve every built family. A known nightly-only
family such as `gfx900` is treated as unknown and fails the configure job
instead of being skipped as a family with no configured test runner.

I reproduced the failure locally:

```powershell
D:/projects/TheRock/.venv/Scripts/python.exe github_actions/configure_pytorch_test_matrix.py --build-amdgpu-families "gfx900" --package-index-url "https://example.com/whl/"
```

Result:

```text
ValueError: No linux AMDGPU family entry found for 'gfx900'
```

Impact: scenario 1 from the plan - nightly/prerelease release workflow runs
tests on all available runners - is not reliable yet. Broad release builds may
fail in `configure_pytorch_tests` before any quick test job runs.

Required action: make the quick-test resolver see the same known family universe
as release setup, including nightly families. Known families with no
`test-runs-on` should be skipped with a summary entry. Keep failing fast for
truly unknown explicit test family input. Add a unit test for a nightly-only
known family with no runner so this does not regress.

### 2. Manifest Generation

**IMPORTANT: Windows nightly triton fallback catches all exceptions**

`generate_pytorch_manifest_upfront.py` catches broad `Exception` when fetching
the triton pin and falls back to `main-windows` when `fallback_branch` is set:

`build_tools/github_actions/generate_pytorch_manifest_upfront.py:184`

```python
except Exception:
    if fallback_branch:
        log(f"  triton: no pin file, falling back to {fallback_branch}")
```

The intent is reasonable - tolerate an absent Windows triton pin - but the
catch also hides unrelated failures such as rate limits, auth problems, network
errors, or malformed API responses. That can silently produce a manifest with a
different triton commit from the intended pin.

Recommendation: catch only the "pin file does not exist" condition. If
`GitHubAPIError` does not currently expose HTTP status, either extend it enough
to distinguish 404 from other failures, or add a small helper that returns
`None` only for file-not-found and re-raises all other API failures. This can
land before the Windows workflow split if Linux validation is the immediate
target.

### 3. GitHub Actions Style

**IMPORTANT: Complex inline Bash remains in the new reusable build workflow**

The new `multi_arch_build_portable_linux_pytorch_wheels.yml` still contains
substantial inline Bash logic, including cache flag selection, cache stats
branching, command substitution for target expansion, and the fat-wheel split
block:

- `.github/workflows/multi_arch_build_portable_linux_pytorch_wheels.yml:298`
- `.github/workflows/multi_arch_build_portable_linux_pytorch_wheels.yml:305`
- `.github/workflows/multi_arch_build_portable_linux_pytorch_wheels.yml:325`
- `.github/workflows/multi_arch_build_portable_linux_pytorch_wheels.yml:356`

Most of this was moved from the prior release workflow rather than newly
invented, so I would not block the first focused workflow-dispatch validation
on it. It is still at odds with the GitHub Actions style guide and the stated
direction to keep workflow logic in scripts where it can be unit tested.

Recommendation: before treating this as PR-ready, extract at least the cache
argument selection and wheel-splitting sequence into build_tools scripts. The
split step is the highest-value extraction because it is long, package-critical,
and currently only testable by running the full workflow.

---

## Recommendations

### Required

1. Fix quick-test family resolution so `auto` works for broad release family
   sets, including known nightly-only families without runners.
2. Add a regression test for a known no-runner/nightly-only family.

### Recommended

1. Narrow the Windows triton fallback exception handling before relying on
   Windows manifests.
2. Start extracting the remaining complex inline Bash from the reusable build
   workflow into scripts.
3. Update the high-level task checklist to mark the test matrix script and
   release quick-test jobs as implemented.

### Future Follow-up

1. Move package bucket to CDN/index URL mapping into
   `build_tools/_therock_utils/s3_buckets.py`, as already noted in the code.
2. Add PR #4499-style full-test dispatch after quick Linux validation.
3. Repeat the reusable build/orchestrator split for Windows.

---

## Testing Evidence

Ran focused Python tests from `D:/projects/TheRock/build_tools`:

```powershell
D:/projects/TheRock/.venv/Scripts/python.exe -m pytest github_actions/tests/checkout_from_manifest_test.py github_actions/tests/configure_pytorch_test_matrix_test.py github_actions/tests/determine_version_test.py github_actions/tests/generate_pytorch_manifest_upfront_test.py github_actions/tests/prepare_pytorch_manifests_test.py github_actions/tests/publish_pytorch_to_release_bucket_test.py github_actions/tests/publish_rocm_to_release_buckets_test.py github_actions/tests/write_pytorch_manifest_versions_test.py
```

Result: 45 passed, 1 pytest cache warning from local `.pytest_cache` permissions.

Ran changed-file pre-commit:

```powershell
pre-commit run --from-ref main --to-ref HEAD
```

Result: all hooks passed, including YAML checks, black, mdformat, and GitHub
Actions workflow linting.

Also reproduced the blocking quick-test matrix failure with `gfx900` as shown
above.

---

## Workflow Validation Guidance

After fixing the `auto` family-resolution issue, the next useful real runs are:

1. Direct reusable build workflow dispatch for one cell:
   `amdgpu_families=gfx950`, `test_amdgpu_families=auto`, one Python version,
   one PyTorch release ref.
2. Direct reusable build workflow dispatch with an explicit narrower test set:
   build a small multi-family set and set `test_amdgpu_families=gfx950` or
   similar.
3. Release orchestrator dispatch with a narrow dev family set, verifying that
   manifests are generated once and each child build/test cell receives its
   explicit manifest URL.
4. A broader release-like run only after the blocking matrix issue is fixed.

---

## Conclusion

**Approval Status: CHANGES REQUESTED**

The architecture and data flow are in good shape for the intended build to test
bridge, and the local test coverage is a useful base. Fix the quick-test matrix
resolver before relying on broad nightly/prerelease release runs. Narrow direct
workflow-dispatch runs can still be useful for validating the rest of the
pipeline, but they would not exercise the failing broad-family path.
