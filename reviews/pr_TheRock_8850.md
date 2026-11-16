# PR review: ROCm/TheRock 8850

- PR: https://github.com/ROCm/TheRock/pull/8850
- Reviewed head: `21ae6b176cfeec7977a06b80639d80134ea138c5`
- Base: `1e21477a5ca2ac34ffcf4e80b2955e46ddaa9f09`
- Reviewed: 2026-11-16
- Assessment: **CHANGES REQUESTED**

## Findings

### BLOCKING: Linux runtime bitcode disappears from the artifacts

The new cache loaded by [compiler/CMakeLists.txt:129](https://github.com/ROCm/TheRock/blob/21ae6b176cfeec7977a06b80639d80134ea138c5/compiler/CMakeLists.txt#L129) changes the device runtime triple from `amdgcn-amd-amdhsa` to `amdgpu-amd-amdhsa`. However, [artifact-amd-llvm.toml:21](https://github.com/ROCm/TheRock/blob/21ae6b176cfeec7977a06b80639d80134ea138c5/compiler/artifact-amd-llvm.toml#L21) still includes only `lib/llvm/lib/amdgcn-amd-amdhsa/*.bc`.

This is confirmed in the actual PR artifacts, rather than just inferred from the diff:

| File below `lib/llvm/lib/<device-triple>/` | Base bytes | PR artifact |
| --- | ---: | --- |
| `libc.bc` | 624,584 | Missing |
| `libm.bc` | 976,956 | Missing |
| `libomptarget-amdgpu.bc` | 364,884 | Missing |

The [PR install log](https://therock-ci-artifacts.s3.amazonaws.com/43926744873-linux/logs/compiler-runtime/amd-llvm_install.log) explicitly installs all three under `amdgpu-amd-amdhsa`. None appears in the PR `lib`, `dev`, or `run` archive inventory. The remaining `dbg` and `doc` archives are only 201 and 3,567 bytes, respectively. The base `lib` archive contains all three. These are runtime bitcode inputs, so removing them breaks consumers requiring the GPU libc/libm or OpenMP device library. The reduction in archive size is not a successful size optimization.

**Required action:** Update the descriptor to collect the new device directory, preserving any old paths that must remain supported. Verify the resulting published artifacts contain all three files, and exercise GPU OpenMP compilation against an artifact installation.

### BLOCKING: `THEROCK_COMPILER_RT_DEBUG` stops reaching Linux host compiler-rt

[compiler/CMakeLists.txt:159](https://github.com/ROCm/TheRock/blob/21ae6b176cfeec7977a06b80639d80134ea138c5/compiler/CMakeLists.txt#L159) retains the top-level `-DCOMPILER_RT_DEBUG=${THEROCK_COMPILER_RT_DEBUG}` argument, but the new cache replaces the host `default` runtime target with `x86_64-unknown-linux-gnu`.

In the pinned LLVM source, [`runtime_default_target()`](https://github.com/ROCm/llvm-project/blob/e974ae2ed2371d30b10a5852710f5631e2545ce9/llvm/runtimes/CMakeLists.txt#L286) passes the runtime option prefixes to its ExternalProject. [`runtime_register_target()`](https://github.com/ROCm/llvm-project/blob/e974ae2ed2371d30b10a5852710f5631e2545ce9/llvm/runtimes/CMakeLists.txt#L381) instead forwards `RUNTIMES_<triple>_*` options. The cache translates several other options into that namespace, but not this one. The new [Linux configure log](https://therock-ci-artifacts.s3.amazonaws.com/43926744873-linux/logs/compiler-runtime/amd-llvm_configure.log) lists `COMPILER_RT_DEBUG` as unused; the base configure log does not.

Default release CI uses `OFF`, so it does not reveal the user-visible failure: setting `THEROCK_COMPILER_RT_DEBUG=ON` no longer enables debug mode for the host compiler-rt runtime build. The new separately registered builtins also need their own forwarding if this toggle is intended to cover them.

**Required action:** Pass the option through the appropriate `RUNTIMES_<host>_COMPILER_RT_DEBUG` and `BUILTINS_<host>_COMPILER_RT_DEBUG` settings. Check the generated child configure arguments with the toggle `ON`, on Linux and Windows.

### IMPORTANT: The existing all-tools option no longer builds all tools

[compiler/CMakeLists.txt:108](https://github.com/ROCm/TheRock/blob/21ae6b176cfeec7977a06b80639d80134ea138c5/compiler/CMakeLists.txt#L108) maps `THEROCK_BUILD_LLVM_TOOLS=ON` to `LLVM_INCLUDE_TESTS=ON`, which removes the cache's tool allow-list. However, [the new build command](https://github.com/ROCm/TheRock/blob/21ae6b176cfeec7977a06b80639d80134ea138c5/cmake/therock_subproject.cmake#L1139) builds only the selected distribution targets. Enabling a tool in CMake does not add it to a distribution.

For example, `llc`, `lli`, and `llvm-size` are not in the pinned cache's [tools distribution](https://github.com/ROCm/llvm-project/blob/e974ae2ed2371d30b10a5852710f5631e2545ce9/clang/cmake/caches/ROCm.cmake#L320). Previously the ordinary default build built all enabled tools. With the new default distribution list, these tools are neither requested by the all-tools flag nor staged. This finding is based on target construction; the supplied CI uses the flag's default `OFF` and does not test this case.

**Recommendation:** Preserve the existing option's documented behavior by selecting the full build/install path when it is enabled, or by expanding the relevant distribution components. Verify representative tools such as `llc` are built and installed with the option `ON`.

## Comparison method

The baseline is [main run 43739303240](https://github.com/ROCm/TheRock/actions/runs/43739303240), whose head is the PR's exact base commit. The comparison run is [PR run 43926744873](https://github.com/ROCm/TheRock/actions/runs/43926744873). Both have successful Linux and Windows compiler-runtime stage jobs. Both Linux logs check out the same LLVM commit, `e974ae2ed2371d30b10a5852710f5631e2545ce9`, and SPIR-V translator commit, `cc8292cfc48d8e6e4e8f9b488f4a1e21790fafbd`.

I compared authenticated GitHub job logs, public S3 configure/install logs, exact HTTP Content-Length values, and archive member inventories and hashes. No source checkout was changed and no full ROCm build was run. This is a comparison of the published release CI configurations; ASAN, other host architectures, and nondefault distribution combinations were not built locally.

## Effective CMake configuration

**The configurations are not identical.** There is no uploaded complete `CMakeCache.txt` in the inspected log indexes, so this is not a claim of an exhaustive cache-entry diff. The table combines actual configure commands and build/install output with the cache and runtime forwarding code at the pinned LLVM revision. It separates effective changes from renamed or relocated settings.

| Setting/behavior | Before | After | Scope/impact |
| --- | --- | --- | --- |
| Build and installation targets | Default build; full `cmake --install` | Selected `*-distribution` and `install-*-distribution` targets | Both platforms; changes build/install membership |
| Default staged distributions | Not used | Linux: `compiler;runtimes;dev;tools;fortran;utils`; Windows omits `fortran` | `multilibs` is disabled by default |
| `LLVM_RUNTIME_TARGETS` | `default;amdgcn-amd-amdhsa` | `x86_64-unknown-linux-gnu;amdgpu-amd-amdhsa` | Linux; changes child configuration forwarding and installed device paths |
| `LLVM_BUILTIN_TARGETS` | Default builtins configuration | Explicit host and device triples | Linux; builtins configured separately per target |
| `LLVM_RUNTIME_MULTILIBS` | Unset | `debug;asan;debug+asan` | Linux; configured definitions, not staged by the default distribution selection |
| `LLVM_OPTIMIZED_TABLEGEN` | Upstream default `OFF` | Cache sets `ON` | Both; generally neutral for the ordinary Release build without assertions |
| `CLANG_TOOL_CLANG_SCAN_DEPS_BUILD` | `OFF` on Linux | `ON` | Linux; option enabled, but the tools distribution only installs it on Windows |
| Host runtime libc++/libc++abi options, sanitizer includes, libomp RPATH, libomptarget options | Top-level/default runtime forwarding | `RUNTIMES_<host>_*` cache entries | Most are deliberate equivalent translations; debug toggle is missed as noted above |
| `COMPILER_RT_DEBUG` | Reaches the default host runtime build | Top-level argument unused on Linux | Regression when enabled |
| `LLVM_INCLUDE_TESTS` in supplied CI | Empty/false | Explicit `OFF` | Same boolean behavior in these runs |
| LLVM/Clang projects and runtime lists | Platform-specific project/runtime sets | Same sets, reordered | Linux retains Flang, MLIR, OpenMP, offload, flang-rt and libc family; Windows retains clang/lld/clang-tools-extra and compiler-rt |
| `LLVM_TARGETS_TO_BUILD` | `AMDGPU;Native;SPIRV` | `Native;AMDGPU;SPIRV` | Same target set |
| `CLANG_ENABLE_ARCMT` | Explicit `OFF` | Removed | Pinned Clang defaults the replacement `CLANG_ENABLE_OBJC_REWRITER` to `OFF`; removes deprecation warning |
| `CLANG_ENABLE_CIR` | Explicit `OFF` on Windows | Uses pinned upstream default `OFF` | No CIR enablement in these runs |
| Build type, benchmarks, examples, static analyzer, clangd, zlib, Z3, libxml2, default linker/rtlib/unwindlib | Release and existing restrictions/defaults | Equivalent settings from cache | No evidence of a broad compiler feature or optimization-level change |

The default `run` archive membership on Linux is unchanged. LLVM package export files change from monolithic names such as `LLVMExports.cmake` to distribution-specific names such as `LLVMdevExports.cmake`; the package config files are updated accordingly. Device headers, static libraries, and Fortran modules move to the new triple directory.

## Exact compressed artifact sizes

Bytes below are HTTP Content-Length values, not the rounded MB labels in the HTML indexes. `amd-llvm` also packages the separately built comgr and hipcc stages.

| Platform | Component | Base bytes | PR bytes | Delta bytes |
| --- | --- | ---: | ---: | ---: |
| Linux | `dbg` | 201 | 201 | 0 |
| Linux | `dev` | 244,342,457 | 244,377,279 | +34,822 |
| Linux | `doc` | 3,596 | 3,567 | -29 |
| Linux | `lib` | 212,462,262 | 211,510,270 | -951,992 |
| Linux | `run` | 65,732,708 | 65,732,514 | -194 |
| **Linux** | **Total** | **522,541,224** | **521,623,831** | **-917,393 (-0.1756%)** |
| Windows | `dbg` | 193 | 193 | 0 |
| Windows | `dev` | 186,747,672 | 186,774,717 | +27,045 |
| Windows | `doc` | 194 | 192 | -2 |
| Windows | `lib` | 109,091,308 | 109,091,349 | +41 |
| Windows | `run` | 695,119,522 | 695,119,457 | -65 |
| **Windows** | **Total** | **990,958,889** | **990,985,908** | **+27,019 (+0.00273%)** |

Indexes: [base Linux](https://therock-ci-artifacts.s3.amazonaws.com/43739303240-linux/index.html), [PR Linux](https://therock-ci-artifacts.s3.amazonaws.com/43926744873-linux/index.html), [base Windows](https://therock-ci-artifacts.s3.amazonaws.com/43739303240-windows/index.html), [PR Windows](https://therock-ci-artifacts.s3.amazonaws.com/43926744873-windows/index.html).

### Uncompressed sizes and what changed

These values are the packaging jobs' `uncompressed_size` measurements, which count file paths before tar hardlink deduplication. They therefore differ from the sum of regular-file payload sizes in the tar inventories.

| Platform | Component | Base bytes | PR bytes | Delta bytes |
| --- | --- | ---: | ---: | ---: |
| Linux | `lib` | 1,756,057,419 | 1,754,155,171 | -1,902,248 |
| Linux | `dev` | 2,116,861,605 | 2,116,890,120 | +28,515 |
| Linux | `run` | 499,956,922 | 499,956,954 | +32 |
| Windows | `lib` | 346,328,005 | 346,328,005 | 0 |
| Windows | `dev` | 1,198,416,316 | 1,198,443,497 | +27,181 |
| Windows | `run` | 2,055,484,986 | 2,055,484,986 | 0 |

- Linux: the three missing bitcode files account for **1,966,424 uncompressed bytes removed**. Small runtime-library changes offset part of that decrease. At unchanged paths, only one `run` member changes: `llvm-omp-kernel-replay`, from 116,624 to 116,656 bytes. Core compiler executables do not grow. Development changes are export/config metadata and device-directory renames; static development libraries retain their content across the directory rename.
- Windows: `lib` and `run` have exactly the same uncompressed sizes and packaging file counts before/after. Every `run` member is identical, including file hashes and link metadata. The development payload increase is CMake export/configuration metadata, rather than larger compiler libraries. Equal sizes do not mean all library files are byte-identical: 15 `lib` members and many development libraries have different hashes at unchanged sizes.
- `dbg` and `doc` are tiny in these runs. Their compression fluctuations do not indicate a compiler feature change.

## CI status and validation limits

All PR checks were inspected, not only the linked release run. Both release compiler-runtime stages and the Linux ASAN compiler-runtime stage pass. The visible failure is the `therock-pr-bot` aggregate job; the PR discussion includes a pre-commit-failed marker, while the separately listed `pre-commit` check passes. Many downstream jobs are still pending, and the bot status is not evidence of a compiler build failure. Unit-test and security checks are successful.

Existing passing HIP/library tests do not establish GPU OpenMP artifact completeness. Before merge, validate the three missing bitcode members, compiler-rt debug forwarding with the option enabled, and representative all-tools outputs.

## Evidence and reproduction

All downloaded evidence and helper scripts are under `D:/scratch/codex/pr8850/`:

- `pr.diff`, `compiler-head.cmake`, `pre-base.cmake`, `ROCm.cmake`, `TheRock.cmake`: reviewed source snapshots.
- `{base,pr}-{linux,windows}-job.log`: authenticated GitHub stage logs.
- `{43739303240,43926744873}-{linux,windows}-{configure,install}.log`: S3 logs.
- `*.headers`: exact object-size headers; `*.tar.zst`: downloaded archives.
- `compare_archives.py`, `*.tar.json`, `archive-comparison.json`, `archive-comparison.txt`: streaming inventories, per-file SHA-256 hashes, and comparison output. No archive extraction is required.
- `checks.json`, `checks-latest.json`, `bot.log`, `discussion.json`: CI and discussion evidence.

Representative commands used (substitute the run, platform, and component to reproduce the complete matrix):

```powershell
gh pr view 8850 --repo ROCm/TheRock --json title,body,files,headRefOid,baseRefOid,commits
gh pr diff 8850 --repo ROCm/TheRock
gh pr checks 8850 --repo ROCm/TheRock --json name,state,link
gh api repos/ROCm/TheRock/actions/jobs/133509707093/logs
gh api repos/ROCm/TheRock/actions/jobs/132888940523/logs
curl.exe -fsSI https://therock-ci-artifacts.s3.amazonaws.com/43926744873-linux/amd-llvm_lib_generic.tar.zst
curl.exe -fsSL https://therock-ci-artifacts.s3.amazonaws.com/43926744873-linux/logs/compiler-runtime/amd-llvm_install.log
D:/projects/TheRock/.venv/Scripts/python.exe D:/scratch/codex/pr8850/compare_archives.py
```

Full command output is retained in the files listed above. This review was not posted to GitHub.

Generated with Codex.
