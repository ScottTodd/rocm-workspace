# PR Review: [AMD-SMI] Auto-detect amdclang++ as default compiler

* **PR:** [ROCm/rocm-systems#5047](https://github.com/ROCm/rocm-systems/pull/5047)
* **Author:** sumanth-gavini
* **Reviewed:** 2026-05-08
* **Context:** [TheRock#3976](https://github.com/ROCm/TheRock/issues/3976) — root out hardcoded `/opt/rocm` paths
* **State:** OPEN
* **Base:** `develop` ← `users/sumanthg/amdsmi_clang`

---

## Summary

Adds automatic compiler detection to AMD-SMI's standalone build. The detection
uses `hipconfig --path` for ROCm discovery (per #3976 recommendations), then
searches for `amdclang++` → `clang++` within the discovered ROCm path. GCC is
no longer auto-selected; users must opt in via a new toolchain file
(`cmake/toolchains/amdsmi-gcc-toolchain.cmake`). Documentation in `README.md`
and `docs/install/build.md` is updated with build requirements and
troubleshooting.

**Net changes:** +350 lines, -1 line across 4 files

---

## Overall Assessment

**⚠️ CHANGES REQUESTED** — The core approach (hipconfig-based discovery, fail
on missing ROCm compiler) is sound and well-aligned with #3976. However, there
is a correctness issue with the guard condition that can produce mixed compiler
toolchains, the CI is broken by the new FATAL_ERROR, and the PR body test
results don't match the current code.

**Strengths:**

- Uses `hipconfig --path` for tool-based ROCm discovery — no hardcoded paths in
  CMake logic
- Fails loudly with FATAL_ERROR when no ROCm compiler is found (per #3976
  principle 5: "fail loudly on misconfiguration")
- Validates compiler executability before using it
- Provides a clean GCC opt-in via toolchain file
- Respects user-provided `CMAKE_CXX_COMPILER`/`CMAKE_C_COMPILER` and
  `CMAKE_TOOLCHAIN_FILE`
- Uses `NO_DEFAULT_PATH` to avoid accidentally picking up system compilers

**Issues:**

- Guard condition uses OR — can mix compiler families (e.g., user's gcc for CXX
  + auto-detected amdclang for C)
- All standalone CI builds fail because hipconfig isn't available in CI
  containers
- PR body test results describe GCC-with-warning behavior that no longer exists
  in the code

---

## Detailed Review

### 1. CMakeLists.txt — Guard Condition

**⚠️ IMPORTANT: OR in guard allows mixed compiler toolchains**

```cmake
if(NOT CMAKE_TOOLCHAIN_FILE AND (NOT DEFINED CMAKE_CXX_COMPILER OR NOT DEFINED CMAKE_C_COMPILER))
```

If a user specifies only one compiler (e.g., `-DCMAKE_CXX_COMPILER=g++`), the
`OR` condition fires because `CMAKE_C_COMPILER` is undefined. The
auto-detection block runs and sets C_COMPILER to `amdclang` via
`set(... CACHE ...)`. The CXX cache entry isn't overwritten (already set), so
the result is GCC C++ + LLVM C — almost certainly not intended.

@oliveiradan already flagged this in review comments. The condition should use
AND:

```cmake
if(NOT CMAKE_TOOLCHAIN_FILE AND NOT DEFINED CMAKE_CXX_COMPILER AND NOT DEFINED CMAKE_C_COMPILER)
```

This way, specifying either compiler disables auto-detection entirely.

**Recommendation:** Change `OR` to `AND`.

### 2. CMakeLists.txt — Duplicated validation logic

**💡 SUGGESTION: DRY up compiler search + validation**

The amdclang search (find_program + validate) and the clang search are
structurally identical — both do find_program for CXX, find_program for C,
validate both, unset on failure. @oliveiradan also noted this. A CMake function
or macro taking the compiler name as a parameter would reduce the duplication:

```cmake
function(find_rocm_compiler COMPILER_NAME CXX_NAME C_NAME RESULT_CXX RESULT_C)
    find_program(${RESULT_CXX} NAMES ${CXX_NAME} HINTS ${_AMDCLANG_HINTS} NO_DEFAULT_PATH)
    find_program(${RESULT_C} NAMES ${C_NAME} HINTS ${_AMDCLANG_HINTS} NO_DEFAULT_PATH)
    # ... validate and unset on failure ...
endfunction()
```

### 3. CMakeLists.txt — FATAL_ERROR references `/opt/rocm`

**💡 SUGGESTION: Avoid `/opt/rocm` in error message**

The FATAL_ERROR at line ~158 suggests:
```
export PATH=$PATH:/opt/rocm/bin
```

Per #3976, even user-facing hints should avoid baking in a specific path. A more
robust suggestion:

```
Ensure hipconfig is in your PATH (from your ROCm installation's bin/ directory).
```

### 4. CMakeLists.txt — Wrong variable for verbose logging

**⚠️ IMPORTANT: `CMAKE_VERBOSE_MAKEFILE` is the wrong verbosity check**

The code gates discovery messages on `CMAKE_VERBOSE_MAKEFILE`:

```cmake
if(CMAKE_VERBOSE_MAKEFILE)
    message(STATUS "Found ROCm via hipconfig: ${ROCM_DIR}")
endif()
```

[`CMAKE_VERBOSE_MAKEFILE`](https://cmake.org/cmake/help/latest/variable/CMAKE_VERBOSE_MAKEFILE.html)
controls whether Makefile generators echo compile commands at build time — it
has nothing to do with configure-time verbosity. With `-GNinja`, this variable
is meaningless and these messages would never appear.

Since the whole point of this detection is to avoid ambiguity about which ROCm
installation is used, just always print it:

```cmake
message(STATUS "Found ROCm via hipconfig: ${ROCM_DIR}")
```

If a quieter option is wanted, use `message(VERBOSE ...)` which is controlled
by `--log-level=VERBOSE` at configure time (works with all generators).

### 5. CI — Standalone builds broken

**⚠️ IMPORTANT: All Build jobs fail due to missing hipconfig**

All 9 standalone Build jobs (Ubuntu22, RHEL9, AlmaLinux8, etc.) hit the new
FATAL_ERROR because the CI containers don't have ROCm installed (no
`hipconfig`). The "Build AMDSMI" step's exit code is silently swallowed (the
script doesn't check return codes — pre-existing CI bug), so it reports success,
but no package is generated, and the Install step fails.

Example from Build (Ubuntu22) logs:
```
CMake Error at CMakeLists.txt:158 (message):
  No suitable C++ compiler found in ROCm installation.
  Neither amdclang++ nor clang++ found in ROCm paths.
...
-- Configuring incomplete, errors occurred!
make: *** No targets specified and no makefile found.  Stop.
```

The CI needs to be updated to either:
1. Pass `-DCMAKE_CXX_COMPILER=g++ -DCMAKE_C_COMPILER=gcc`, or
2. Pass `-DCMAKE_TOOLCHAIN_FILE=../cmake/toolchains/amdsmi-gcc-toolchain.cmake`, or
3. Use containers that have ROCm installed

**Recommendation:** Update the CI build scripts to explicitly specify the
compiler when ROCm isn't available, or use the new toolchain file. Also
separately fix the build script to properly check cmake return codes.

### 6. PR body — Stale test results

**⚠️ IMPORTANT: Test 3 describes behavior that doesn't exist in the code**

The PR body's "Test Result" section shows:
```
Test 3: No clang++ (uses gcc WITH WARNING)
CMake Warning at CMakeLists.txt:69 (message):
  Neither amdclang++ nor clang++ found.  Falling back to GCC.
```

But the current code produces `FATAL_ERROR`, not a GCC fallback with warnings.
The test results appear to be from an earlier iteration of the code.

**Recommendation:** Update the PR body to reflect the current behavior (cmake
fails with an error, user is directed to the toolchain file for GCC).

### 7. Documentation — Duplication

**💡 SUGGESTION: Consolidate duplicate documentation**

`README.md` (lines 40-116) and `docs/install/build.md` (lines 30-90) contain
nearly identical content about compiler discovery, GCC toolchain usage, and
troubleshooting. This creates maintenance burden — changes need to be made in
two places.

Consider making `docs/install/build.md` the canonical source and having
`README.md` link to it, or vice versa.

### 8. Documentation — `/opt/rocm` in examples

**💡 SUGGESTION: Use placeholders in documentation examples**

Several documentation examples reference `/opt/rocm`:
- `README.md`: `export PATH=$PATH:/opt/rocm/bin`
- `docs/install/build.md`: `cmake .. -DCMAKE_CXX_COMPILER=/opt/rocm-<version_number>/lib/llvm/bin/clang++`

Given #3976 context, consider using `<rocm-install-path>` or the hipconfig
approach consistently. The `docs/install/build.md` examples with
`/opt/rocm-<version_number>` are acceptable since they show explicit
version-specific paths (demonstrating the user is intentionally choosing a
specific install), but the bare `/opt/rocm/bin` in troubleshooting should be
updated.

---

## Recommendations

### ⚠️ IMPORTANT (Should Fix):

1. **Change `OR` to `AND` in guard condition** to prevent mixed compiler
   toolchains when user specifies only one compiler
2. **Update CI build configuration** to handle the new compiler requirement
   (pass GCC explicitly or use toolchain file in containers without ROCm)
3. **Update PR body test results** to match the current FATAL_ERROR behavior
4. **Fix `CMAKE_VERBOSE_MAKEFILE` usage** — it only affects Makefile generators'
   build-time verbosity, not configure-time messages. Always print the
   discovered ROCm path, or use `message(VERBOSE ...)` with `--log-level`

### 💡 Consider:

1. Remove `/opt/rocm/bin` from FATAL_ERROR message — suggest hipconfig
   PATH instead
2. DRY up the duplicated find_program + validate pattern for amdclang vs clang
4. Consolidate duplicate documentation between README.md and build.md

### 📋 Future Follow-up:

1. Fix standalone CI build script to properly check cmake return codes (the
   current script swallows configure failures)
2. Address remaining `/opt/rocm` references in existing AMD-SMI code (e.g.,
   `LD_LIBRARY_PATH` in README.md line 37)
3. Other rocm-systems subprojects could adopt a similar hipconfig-based compiler
   discovery pattern

---

## Alignment with TheRock#3976

| Principle | Status |
|-----------|--------|
| No hardcoded absolute paths in CMake logic | ✅ Met |
| Fail loudly on misconfiguration | ✅ Met (FATAL_ERROR) |
| User-facing discovery via tool commands | ✅ Met (hipconfig --path) |
| No env var assumptions (ROCM_PATH, etc.) | ✅ Met |
| `/opt/rocm` in error messages / docs | ⚠️ Partially — some references remain |

The CMake implementation is well-aligned with #3976 principles. The remaining
`/opt/rocm` references are in user-facing documentation and error messages,
which is lower severity than programmatic paths but worth cleaning up.

---

## Prior Review Comments

@oliveiradan left several comments that are partially addressed in the current
code:

| Comment | Status |
|---------|--------|
| Validate ROCM_DIR before using in hints | ✅ Addressed (`if(ROCM_DIR)` guard) |
| Guard condition for partial compiler specification | ❌ Not yet addressed |
| `unset(... CACHE)` for find_program results | ✅ Already uses CACHE |
| Refactor duplicated validation code | ❌ Not yet addressed |
| GCC should be in toolchain file only | ✅ Addressed |

---

## Conclusion

**Approval Status: ⚠️ CHANGES REQUESTED**

The PR makes good progress toward #3976 compliance for AMD-SMI's standalone
build. The hipconfig-based discovery and FATAL_ERROR on missing compiler are
correct decisions. The main items to address are: (1) fix the guard condition to
use AND instead of OR, (2) update CI to work with the new compiler requirement,
and (3) update the stale test results in the PR body.
