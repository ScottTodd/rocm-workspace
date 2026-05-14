# PR Review: hipBLAS: Normalize Windows gtest success exit

* **PR:** [ROCm/rocm-libraries#7060](https://github.com/ROCm/rocm-libraries/pull/7060)
* **Author:** stellaraccident (Stella Laurenzo)
* **Base:** `develop` <- `users/stella/pr3928-landing-hipblas-windows-exit`
* **Reviewed:** 2026-05-05
* **Upstream:** Partial split from [ROCm/TheRock#3928](https://github.com/ROCm/TheRock/pull/3928)

---

## Summary

Attempts to fix a Windows-specific issue where `hipblas-test` reports a
non-zero exit status even when all GTest test cases pass. The fix normalizes
`status` to 0 when GTest's `successful()` API confirms all tests passed,
before passing it to `std::quick_exit()`.

**Net changes:** +5 lines, -2 lines across 1 file

---

## Overall Assessment

**CHANGES REQUESTED** - Local debugging proves this fix will not resolve the
exit code 3 issue. The exit code is set by `quick_exit` itself (likely via
`at_quick_exit` handlers from loaded DLLs), not by the `status` variable.
Normalizing `status` to 0 before calling `quick_exit(0)` still produces exit
code 3.

**Strengths:**

- Correctly identifies the symptom (non-zero exit from passing tests)
- Uses the canonical GTest API for test result checking

**Blocking Issues:**

- The fix doesn't address the actual cause of exit code 3
- Local reproduction proves `quick_exit(status)` produces exit code 3
  regardless of `status` value when `std::system()` was previously called

---

## Detailed Review

### ❌ BLOCKING: Fix does not resolve exit code 3

**Local reproduction on Windows (gfx1100, W7900 Dual Slot)** using CI
artifacts from
[run 25334533811](https://github.com/ROCm/TheRock/actions/runs/25334533811):

```
$ # Same binary, same single passing test, different --yaml vs --data:

$ hipblas-test.exe --gtest_filter=hipblas_auxiliary.statusToString
[  PASSED  ] 1 test.
EXIT CODE: 0

$ hipblas-test.exe --yaml hipblas_smoke.yaml --gtest_filter=hipblas_auxiliary.statusToString
[  PASSED  ] 1 test.
EXIT CODE: 3

$ hipblas-test.exe --data <pre-generated-data> --gtest_filter=hipblas_auxiliary.statusToString
[  PASSED  ] 1 test.
EXIT CODE: 0
```

The **only** difference between `--yaml` and `--data` is that `--yaml`
triggers [`hipblas_parse_yaml()`](https://github.com/ROCm/rocm-libraries/blob/develop/projects/hipblas/clients/common/hipblas_parse_data.cpp#L37),
which calls `std::system()` to run `hipblas_gentest.py`. The gentest script
itself returns 0 — the issue is that calling `std::system()` in a process that
later calls `std::quick_exit()` causes the process exit code to be 3 on
Windows/MSVC.

**Why normalizing `status` doesn't help:** The exit code 3 is not coming from
`RUN_ALL_TESTS()` or the `status` variable. It's produced by `quick_exit()`
itself, likely via an `at_quick_exit` handler registered by one of the loaded
ROCm DLLs (amdhip64, comgr, rocblas, etc.) whose behavior changes after
`system()` has been called. Evidence:

- Exit code 3 occurs whether tests pass (CI: 1676 pass) or fail (local: 664
  fail due to driver mismatch) — the value of `status` is irrelevant
- A minimal reproduction loading the same DLLs from Python and calling
  `system()` + `quick_exit()` via ctypes does NOT reproduce the issue,
  indicating the trigger is specific to the DLLs' `DllMain` initialization
  path (import-table loading vs. runtime `LoadLibrary`)

### ⚠️ IMPORTANT: hipblas is the only test binary using `quick_exit`

All other test binaries in rocm-libraries (rocblas, rocsolver, hipsolver,
hipsparse, hipblaslt, etc.) just `return status;` — hipblas is the only one
using `std::quick_exit()`. The original rationale was that "Post-main cleanup
in linked DLLs (HIP runtime) crash in comgr." If the comgr teardown crash has
been resolved in other test binaries that use normal `return`, it may no longer
be necessary here.

---

## Root Cause Analysis

The exit code 3 is caused by the combination of:

1. **`std::system()`** called in `hipblas_parse_yaml()` to run
   `hipblas_gentest.py`
2. **`std::quick_exit()`** called at process exit to bypass DLL teardown
3. **ROCm DLLs loaded via import table** (amdhip64, comgr, rocblas, kpack,
   etc.) which register `at_quick_exit` handlers during `DllMain`

The `at_quick_exit` handlers run during `quick_exit()` and apparently interact
with CRT state left behind by `system()`, causing the process to exit with
code 3 instead of the requested status.

Note: exit code 3 on Windows is `ERROR_PATH_NOT_FOUND`, and `hipErrorNotInitialized`
is also 3 in the HIP error enum. The latter is suggestive — after `hipDeviceReset()`
puts the runtime into a "not initialized" state, a cleanup handler checking device
status could produce this code.

---

## Recommended Fixes

Any one of these should resolve the issue:

### Option 1: Replace `std::system()` with `CreateProcessW()` (preferred)

In `hipblas_parse_yaml()`, replace:
```cpp
int status = std::system(cmd.c_str());
```
with `CreateProcessW()` / `WaitForSingleObject()` / `GetExitCodeProcess()`.
This avoids whatever CRT state `system()` sets that interacts with
`quick_exit`.

### Option 2: Replace `quick_exit` with `ExitProcess`

```cpp
#ifdef WIN32
    ExitProcess(::testing::UnitTest::GetInstance()->successful() ? 0 : status);
#else
    return status;
#endif
```

This bypasses `at_quick_exit` handlers entirely, which is even more aggressive
than `quick_exit` at avoiding DLL teardown issues.

### Option 3: Remove `quick_exit` entirely

```cpp
    return status;
```

If the comgr DLL teardown crash is no longer relevant (other test binaries
survive without `quick_exit`), the simplest fix is to remove the special
Windows handling entirely.

### Debugging to confirm

When the local build is ready, add before `quick_exit`:
```cpp
fprintf(stderr, "DEBUG: status=%d\n", status);
ExitProcess(status);  // test if this gives correct exit code
```

If `ExitProcess(status)` gives exit code 0 when tests pass, that confirms the
bug is in `at_quick_exit` handlers.

---

## CI Evidence

| Check | Status | Notes |
|-------|--------|-------|
| pre-commit | pass | |
| Linux Build (gfx94X) | pass | |
| Linux hipblas Test (gfx94X) | pass | All shards passed |
| Windows Build (gfx1151) | **fail** | Unrelated build step failure |
| Windows Test (gfx1151) | skipped | Skipped due to build failure |

The behavioral validation requires a successful Windows CI run. The PR body
acknowledges this, but the fix will not pass validation — `quick_exit(0)`
will still exit with code 3.

---

## Conclusion

**Approval Status: CHANGES REQUESTED**

The PR correctly identifies the symptom but the fix doesn't address the root
cause. Local testing proves that the exit code 3 comes from the interaction of
`std::system()` (in `hipblas_parse_yaml`) and `std::quick_exit()` (at process
exit), not from the `status` variable. Normalizing `status` to 0 still
produces exit code 3 because `quick_exit` itself is the source of the bad exit
code.

The fix should target either:
- `hipblas_parse_yaml`: replace `std::system()` with `CreateProcessW()`
- The exit path: replace `quick_exit` with `ExitProcess` or plain `return`
