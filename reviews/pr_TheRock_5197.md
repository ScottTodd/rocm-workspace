# PR Review: Add COMGR build-time unit tests to CI (re-land)

* **PR:** [#5197](https://github.com/ROCm/TheRock/pull/5197)
* **Author:** kasaurov
* **Reviewed:** 2026-05-26
* **Base:** `main`
* **Branch:** `users/kasaurov/comg-unit-tests-11`
* **Head SHA:** `2fd5548c8e7a953c3845e6e7745f7b39bd453287`

---

## Summary

This PR re-lands COMGR build-tree tests in the compiler-runtime stage. It
registers AMD COMGR LIT and CTest commands through
`therock_cmake_subproject_build_test()`, adds non-blocking `therock-build-tests`
workflow steps for Linux and Windows compiler-runtime builds, removes the old
installed `llvm-lit` wrapper logic, and keeps the minimal LLVM tool filtering
fix needed for the previous Windows offload-arch regression.

**Net changes:** +104 lines, -47 lines across 6 files.

---

## Overall Assessment

**APPROVED** - I did not find blocking or important code issues in the PR.

The build-test integration is consistent with the existing build-test
infrastructure and the previous PR #4881 review. The re-land addresses the
noted Windows offload-arch regression by no longer forcing
`CLANG_TOOL_OFFLOAD_ARCH_BUILD` off on Windows, while still avoiding a full LLVM
tool build for COMGR-only tests.

**Issues:**

- No blocking findings.
- No important findings.

---

## CI Evidence

Current PR checks from `gh pr checks` show the key compiler-runtime stage jobs
passed:

| Job | Result | Evidence |
|-----|--------|----------|
| Linux compiler-runtime stage | pass | [job 77884626170](https://github.com/ROCm/TheRock/actions/runs/26436033028/job/77884626170) |
| Windows compiler-runtime stage | pass | [job 77884627360](https://github.com/ROCm/TheRock/actions/runs/26436033028/job/77884627360) |
| pre-commit | pass | [job 77818989612](https://github.com/ROCm/TheRock/actions/runs/26436032896/job/77818989612) |
| Unit Tests, ubuntu-24.04 | pass | [job 77818989618](https://github.com/ROCm/TheRock/actions/runs/26436032894/job/77818989618) |
| Unit Tests, windows-2022 | pass | [job 77818989634](https://github.com/ROCm/TheRock/actions/runs/26436032894/job/77818989634) |

Step-level job metadata shows `Run build tests` completed successfully in both
compiler-runtime jobs:

- Linux: step 15, 2026-05-26 15:05:11Z to 15:05:24Z.
- Windows: step 19, 2026-05-26 10:06:44Z to 10:07:01Z.

CI caveat: the overall workflow run was still in progress during review, with
some packaging/test jobs pending. One Windows `Test Sanity Check` job failed
before test execution in `Run setup test environment workflow`, so that failure
does not directly implicate the COMGR build-test changes from this diff.
Logs were not available yet because GitHub reports run `26436033028` as still
in progress.

---

## Detailed Review

### Build-Test Runner

The runner change in
[`cmake/therock_subproject.cmake`](https://github.com/ROCm/TheRock/blob/2fd5548c8e7a953c3845e6e7745f7b39bd453287/cmake/therock_subproject.cmake#L1199-L1279)
preserves the important semantics from the old multi-`COMMAND` custom command:
the stamp is only touched after the runner exits successfully. The new behavior
also improves test visibility by running each configured command and reporting
a per-command summary before failing the aggregate runner if any command failed.

The command registration still uses the existing `teatime.py` prefix, so logs
and interactive CI output remain consistent with surrounding build tooling.

#### SUGGESTION: Escape generated CMake script arguments defensively

The generated script currently serializes each argument with:

```cmake
foreach(_arg IN LISTS _full_cmd)
  string(APPEND _cmd_str " \"${_arg}\"")
endforeach()
```

This is low risk for the current COMGR and rocjitsu test commands because the
arguments are controlled build-tree paths and simple flags. Still, this is a
generic helper, so a future caller with a quote or semicolon in an argument
would produce an invalid generated CMake script or split the argument. Consider
escaping CMake string/list metacharacters before appending arguments to
`_cmd_str`.

### COMGR Test Registration

[`compiler/CMakeLists.txt`](https://github.com/ROCm/TheRock/blob/2fd5548c8e7a953c3845e6e7745f7b39bd453287/compiler/CMakeLists.txt#L188-L202)
registers the COMGR LIT and CTest commands clearly. Running from the build tree
is the right model here because these tests need LLVM and COMGR build-tree
artifacts, not only staged install artifacts.

The `THEROCK_BUILD_COMGR_TESTS` defaulting pattern keeps command-line overrides
working while making COMGR test enablement follow TheRock's global
`THEROCK_BUILD_TESTING` setting.

### LLVM Tool Selection

The removal of
`-DCLANG_TOOL_OFFLOAD_ARCH_BUILD=${THEROCK_CONDITION_IS_NON_WINDOWS}` from
[`compiler/CMakeLists.txt`](https://github.com/ROCm/TheRock/blob/2fd5548c8e7a953c3845e6e7745f7b39bd453287/compiler/CMakeLists.txt#L97-L106)
and the narrowed implicit-tool condition in
[`compiler/pre_hook_amd-llvm.cmake`](https://github.com/ROCm/TheRock/blob/2fd5548c8e7a953c3845e6e7745f7b39bd453287/compiler/pre_hook_amd-llvm.cmake#L142-L175)
match the stated re-land fix: COMGR tests can request the required LLVM utility
support without forcing a full LLVM tool build, and Windows no longer loses
`offload-arch`.

### Workflow Integration

The Linux and Windows workflow steps call the aggregate `therock-build-tests`
target in the compiler-runtime stage:

- [Linux workflow](https://github.com/ROCm/TheRock/blob/2fd5548c8e7a953c3845e6e7745f7b39bd453287/.github/workflows/multi_arch_build_portable_linux_artifacts.yml#L171-L177)
- [Windows workflow](https://github.com/ROCm/TheRock/blob/2fd5548c8e7a953c3845e6e7745f7b39bd453287/.github/workflows/multi_arch_build_windows_artifacts.yml#L193-L199)

Keeping this as a separate non-blocking step is reasonable for the bring-up
phase. It keeps build/artifact failures distinct from test failures and avoids
blocking artifact upload while the new test lane is being stabilized.

#### SUGGESTION: Refresh stale PR description text

The PR body says `configure_stage.py` sets `-DTHEROCK_BUILD_TESTING=ON` for
`compiler-runtime`, but the current PR does not modify `configure_stage.py`, and
the base/head copies I checked do not contain that logic. The tests are enabled
through the normal top-level `BUILD_TESTING`/`THEROCK_BUILD_TESTING` defaulting
path. This is not a code issue, but updating the PR description would make the
re-land evidence easier to verify.

---

## Testing Recommendations

Before merge, wait for the remaining CI jobs in run
[`26436033028`](https://github.com/ROCm/TheRock/actions/runs/26436033028) to
complete or document why any remaining failures are unrelated. Once the run
completes, inspect the compiler-runtime job logs for the `Run build tests`
steps, because `continue-on-error: true` can make step metadata less explicit
than the underlying COMGR LIT/CTest summary.

---

## Conclusion

**Approval Status: APPROVED**

No blocking changes are needed from the code review. The only follow-ups I
recommend are refreshing stale PR-body text and, after the workflow run
finishes, checking the build-test logs directly to confirm the pass counts
claimed in the PR description.
