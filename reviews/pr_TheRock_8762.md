# Review: unified hipCCL build

- PR: [ROCm/TheRock 8762](https://github.com/ROCm/TheRock/pull/8762), head `c12a41b8969e77911e7cc7aa836673d9c4d2096e`.
- Compared [PR release run 37667630158](https://github.com/ROCm/TheRock/actions/runs/37667630158) with [baseline 37620849077](https://github.com/ROCm/TheRock/actions/runs/37620849077), head `4c6a8039190e9b267bdd93743c01d2686996bdfa`.
- Reviewed October 7, 2026. PR release testing was still waiting on sanity when inspected; baseline overall conclusion is failure, although the relevant builds and prim tests passed.
- Both runs pin rocm-libraries to `9db047704895e1afbe7235e925f3280d5e28e049`. This controls component revision drift, but changing from standalone sources to the copied hipccl3 sources still changes implementation/version content.

## Overall assessment: CHANGES REQUESTED

The unified inner Ninja build can compile the components concurrently, and the expensive tests remain separate from the header install. However, the shared install directory silently loses/replaces benchmarks, and the coverage replacement mapping is incorrect. There are also downstream compatibility changes and an unnecessary dependency on rocRAND.

## Findings

### BLOCKING: colliding benchmark filenames silently change what the artifact tests

The shared [hipCCL_tests stage](https://github.com/ROCm/TheRock/blob/c12a41b8969e77911e7cc7aa836673d9c4d2096e/math-libs/CMakeLists.txt#L157) and [benchmark artifact selector](https://github.com/ROCm/TheRock/blob/c12a41b8969e77911e7cc7aa836673d9c4d2096e/math-libs/artifact-prim.toml#L13) put both rocPRIM and hipCUB benchmarks in the same `bin/` directory. Upstream prefixes hipCUB CMake target names but preserves the colliding installed names through [OUTPUT_NAME and rocm_install](https://github.com/ROCm/rocm-libraries/blob/9db047704895e1afbe7235e925f3280d5e28e049/projects/hipccl/hipccl3/hipcub/benchmark/CMakeLists.txt#L106).

The actual Linux gfx942 install log contains **26 duplicate benchmark destinations**. Thirteen later hipCUB installs overwrite rocPRIM; thirteen report `Up-to-date`, retaining rocPRIM. Thus only one implementation survives at each shared name, with a mixture of component ownership.

Concrete binary evidence:

| Installed name | Baseline | PR |
|---|---|---|
| `bin/benchmark_device_reduce` | 3,031,936 bytes; hipCUB `reduce_benchmark` / `sum_kernel` classes | 1,123,200 bytes; rocPRIM `device_reduce_benchmark` class and rocPRIM source path |

This is a silent behavioral replacement, not a size optimization. A benchmark runner invoking the old filename now measures a different library. Before the PR, the descriptor excluded rocPRIM benchmarks and shipped the hipCUB copy.

**Required action:** assign distinct installed names or directories to both sets, update packaging/runners, and check destination uniqueness. Changing install order cannot preserve both binaries. Evidence: [PR install log](https://therock-ci-artifacts.s3.amazonaws.com/37667630158-linux/logs/math-libs/gfx94X-dcgpu/hipCCL_tests_install.log), downloaded baseline/PR archives, and local `check-benchmark-collision.py` reproduction.

### BLOCKING: coverage replacement now skips all prim test executables

The [new COMPONENT_MAP values](https://github.com/ROCm/TheRock/blob/c12a41b8969e77911e7cc7aa836673d9c4d2096e/build_tools/install_rocm_code_coverage_build.py#L60) use `hipCCL` as the replacement selector. But [replace_instrumented_libraries](https://github.com/ROCm/TheRock/blob/c12a41b8969e77911e7cc7aa836673d9c4d2096e/build_tools/install_rocm_code_coverage_build.py#L224) strips the stage prefix before matching this selector against the installed path. It does not match the subproject directory.

Against the actual Linux inventories, the old `hipCUB[^a-zA-Z]` selector matches 51 regular test-artifact files; the new `hipCCL[^a-zA-Z]` selector matches **zero**. Conversely it matches 1,312 development files, including every component's relocated headers. Requesting a component replacement therefore replaces all components' headers while leaving the test binaries uninstrumented.

**Required action:** retain component-aware installed-path matching, or deliberately replace the complete unified artifact with explicit semantics. Validate selection of instrumented executables as well as headers. Some old component matching was already incomplete; the concrete new regression is losing the previously matched hipCUB paths.

### IMPORTANT: unnecessary rocRAND dependency delays header consumers

[hipCCL BUILD_DEPS](https://github.com/ROCm/TheRock/blob/c12a41b8969e77911e7cc7aa836673d9c4d2096e/math-libs/CMakeLists.txt#L137) adds rocRAND to the header-only build. Dependency staging gates configure, so rocSPARSE, rocSOLVER, and prim tests now wait for rocRAND, including its tests/benchmarks. rocALUTION already waited for rocRAND.

The copied rocThrust [rocRAND dependency is benchmark-only](https://github.com/ROCm/rocm-libraries/blob/9db047704895e1afbe7235e925f3280d5e28e049/projects/hipccl/hipccl3/rocthrust/cmake/Dependencies.cmake#L423); the header target does not build benchmarks. Keep rocRAND on `hipCCL_tests`, remove it from `hipCCL`, and verify the header-only configure. See timing analysis below for measured impact and limits.

### IMPORTANT: installed headers and versioned package discovery have breaking changes

The [source switch](https://github.com/ROCm/TheRock/blob/c12a41b8969e77911e7cc7aa836673d9c4d2096e/math-libs/CMakeLists.txt#L124) and [Windows symlink disable](https://github.com/ROCm/TheRock/blob/c12a41b8969e77911e7cc7aa836673d9c4d2096e/math-libs/CMakeLists.txt#L113) have observable consumer consequences:

- All 1,310 headers move under `include/hipccl/{rocprim,hipcub,thrust}`. Linux preserves legacy include paths with three symlinks; Windows has no replacements. Direct compiler consumers using only `-I<prefix>/include` lose the previously valid include paths. Exported CMake targets do supply `include/hipccl`.
- rocPRIM changes from 4.8.0 to 5.0.0. The actual installed version file uses SameMajorVersion: a CMake reproduction with `PACKAGE_FIND_VERSION=4.8` reports compatible on baseline and incompatible on PR. Thus `find_package(rocprim 4.8 REQUIRED CONFIG)` changes behavior even though unversioned discovery works.

**Recommendation:** preserve compatibility for this migration, or explicitly document and coordinate these breaking changes. The description's claim that downstream discovery is unchanged needs qualification. Test direct Windows includes and versioned package discovery in addition to in-tree consumers.

## Build graph, timing, and parallelism

The relevant graph changes from:

```text
hip-clr → rocPRIM headers → rocPRIM_tests / hipCUB / rocSPARSE / rocSOLVER
                       ↘ rocThrust ← rocRAND
```

to:

```text
hip-clr → rocRAND, including clients → hipCCL headers
                                      ├─ hipCCL_tests: rocPRIM + hipCUB + rocThrust
                                      ├─ rocSPARSE
                                      └─ rocSOLVER
```

These diagrams show the changed edges, not every dependency. The three old test builds become one background subprocess. `BACKGROUND_BUILD` controls the outer Ninja job pool; it does not serialize compiler jobs inside that subprocess. The inner Ninja contains ready work from all three components.

Measured header staging, seconds from the outer math-library Ninja start:

| Header provider | Linux baseline → PR | Windows baseline → PR |
|---|---:|---:|
| rocPRIM | 4.72 → 16.11 | 48.94 → 119.16 |
| hipCUB | 14.49 → 16.11 | 113.49 → 119.16 |
| rocThrust | 34.99 → 16.11 | 504.11 → 119.16 |

The old hipCUB/rocThrust stages included their tests and benchmarks, so the split improves rocThrust header availability even while delaying rocPRIM. PR hipCCL configure starts immediately after rocRAND stages at 10.89 s on Linux and 64.76 s on Windows.

There is also a larger combined configuration barrier before test compilation: `hipCCL_tests` configure takes 28.36 s on Linux and 359.12 s on Windows. Previously each independent project could start compiling once its own configure finished (rocThrust configure alone took 20.78 / 161.67 s). Combining builds improves the scope of the inner scheduling queue but requires all component configuration to finish first. Neither this barrier nor the dependency delay should be hidden by the successful build result.

### Matched CI Build stage step durations

These exclude checkout, artifact download, and upload. Every listed build passed. They are measurements from one pair of runs, not a controlled cold-build benchmark.

| Platform / target family | Baseline | PR | Delta |
|---|---:|---:|---:|
| Linux gfx110X-all | 15:13 | 16:21 | +1:08 (+7.4%) |
| Linux gfx125X-dcgpu | 12:01 | 13:25 | +1:24 (+11.7%) |
| Linux gfx120X-all | 15:22 | 17:33 | +2:11 (+14.2%) |
| Linux gfx94X-dcgpu | 41:46 | 43:58 | +2:12 (+5.3%) |
| Linux gfx1151 | 4:42 | 6:27 | +1:45 (+37.2%) |
| Windows gfx110X-all | 48:38 | 59:05 | +10:27 (+21.5%) |
| Windows gfx1151 | 29:16 | 33:23 | +4:07 (+14.1%) |
| Windows gfx120X-all | 89:14 | 89:42 | +0:28 (+0.5%) |

### Achieved parallelism and critical path

From the archived inner Ninja logs (deduplicating multi-output commands):

| Prim build | Baseline command span | PR command span | PR peak concurrent commands | PR mean concurrent commands |
|---|---:|---:|---:|---:|
| Linux gfx942 | hipCUB 1.15 s; rocPRIM_tests 0.72 s; rocThrust 2.06 s | unified 280.45 s | 98 | 44.6 |
| Windows gfx110X | hipCUB 10.12 s; rocPRIM_tests 12.19 s; rocThrust 220.88 s | unified 1,434.81 s | 95 | 31.5 |

The baseline spans are separate builds and may overlap; their sum is not a baseline critical-path duration. Concurrency counts include compilation, linking, and other Ninja commands and are **not CPU-utilization percentages**.

There is direct evidence of cross-component overlap inside the unified build. On Linux, relative to its inner Ninja start, rocPRIM commands span 0.07–280.46 s, hipCUB 15.33–207.50 s, and rocThrust 35.10–190.91 s. On Windows the corresponding ranges are 0.35–1,434.85 s, 39.33–1,227.06 s, and 114.24–767.20 s. Configuration order therefore does not serialize component compilation.

The tail contains expensive individual rocPRIM benchmark compilations: Linux `benchmark_device_select.cpp.o` takes 268.25 s; Windows `benchmark_device_segmented_radix_sort_pairs.cpp.obj` takes 1,397.05 s. More ready work early in the build does not eliminate these long final commands.

Nevertheless **hipCCL_tests is not the full math-stage critical bottleneck in either inspected trace**. It ends at about 325 s into the Linux stage, whose Ninja finishes at 2,638 s; hipSPARSELt lasts until about 2,634 s. On Windows gfx110X it ends at 1,913 s, versus a 3,545 s stage, with rocSPARSE still building until about 3,367 s. The unified test target does not gate downstream header consumers.

Cache state dominates the before/after prim difference: baseline Linux commands complete in fractions of a second from warmed compiler caches, whereas PR commands include long compilation work. Whole-stage ccache hit rates are 96.98% → 95.39% on Linux and 96.50% → 94.75% on Windows. Runner CPU models match within each pair (Linux EPYC 9R45; Windows EPYC 9R14), but this remains a single warm-cache comparison with changed source paths/content. It cannot isolate steady-state or cold-build scheduling efficiency. The observed stage slowdown is real; attributing all of it to combining the build would be unsupported.

Evidence: [PR Linux Ninja archive](https://therock-ci-artifacts.s3.amazonaws.com/37667630158-linux/logs/math-libs/gfx94X-dcgpu/ninja_logs.tar.gz), [baseline Linux](https://therock-ci-artifacts.s3.amazonaws.com/37620849077-linux/logs/math-libs/gfx94X-dcgpu/ninja_logs.tar.gz), [PR Windows gfx110X](https://therock-ci-artifacts.s3.amazonaws.com/37667630158-windows/logs/math-libs/gfx110X-all/ninja_logs.tar.gz), [baseline Windows](https://therock-ci-artifacts.s3.amazonaws.com/37620849077-windows/logs/math-libs/gfx110X-all/ninja_logs.tar.gz). Parsed command intervals and analysis code are retained under `D:/scratch/codex/pr8762/timing/`.

## Binary and artifact size comparison

The libraries are header-only: there is no new production `prim` shared-library payload. Most growth is test/benchmark content. Sizes below are summed regular-file payload bytes expressed in MiB (1,048,576 bytes), excluding tar padding. GPU-specific test archives contain the split GPU-code payload and must be counted in addition to generic host files.

| Artifact | Baseline MiB | PR MiB | Delta MiB |
|---|---:|---:|---:|
| Linux `prim_dev_generic` | 12.493 | 12.505 | +0.013 |
| Linux `prim_test_generic` | 1,944.201 | 2,059.198 | +114.997 |
| Linux `prim_test_gfx942` | 64.818 | 72.836 | +8.019 |
| **Linux generic + gfx942 tests** | **2,009.019** | **2,132.034** | **+123.015 (+6.12%)** |
| Windows `prim_dev_generic` | 12.800 | 12.813 | +0.013 |
| Windows `prim_test_generic` | 1,024.991 | 1,078.344 | +53.353 |
| Windows `prim_test_gfx1200` | 52.807 | 60.434 | +7.627 |
| Windows `prim_test_gfx1201` | 53.730 | 61.740 | +8.010 |
| **Windows generic + gfx1200/gfx1201 tests** | **1,131.527** | **1,200.518** | **+68.991 (+6.10%)** |

Compressed test downloads grow **270.259 → 294.199 MiB** for Linux generic+gfx942 (+23.940 MiB), and **298.795 → 320.845 MiB** for Windows generic+gfx1200/gfx1201 (+22.050 MiB). Development archives become slightly smaller compressed despite slightly larger extracted content; compressed size alone is not a code-size metric.

Linux generic test growth decomposes into:

- 31 added rocPRIM benchmark filenames: **110,173,312 bytes (105.07 MiB)**.
- All benchmark binaries together: **+120,073,344 bytes**; this includes changes/replacements at existing names and is affected by the collision bug.
- `bin/test_*` binaries: **+444,672 bytes**.
- `.hip` example binaries: **+64,384 bytes**.
- Small remaining changes are metadata/helper content.

Windows has the same 31 added names, totaling **55,855,616 bytes**; all benchmarks grow by **55,864,320 bytes**, `bin/test_*` by **20,992 bytes**, and `.hip.exe` examples by **59,392 bytes**. These are shipped host-file sizes after GPU-code splitting, not total per-executable device-code sizes.

Generic artifact keys are shared by architecture jobs. Downloaded Linux generic files match the gfx94 job's upload; Windows generic files match the final gfx120 job's upload, confirmed by compressed byte sizes and logs. The Windows gfx110 job's generic contents have slightly different byte totals, so this table consistently uses the gfx120 versions. Do not sum generic content once per architecture.

Evidence: [Linux PR build/upload log](https://github.com/ROCm/TheRock/actions/runs/37667630158/job/112958213252), [Linux baseline](https://github.com/ROCm/TheRock/actions/runs/37620849077/job/112794458539), [Windows PR gfx120](https://github.com/ROCm/TheRock/actions/runs/37667630158/job/112964050181), [Windows baseline gfx120](https://github.com/ROCm/TheRock/actions/runs/37620849077/job/112797513772). Generic dev/test archives were downloaded and inventoried; GPU-specific sizes come from their upload logs.

## Included/excluded files of note

1. **No test-artifact relative filenames removed:** Linux 552 → 583 regular files; Windows 386 → 417. All 31 additions are rocPRIM benchmarks. Filename preservation does not imply semantic preservation: the collision finding demonstrates existing benchmark names changing implementation.
2. **Headers relocate without being dropped:** after normalizing the `include/hipccl/` relocation, both contain 1,310 headers. SHA-256 comparison finds exactly three changed headers: `rocprim_version.hpp` and rocThrust's `hipstdpar/impl/interpose_allocations_v0.hpp` / `interpose_allocations_v1.hpp`. The latter changes are substantive source differences, not packaging effects.
3. **New umbrella CMake files:** `lib/cmake/hipccl/hipccl-config.cmake` and `hipccl-config-version.cmake`. Existing component configs remain and point to the relocated includes; hipCUB/rocThrust target exports gain checks for the exported rocPRIM target.
4. **Licenses consolidate:** `share/doc/rocprim/LICENSE.md`, `share/doc/hipcub/LICENSE.txt`, and `share/doc/rocthrust/LICENSE` become `share/doc/hipccl/LICENSE`. Linux license payload changes from 12,925 to 13,504 bytes. This is a path/consolidation change, not disappearance of the license payload.
5. **CTest registrations preserved:** Linux archive comparison finds identical registered-name sets, including seed variants: hipCUB 196, rocPRIM 356, rocThrust 668. Resource helpers and component CTest files remain. This proves registration preservation, not successful execution.
6. **Debug archives remain empty in both release runs.** Separately, the new descriptor only lists `hipCCL/stage` for dbg, while binaries move to `hipCCL_tests/stage`. Add coverage of that stage for configurations producing split debug files; the release comparison cannot validate that case.

## Test behavior and validation limits

The PR release configure log explicitly selects rocPRIM, hipCUB, and rocThrust. Their jobs are held behind the [queued sanity job](https://github.com/ROCm/TheRock/actions/runs/37667630158/job/113007340377); their absence is not a selection regression. The runs also use different test workloads: **baseline standard, PR quick**. Eventual quick-mode runtimes will not establish parity with baseline standard-mode runtimes.

| Baseline Linux gfx94X suite | CTest entries passed | CTest wall time |
|---|---:|---:|
| rocPRIM shard 1/2 | 45 | 446.93 s |
| rocPRIM shard 2/2 | 44 | 631.84 s |
| hipCUB | 49 | 514.11 s |
| rocThrust | 167 | 535.42 s |

These are CTest entries, not individual GTest cases. Baseline also passes the three suites on Linux gfx90a/gfx950 and Windows gfx110X. Registered-name counts above are larger because they include additional seed variants before CI filtering/sharding.

The separate [PR ASAN run](https://github.com/ROCm/TheRock/actions/runs/37667629817) fails all three prim suites **before test execution**: each `generate_resource_spec` helper cannot load `libclang_rt.asan.so`. Other projects encounter the same runtime-loading failure, so it is not established as a consolidation regression. All 37 failing ASAN job-log endpoints were inspected: 28 were available and nine returned authenticated `BlobNotFound`; failures also include unrelated timeouts, missing files, and ASAN findings. They should not be attributed en masse to this PR.

Relevant validation: run the same standard suites as baseline after addressing packaging; check installed benchmark identity/uniqueness, direct Windows includes, versioned CMake discovery, instrumented replacement, and split-debug packaging. The added selector-normalization test is useful but cannot cover these artifact behaviors. Full local builds/GPU tests were not run; the review used the completed CI builds, downloaded artifacts, Ninja logs, source inspection, and targeted CMake/binary-inventory reproductions.

## Reproduction and retained evidence

Evidence and scripts are under `D:/scratch/codex/pr8762/`, including `pr.diff`, run/job JSON, full downloaded job logs, archive inventories, normalized diffs, `graph-review.md`, `test-review.md`, `failure-summary-complete.txt`, and timing analysis.

Representative exact commands:

```powershell
gh pr view 8762 --repo ROCm/TheRock --json number,title,author,body,files,baseRefName,headRefName,headRefOid
gh pr diff 8762 --repo ROCm/TheRock
gh pr checks 8762 --repo ROCm/TheRock
gh api 'repos/ROCm/TheRock/actions/runs/37667630158/jobs?per_page=100' --paginate --slurp
gh api repos/ROCm/TheRock/actions/jobs/112958213252/logs
curl.exe -fLsS 'https://therock-ci-artifacts.s3.amazonaws.com/37667630158-linux/prim_test_generic.tar.zst' -o D:/scratch/codex/pr8762/pr-linux-test.tar.zst
D:/projects/TheRock/.venv/Scripts/python.exe D:/scratch/codex/pr8762/inventory.py
D:/projects/TheRock/.venv/Scripts/python.exe D:/scratch/codex/pr8762/analyze_artifacts.py
D:/projects/TheRock/.venv/Scripts/python.exe D:/scratch/codex/pr8762/check-benchmark-collision.py
cmake -P D:/scratch/codex/pr8762/check-rocprim-version.cmake
```

The compatibility reproduction prints baseline `compatible-with-4.8=TRUE`, PR `FALSE`. Inventory comparison prints Linux and Windows `added 31 removed 0`; binary provenance output demonstrates the benchmark replacement. Full outputs are retained in scratch rather than reproduced in this report.

Review scope: superbuild/CMake, artifacts, helper logic, tests, documentation/compatibility, security, and performance. No new secret/injection issue was found in the changed code. The build/packaging change needs artifact and consumer integration checks; a new feature flag is not required merely for combining builds, but omission of these checks is not justified by successful compilation. No repository source files were changed and no review was posted to GitHub.

## Follow-up: local Windows build

Read-only inspection of `D:/projects/TheRock/build/math-libs/hipCCL_tests` confirms that both build outputs exist for all 26 colliding names, while the stage holds only one per name. SHA-256 comparison shows **all 26 staged executables match hipCUB** in this local build. This differs from the Linux CI mixture described above: the local install overwrote all 26 rocPRIM copies.

For `benchmark_device_reduce.exe`, the rocPRIM build output is 644,096 bytes; hipCUB is 2,906,624 bytes; the staged executable is byte-identical to hipCUB. The generated install scripts explicitly send both sources to `${CMAKE_INSTALL_PREFIX}/bin`:

- `build/rocprim/benchmark/cmake_install.cmake:361`
- `build/hipcub/benchmark/cmake_install.cmake:261`

The local `build/logs/hipCCL_tests_install.log` records the two installs at lines 369 and 671. Thus `PROJECT_BINARY_DIR` successfully separates build outputs, but the generated installation destinations still collide. The symptom here is loss of the rocPRIM copies; the identity of the survivor differs from the inspected Linux CI artifact.

All names, sizes, and three-way SHA-256 results are saved in `D:/scratch/codex/pr8762/local-windows-benchmark-hashes.json`. No build, install, or executable was run; the active build tree was left unchanged.

## Follow-up: nightly flattened tarball and regression attribution

Inspected `D:/scratch/codex/therock-dist-windows-gfx1151-tests-10.2.0a20261007.tar.gz` in streaming read-only mode. It contains one `bin/benchmark_device_reduce.exe`, 855,040 bytes, with hipCUB `reduce_benchmark`/`sum_kernel` class names. Its SHA-256 is `d17294392ea2cd2a2c2951daa34fe041a3f69a756d7309ddea29747b6715ad56`. The prim benchmark filenames match all 75 baseline prim benchmark filenames; two additional `benchmark_*` files are `benchmark_device_api.exe` and `benchmark_host_api.exe`. The 31 new PR benchmark filenames are absent from this nightly.

The flat `bin/` layout and the presence of unprefixed benchmark names are **preexisting**, and are not themselves a regression. The old artifact descriptor selected `bin/benchmark_*` only from hipCUB, `bin/benchmark_thrust_*` from rocThrust, and no benchmarks from rocPRIM_tests. The baseline Windows prim artifact contains 35 hipCUB benchmarks and 40 rocThrust benchmarks, zero rocPRIM benchmarks, and no duplicate regular-file relative paths. Therefore the old flattened artifact merge did not have two prim benchmark implementations competing for these paths.

The PR-specific regression is moving the two sets into one installed stage **before artifact filtering**: the old descriptor could select the hipCUB copy by its stage; the new descriptor cannot distinguish the implementations after installation. The observed Linux CI substitution of a previously shipped hipCUB benchmark with rocPRIM remains a regression. The local Windows loss of rocPRIM copies alone is not a regression in previously shipped coverage, because those copies were already excluded; it demonstrates that the new combined install cannot preserve both sets. This distinction narrows the finding without treating existing flattening as new.

Reproduction: `D:/projects/TheRock/.venv/Scripts/python.exe D:/scratch/codex/pr8762/inspect-nightly.py`. Full output is retained in `nightly-inspection.txt`; member lists, size, hash, and embedded class-name evidence are in `nightly-benchmarks.json`. The exact baseline descriptor is saved as `base-artifact-prim.toml`.

## Follow-up: external source fetch audit

**FUTURE WORK (preexisting): rocThrust fetches and builds an apparently unused Google Benchmark dependency.** Local Windows `hipCCL_tests_configure.log:301` reports Google Benchmark missing and fetches it. Generated `_deps/googlebench-subbuild/googlebench-populate-prefix/tmp/googlebench-populate-gitclone.cmake` clones `https://github.com/google/benchmark.git` and checks out `v1.9.5`. `_deps` contains only googlebench source/build/subbuild directories; the generated Ninja graph and build log confirm `benchmark.lib` and `benchmark_main.lib` are built.

This is not newly introduced by consolidation: baseline Windows `rocThrust_configure.log:76-81` reports the same fetch and version, and standalone `projects/rocthrust/cmake/Dependencies.cmake:394-429` contains the equivalent logic. PR Linux also fetches it. TheRock does not supply a benchmark package in the inspected dependency graph, so the missing-package fallback executes; `EXTERNAL_DEPS_FORCE_DOWNLOAD=OFF` does not disable fallback downloads, and `USE_SYSTEM_LIB=ON` governs ROCm library selection rather than all third-party dependencies.

The dependency appears obsolete after conversion to primbench: current rocThrust benchmark targets use the shared primbench headers, source scans found no Google Benchmark includes/API usage in its benchmark/test trees, and no generated `LINK_LIBRARIES` entry refers to `benchmark.lib` or `benchmark_main.lib`. Prefer removing the obsolete fetch/build block in rocThrust (both standalone and hipccl3 copies) after validating benchmark builds, rather than adding a new TheRock dependency solely to satisfy unused code. If another supported configuration genuinely needs Google Benchmark, gate the fetch on that configuration and provide a superproject-controlled dependency for it.

Other observed dependency resolution in the local configure:

| Dependency | Observed behavior |
|---|---|
| ROCm CMake | Found through TheRock; root fetch fallback not taken |
| GoogleTest | TheRock's `third-party/googletest/dist/lib/cmake/GTest`; no fetch |
| rocPRIM | Existing unified target reused; installed package also available for tests |
| rocRAND | TheRock's `math-libs/rocRAND/dist/lib/cmake/rocrand`; no fetch |
| SQLite | TheRock's Windows sysdeps package; `SQLITE_USE_SYSTEM_PACKAGE=ON`; no fetch |
| TBB | Not found, but `BUILD_HIPSTDPAR_TEST_WITH_TBB=OFF`; no fetch |
| libhipcxx | Not found in this subproject; rocThrust uses its deprecated fallback, not a download |

No additional realized external source fetch was found in the inspected local hipCCL/hipCCL_tests configure logs and `_deps` tree. Source contains conditional fetch paths for other configurations; this is not a claim that all configurations are network-free. The root does not include `shared_third_party.cmake`, so its nlohmann_json/GTest declarations do not cause downloads here. Local configure/build logs are retained as `local-hipCCL_tests-configure.log` and `local-hipCCL_tests-build.log` in the review scratch directory. No build-tree changes or configure/build reruns were performed.

## Follow-up: why Windows gfx1151 hipCCL_tests configure takes four minutes

The linked PR gfx1151 configure log ends at **246.04 seconds** (243.9 s configuring, 2.0 s generating). Its timestamped phases explain most of the elapsed time:

| Activity | Log interval / duration |
|---|---|
| rocPRIM category generation, 88 Python calls | 26.7–71.3 s: 44.6 s |
| hipCUB category generation, 49 Python calls | 103.0–135.1 s: 32.1 s |
| rocThrust category generation, 167 Python calls | 218.1–243.5 s: 25.4 s |
| CXX offload-compression probe | 4.1–11.9 s: 7.8 s |
| HIP parallel-jobs probe | 14.2–21.7 s: 7.5 s |
| HIP offload-compression probe | 77.0–100.6 s: 23.6 s |
| C compiler discovery/ABI setup window | 136.9–167.9 s: about 31 s |
| Google Benchmark lookup/fetch/configure window | 177.5–215.9 s: 38.4 s |
| Remaining work, including generation | about 35 s |

These are log windows, not a function-level profiler. The Google Benchmark window includes compiler-feature and thread checks; the clone/populate portion cannot be precisely isolated. Fetching begins at 179.6 s and output resumes at 183.6 s; it would be wrong to describe the entire 38.4 s as network download time. No benchmark executable compilation occurs in these category-generation loops.

**Largest avoidable cost:** `shared/ctest/TestCategories.cmake:180` runs `parse_test_categories.py` with synchronous `execute_process()` for every target, then rewrites/includes `test_categories.cmake`. The component CMakeLists iterate their target lists and invoke it 88 + 49 + 167 = **304 times**. The parser reloads YAML for each invocation (`parse_test_categories.py:352`). The measured category windows total **102.1 s, about 41.5% of configure time**. Batch all target/resource metadata per component, parse its YAML once, and generate all category suites in one invocation while preserving installed/build-tree test registrations.

The compiler probes build small test programs during configuration. hipCUB tests offload compression separately from the CXX check, and rocThrust's `project(... LANGUAGES CXX C)` introduces C compiler discovery late in the unified configure. Windows process/compiler overhead and contention are plausible contributors, but these logs do not attribute time specifically to antivirus, storage, or CPU contention. Share compatible compiler-capability checks where safe; do not simply hard-code their results.

Baseline gfx1151 configure durations are rocPRIM_tests **46.45 s**, hipCUB **31.58 s**, rocThrust **159.59 s**, summing to **237.62 s**, versus 246.04 s combined in the PR. Baseline has the same 304 category invocations and the same Google Benchmark fetch. The sum is a work comparison, not baseline wall time: separate outer configure/build jobs can overlap and start compiling independently. The unified build creates one barrier covering all component configuration. Thus the four-minute configure is primarily accumulated existing configure work, not evidence of a four-minute new download or a dramatic increase in total configuration work.

Logs saved as `pr-win1151-configure.log` and `base-win1151-{rocPRIM_tests,hipCUB,rocThrust}-configure.log` under the review scratch directory. Sources: https://therock-ci-artifacts.s3.amazonaws.com/37667630158-windows/logs/math-libs/gfx1151/hipCCL_tests_configure.log and corresponding baseline logs under `37620849077-windows/logs/math-libs/gfx1151/`.

Generated with Codex.
