# PR Review: ROCm/TheRock #5288

* **PR:** https://github.com/ROCm/TheRock/pull/5288
* **Title:** `[ci] Enabling ASAN test runners`
* **Author:** `geomin12`
* **Head:** `d69f510ec636f4d3cd5d1948c7550cf6256f773e`
* **Base:** `main` at `ba44369acf04ec5b13ef170698e62ac0fed3a596`
* **Reviewed:** 2026-05-26
* **Net changes:** +93 / -3 across 4 files

---

## Overall Assessment

**CHANGES REQUESTED** - The intended ASAN test skip decision is not wired into the configure outputs or downstream workflows. The tests added in the PR validate `decide_jobs()` but not whether the generated jobs actually skip.

---

## Findings

### BLOCKING: `TestRocmDecision(action=SKIP)` does not suppress downstream test jobs

The PR sets `test_rocm` to `JobAction.SKIP` for ASAN non-schedule/non-dispatch runs:

- [`configure_multi_arch_ci.py#L658-L661`](https://github.com/ROCm/TheRock/blob/d69f510ec636f4d3cd5d1948c7550cf6256f773e/build_tools/github_actions/configure_multi_arch_ci.py#L658-L661)

That decision is not propagated to any workflow output or job condition. `write_outputs()` only emits `enable_build_jobs`, the platform build configs, `test_type`, and test labels:

- [`configure_multi_arch_ci.py#L1028-L1035`](https://github.com/ROCm/TheRock/blob/d69f510ec636f4d3cd5d1948c7550cf6256f773e/build_tools/github_actions/configure_multi_arch_ci.py#L1028-L1035)

`configure()` also still expands build configs using only `jobs.test_rocm.test_type`, so a skipped `test_rocm` still produces a normal Linux build config:

- [`configure_multi_arch_ci.py#L1083-L1089`](https://github.com/ROCm/TheRock/blob/d69f510ec636f4d3cd5d1948c7550cf6256f773e/build_tools/github_actions/configure_multi_arch_ci.py#L1083-L1089)

The ASAN workflow then gates the Linux job only on `linux_build_config != ''` and `enable_build_jobs == 'true'`, and passes only `build_config` and `test_type` to `multi_arch_ci_linux.yml`:

- [`multi_arch_ci_asan.yml#L59-L75`](https://github.com/ROCm/TheRock/blob/d69f510ec636f4d3cd5d1948c7550cf6256f773e/.github/workflows/multi_arch_ci_asan.yml#L59-L75)

Inside the Linux reusable workflow, the ROCm artifact tests and wheel tests gate on `expect_failure`, not on `test_rocm.action`, and they pass `matrix.family_info.test-runs-on` into the test workflows:

- [`multi_arch_ci_linux.yml#L120-L136`](https://github.com/ROCm/TheRock/blob/d69f510ec636f4d3cd5d1948c7550cf6256f773e/.github/workflows/multi_arch_ci_linux.yml#L120-L136)
- [`multi_arch_ci_linux.yml#L229-L246`](https://github.com/ROCm/TheRock/blob/d69f510ec636f4d3cd5d1948c7550cf6256f773e/.github/workflows/multi_arch_ci_linux.yml#L229-L246)

For ASAN, that runner is explicitly populated from `test-runs-on-sandbox`, and the matrix now has a non-empty sandbox runner:

- [`configure_multi_arch_ci.py#L881-L885`](https://github.com/ROCm/TheRock/blob/d69f510ec636f4d3cd5d1948c7550cf6256f773e/build_tools/github_actions/configure_multi_arch_ci.py#L881-L885)
- [`amdgpu_family_matrix.py#L160`](https://github.com/ROCm/TheRock/blob/d69f510ec636f4d3cd5d1948c7550cf6256f773e/build_tools/github_actions/amdgpu_family_matrix.py#L160)

I reproduced the gap locally in a temporary PR worktree by simulating an ASAN pull request with a submodule change, which is the path that bypasses the existing "ASAN PR without submodule changes" whole-workflow skip:

```text
TEST_ROCM_ACTION=skip
LINUX_BUILD_CONFIG_EXISTS=True
TEST_TYPE=full
LINUX_TEST_RUNS_ON=linux-mi325-gpu-rocm-cpu-sandbox
```

That means a submodule-bump ASAN PR can still construct a runnable Linux ASAN build config and then run test jobs on the sandbox runner even though `decide_jobs()` says `test_rocm: skip`.

The current PR CI does not catch this. The `Multi-Arch CI ASAN` pull-request run was successful, but its Linux job was `Linux::skip` because this PR does not change submodules:

- https://github.com/ROCm/TheRock/actions/runs/26174543912/job/77001209693

**Required action:** Wire `test_rocm.action` through the setup outputs and the reusable workflow conditions, or implement the skip directly in the generated test config by clearing/omitting the test runner data when `test_rocm.action == SKIP`. Add an end-to-end test that calls `configure()` for an ASAN pull request with a submodule change and asserts the generated outputs cannot run `test_artifacts_per_family` or `test_python_packages_per_family`.

#### Draft plumbing patch

This is not just a configure-script-only change if `JobAction.SKIP` is meant to control constructed jobs. The decision needs to leave `configure_multi_arch_ci.py`, pass through `setup_multi_arch.yml`, and be consumed by the reusable workflows that construct test jobs.

Minimum affected files:

1. [`configure_multi_arch_ci.py`](https://github.com/ROCm/TheRock/blob/d69f510ec636f4d3cd5d1948c7550cf6256f773e/build_tools/github_actions/configure_multi_arch_ci.py)
2. [`setup_multi_arch.yml`](https://github.com/ROCm/TheRock/blob/d69f510ec636f4d3cd5d1948c7550cf6256f773e/.github/workflows/setup_multi_arch.yml)
3. [`multi_arch_ci_asan.yml`](https://github.com/ROCm/TheRock/blob/d69f510ec636f4d3cd5d1948c7550cf6256f773e/.github/workflows/multi_arch_ci_asan.yml)
4. [`multi_arch_ci_linux.yml`](https://github.com/ROCm/TheRock/blob/d69f510ec636f4d3cd5d1948c7550cf6256f773e/.github/workflows/multi_arch_ci_linux.yml)
5. [`configure_multi_arch_ci_test.py`](https://github.com/ROCm/TheRock/blob/d69f510ec636f4d3cd5d1948c7550cf6256f773e/build_tools/github_actions/tests/configure_multi_arch_ci_test.py)

If the output is intended to be a general multi-arch contract rather than ASAN-only plumbing, also update the other callers and platform workflow:

6. [`multi_arch_ci.yml`](https://github.com/ROCm/TheRock/blob/d69f510ec636f4d3cd5d1948c7550cf6256f773e/.github/workflows/multi_arch_ci.yml)
7. [`multi_arch_ci_windows.yml`](https://github.com/ROCm/TheRock/blob/d69f510ec636f4d3cd5d1948c7550cf6256f773e/.github/workflows/multi_arch_ci_windows.yml)

There are a few reasonable ways to complete this:

**Approach A: Add a scalar `test_rocm_action` output/input.**

This is the smallest direct fix. `configure_multi_arch_ci.py` emits `test_rocm_action`, `setup_multi_arch.yml` exposes it, and the caller passes it into `multi_arch_ci_linux.yml` (and optionally Windows). The reusable workflow gates ROCm test jobs with `inputs.test_rocm_action == 'run'`.

Pros:

- Smallest patch.
- Makes the existing `JobAction.SKIP` decision observable by workflow YAML.
- Easy to review.

Cons:

- Adds another top-level workflow input/output next to `test_type`.
- Sets the pattern for more scalar inputs as the test policy grows.

**Approach B: Add a structured per-platform test config (`linux_test_config`, `windows_test_config`). Recommended if avoiding input sprawl.**

Instead of adding `test_rocm_action` as a sibling to `test_type`, introduce a JSON config object and move related test-policy fields into it:

```json
{
  "test_rocm_action": "skip",
  "test_type": "full",
  "test_type_reason": "ASAN tests skipped due to non-nightly trigger",
  "test_labels": ["test:rocprim"]
}
```

Then `setup_multi_arch.yml` exposes `linux_test_config` and `windows_test_config`, and `multi_arch_ci_linux.yml` consumes fields as:

```yaml
test_type: ${{ fromJSON(inputs.test_config).test_type }}
test_labels: ${{ join(fromJSON(inputs.test_config).test_labels, ',') }}
if: ${{ fromJSON(inputs.test_config).test_rocm_action == 'run' && ... }}
```

Pros:

- Avoids a growing list of workflow inputs for every new test policy knob.
- Gives the configure script one typed place for test-related decisions.
- The existing TODO in `TestRocmDecision` already points in this direction: consolidate test type, labels, and functional-test config into a per-platform test config object.

Cons:

- Touches more call sites than Approach A because existing `test_type` / `test_labels` plumbing needs migration or a compatibility bridge.
- Requires a little care around JSON/list handling in GitHub Actions expressions.

**Approach C: Materialize skip by mutating generated build/test config.**

Instead of surfacing `test_rocm.action`, `configure()` could clear the relevant `test-runs-on` values, or add a `run_rocm_tests: false` field inside `BuildConfig` / `per_family_info`. The existing test workflows already skip when `test_runs_on == ''`.

Pros:

- Can be very small if the only goal is to avoid scheduling GPU test jobs.
- Keeps workflow input count unchanged.

Cons:

- It hides the semantic `JobAction.SKIP` decision inside runner-label mutation.
- It is easy to skip only some test jobs by accident.
- It does not actually complete the job-DAG plumbing promised by `JobDecisions`.

If this PR only wants the tactical ASAN fix, Approach A is acceptable. If this is meant to establish the multi-arch job-decision model, Approach B is cleaner and better aligned with the existing comments in `configure_multi_arch_ci.py`.

Approach A patch sketch:

```diff
diff --git a/build_tools/github_actions/configure_multi_arch_ci.py b/build_tools/github_actions/configure_multi_arch_ci.py
@@
-    test_type = outputs.jobs.test_rocm.test_type if outputs.is_ci_enabled else ""
+    test_type = outputs.jobs.test_rocm.test_type if outputs.is_ci_enabled else ""
+    test_rocm_action = (
+        outputs.jobs.test_rocm.action.value
+        if outputs.is_ci_enabled and outputs.jobs is not None
+        else JobAction.SKIP.value
+    )
     output_vars = {
         "enable_build_jobs": json.dumps(outputs.is_ci_enabled),
         "linux_build_config": json.dumps(linux.to_dict()) if linux else "",
         "windows_build_config": json.dumps(windows.to_dict()) if windows else "",
         "test_type": test_type,
+        "test_rocm_action": test_rocm_action,
         "linux_test_labels": outputs.linux_test_labels,
         "windows_test_labels": outputs.windows_test_labels,
     }
```

```diff
diff --git a/.github/workflows/setup_multi_arch.yml b/.github/workflows/setup_multi_arch.yml
@@
       test_type:
         description: "The test type to run (quick, standard, comprehensive, full)."
         value: ${{ jobs.setup.outputs.test_type }}
+      test_rocm_action:
+        description: "Whether to run ROCm test jobs: run or skip."
+        value: ${{ jobs.setup.outputs.test_rocm_action }}
@@
       test_type: ${{ steps.configure.outputs.test_type }}
+      test_rocm_action: ${{ steps.configure.outputs.test_rocm_action }}
```

```diff
diff --git a/.github/workflows/multi_arch_ci_asan.yml b/.github/workflows/multi_arch_ci_asan.yml
@@
       test_type: ${{ needs.setup.outputs.test_type }}
+      test_rocm_action: ${{ needs.setup.outputs.test_rocm_action }}
```

```diff
diff --git a/.github/workflows/multi_arch_ci_linux.yml b/.github/workflows/multi_arch_ci_linux.yml
@@
       test_type:
         type: string
+      test_rocm_action:
+        type: string
+        default: run
@@
-    if: ${{ !failure() && !cancelled() && fromJSON(inputs.build_config).expect_failure == false }}
+    if: ${{ !failure() && !cancelled() && inputs.test_rocm_action == 'run' && fromJSON(inputs.build_config).expect_failure == false }}
@@
-    if: ${{ !failure() && !cancelled() && fromJSON(inputs.build_config).expect_failure == false }}
+    if: ${{ !failure() && !cancelled() && inputs.test_rocm_action == 'run' && fromJSON(inputs.build_config).expect_failure == false }}
```

Apply the two Linux workflow conditions to `test_artifacts_per_family` and `test_python_packages_per_family`. Leave build jobs, artifact-structure validation, and package-build jobs alone unless the intended policy is to skip all post-build validation. The `JobDecisions` DAG names `test_rocm` as the GPU test node off `build-rocm`, not as a catch-all for build/package/PyTorch work.

The regression test should exercise `configure()`, not only `decide_jobs()`: ASAN + `pull_request` + a changed submodule path should produce `test_rocm.action == JobAction.SKIP`, and the serialized outputs should expose `test_rocm_action=skip` so downstream workflow conditions can consume it.

---

## Notes

- `gh pr view` was unavailable without authentication, so PR metadata came from the public GitHub REST API.
- `gh pr checks` showed unit tests passing, but the overall PR checks currently include unrelated failing jobs in the main multi-arch release workflow.

## Conclusion

**Approval Status: CHANGES REQUESTED**

The specific concern is real: `JobAction.SKIP` for `TestRocmDecision` is currently a local Python decision only, not a job-construction decision.
