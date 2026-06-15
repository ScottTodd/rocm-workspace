# PR Review: ROCm/TheRock #5432

* **PR:** https://github.com/ROCm/TheRock/pull/5432
* **Title:** Fix rocprofiler-sdk build by ordering it after ROCm dist artifacts
* **Reviewed:** 2026-06-01
* **Head:** `8301a63668e10febbfe2cb85a1632a104830a6a1`
* **Scope:** CMake build dependency review, with alternatives for the rocprofiler-sdk HIP test failure

## Summary

The PR adds `EXTRA_DEPENDS` from `rocprofiler-sdk` configure to `artifact-base`, `artifact-sysdeps`, `artifact-amd-llvm`, and `artifact-core-hip`.
The reported failure is real, but this is the wrong layer to fix it. `rocprofiler-sdk` already uses `COMPILER_TOOLCHAIN amd-hip`, which gives it a declared dependency on the HIP-capable toolchain path. The failure comes from the profiler test bypassing that configured toolchain and finding a raw `amd-llvm` compiler path that does not contain HIP headers.

## Overall Assessment

**CHANGES REQUESTED** - Remove the artifact-level `EXTRA_DEPENDS` and fix compiler/tool discovery instead.

## Findings

### BLOCKING: `EXTRA_DEPENDS` on artifact targets makes configure depend on the global distribution

The new dependency edge in [`profiler/CMakeLists.txt`](https://github.com/ROCm/TheRock/blob/8301a63668e10febbfe2cb85a1632a104830a6a1/profiler/CMakeLists.txt#L97-L101) waits for artifact assembly under `build/dist/rocm` before `rocprofiler-sdk+configure`. That makes a subproject configure phase depend on top-level artifact flattening, instead of on declared subproject phase dependencies.

The build-system model separates subproject `stage`/`dist` phase dependencies from top-level artifact construction. `COMPILER_TOOLCHAIN` is explicitly documented as adding an implicit compiler subproject dependency, while `EXTRA_DEPENDS` is just a raw configure dependency escape hatch. In the implementation, `EXTRA_DEPENDS` and compiler toolchain stamp deps both land on the configure command, but the compiler toolchain path uses subproject `stage.stamp` dependencies instead of artifact targets.

The current `rocprofiler-sdk` declaration already has `COMPILER_TOOLCHAIN amd-hip` and `RUNTIME_DEPS hip-clr`. In `therock_subproject.cmake`, `amd-hip` is described as the `amd-llvm` toolchain plus HIP headers/hipcc, and it adds stage-stamp dependencies for the toolchain roots. The failure is therefore not a missing artifact dependency. It is that `source/lib/tests/codeobj/CMakeLists.txt` does its own `find_program(CODEOBJ_AMDCLANGPP NAMES amdclang++)` and then invokes that compiler without an explicit `--rocm-path`.

**Required action:** drop the `EXTRA_DEPENDS` block and fix the compiler discovery/invocation path.

## Viable Fixes

### Preferred TheRock-side fix

Make `COMPILER_TOOLCHAIN amd-hip` expose its HIP-complete toolchain root to `find_program()` before inherited dependency program paths. The likely local change is in `_therock_cmake_subproject_setup_toolchain`: append init content that prepends `THEROCK_TOOLCHAIN_ROOT` program directories after `_init.cmake` injects `_private_program_dirs`, for example:

```cmake
list(PREPEND CMAKE_PROGRAM_PATH
  "${THEROCK_TOOLCHAIN_ROOT}/lib/llvm/bin"
  "${THEROCK_TOOLCHAIN_ROOT}/bin")
```

This matters because adding it only in the generated toolchain file can be superseded by the later `_init.cmake` `CMAKE_PROGRAM_PATH` injection. For `amd-hip`, `THEROCK_TOOLCHAIN_ROOT` is the `hip-clr` dist root, which should contain the compiler payload and HIP headers/device libraries through declared subproject deps. That makes the profiler project's existing `find_program(amdclang++)` resolve to the HIP-complete root instead of `build/compiler/amd-llvm/dist/lib/llvm/bin`.

### Preferred profiler-side fix

Make the codeobj test stop relying on whichever `amdclang++` appears first in CMake search paths. It should either use a cache variable/configured HIP compiler path, or derive the compiler and `clang-offload-bundler` from one selected toolchain directory, and then compile with an explicit ROCm root:

```cmake
COMMAND
  "${CODEOBJ_AMDCLANGPP}" -x hip --rocm-path="${ROCM_PATH}" ...
```

The bundler should be found relative to the selected compiler directory when possible, so the compiler and bundler come from the same toolchain. This fix is robust for TheRock and for standalone ROCm installs.

### Minimal TheRock-specific workaround

If we need a narrow unblock while the profiler project is fixed, pass explicit `CODEOBJ_AMDCLANGPP` and `CODEOBJ_OFFLOAD_BUNDLER` cache values from TheRock, pointing at the `hip-clr` dist root. That avoids top-level `build/dist/rocm`, but it still depends on the profiler code accepting pre-seeded `find_program` variables and is less general than fixing the search/invocation logic.

## CI Evidence

`gh` was not authenticated in this session, so I used public GitHub API endpoints. At review time:

* Unit tests and pre-commit succeeded.
* Windows compiler-runtime failed during `Install requirements`, before configure/build, so it does not validate this PR's behavior.
* Linux compiler-runtime was still in progress.

## Testing Recommendations

After replacing the dependency approach, validate with a clean or expunged profiler configure where `build/dist/rocm/bin/amdclang++` is absent or not yet populated:

```powershell
ninja rocprofiler-sdk+expunge
ninja rocprofiler-sdk+configure
cmake --build D:/projects/TheRock/build/profiler/rocprofiler-sdk/build --target syncthreads_kernel_bin
```

Confirm `CODEOBJ_AMDCLANGPP` resolves to the HIP-complete toolchain root, not the raw `compiler/amd-llvm/dist` root and not the top-level artifact distribution.

---

Generated by Codex.
