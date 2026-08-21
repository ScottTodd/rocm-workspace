# PR Review: Build amd-mesa/libva sysdep on Windows

* **PR:** https://github.com/ROCm/TheRock/pull/7279
* **Head:** `b9710077d4e4173d316df56175daa5988a2c57e3`
* **Base:** `main` (`df21e24c90357697e202a03261d7678c4d1e245d` in the reviewed CI merge)
* **Reviewed:** 2026-08-19
* **Scope:** Comprehensive review, with emphasis on CMake/super-project testing,
  Windows prerequisites, build performance, artifact size, and artifact contents

## Summary

This PR enables the amd-mesa/libva sysdep on Windows, relocates the Mesa
submodule to a common source path, adds a Windows media-libs CI stage, patches
libva/Mesa for the ROCm install layout, and publishes new `dev` and `lib`
artifacts. The Windows build now completes in CI and the new artifacts contain
the expected headers, import libraries, runtime DLLs, and D3D12 VA driver.

The implementation is not ready to merge as-is. A CI helper forces Mesa on even
when the media feature group is disabled, the apparent DLL validation is
silently skipped on Windows, the published pkg-config metadata is inconsistent
with the files and paths in the artifact, the legacy local source-fetch path
omits Mesa on Windows, and the newly required Windows tools are absent from the
setup documentation and validator.

**Net changes:** +495/-14 across 15 files.

## Overall Assessment

**CHANGES REQUESTED**

The build result is promising and the added CI stage has acceptable warm-cache
cost, but five blocking correctness/testing/documentation issues need to be
fixed. The current red CI summary appears unrelated to amd-mesa, but it should
still be rerun or explicitly dispositioned before merge.

## Findings

### BLOCKING: `build_configure.py` defeats the media feature-group switch

[`platform_options["windows"]`](https://github.com/ROCm/TheRock/blob/b9710077d4e4173d316df56175daa5988a2c57e3/build_tools/github_actions/build_configure.py#L80-L86)
unconditionally passes `-DTHEROCK_ENABLE_SYSDEPS_AMD_MESA=ON`. This is both
redundant and behaviorally wrong. After this PR removes the Windows platform
disable from `BUILD_TOPOLOGY.toml`, the generated feature already belongs to
the `MEDIA_LIBS` group and defaults from `THEROCK_ENABLE_MEDIA_LIBS`. Setting the
leaf cache variable explicitly means a caller using
`-DTHEROCK_ENABLE_MEDIA_LIBS=OFF` through `extra_cmake_options` still builds Mesa
and still inherits its Meson/flex/bison requirements.

That contradicts the PR's stated design that Windows Mesa is driven by
`THEROCK_ENABLE_MEDIA_LIBS`, and it undermines the attempted prerequisite
scoping in the root CMake file.

**Required action:** remove the explicit Windows leaf-feature option and rely on
the topology-generated group default, as Linux does. Add a focused configuration
test showing that a Windows configuration with `THEROCK_ENABLE_MEDIA_LIBS=OFF`
leaves `THEROCK_ENABLE_SYSDEPS_AMD_MESA=OFF`, while the default media-enabled
configuration turns it on.

### BLOCKING: The three Windows DLLs are never validated

The new subproject calls
[`therock_test_validate_shared_lib()`](https://github.com/ROCm/TheRock/blob/b9710077d4e4173d316df56175daa5988a2c57e3/third-party/sysdeps/windows/amd-mesa/CMakeLists.txt#L31-L36)
for `rocm_sysdeps_va.dll`, `rocm_sysdeps_va_win32.dll`, and
`vaon12_drv_video.dll`. However, the helper
[`returns immediately on WIN32`](https://github.com/ROCm/TheRock/blob/b9710077d4e4173d316df56175daa5988a2c57e3/cmake/therock_testing.cmake#L20-L23),
so this call registers no tests and validates nothing. The Windows media-libs
job also skips its build-test step. The successful build and artifact-structure
job therefore prove only that files were produced and classified, not that the
DLLs or their transitive imports load.

This is especially important here because the PR renames both libva DLLs,
changes driver discovery, and leaves rocDecode/rocJPEG disabled on Windows, so
no downstream CI consumer exercises the new runtime surface.

A manual `LoadLibraryExW` probe against the completed local staged directory
successfully loaded and unloaded all three DLLs. `link.exe /dump /dependents`
also confirmed that `rocm_sysdeps_va_win32.dll` imports the renamed sibling
`rocm_sysdeps_va.dll`, and that dependency resolved in the staged `bin`
directory. This is positive evidence for the reviewed binaries, but it does not
replace an automated test: the generated local `CTestTestfile.cmake` contains no
tests for this subproject, confirming that the helper registered nothing.

**Required action:** add a real, blocking Windows build test that loads all
three DLLs from the staged layout and ensure the media-libs CI job actually runs
it. Prefer extending the shared-library validation helper with Windows-aware DLL
search handling or using `therock_cmake_subproject_build_test()` as described in
`TESTING.md`. Also preserve concrete evidence for the claimed downstream
rocDecode link/run; a GPU-backed VA initialization test should follow as soon as
that consumer can run in TheRock CI.

### BLOCKING: The published dev artifact contains broken pkg-config metadata

The final CI archives show two semantic artifact defects:

1. `DirectX-Headers.pc` remains in the dev artifact and advertises
   `-ld3dx12-format-properties -lDirectX-Guids` plus DirectX include paths, while
   the PR explicitly
   [deletes those headers and libraries](https://github.com/ROCm/TheRock/blob/b9710077d4e4173d316df56175daa5988a2c57e3/third-party/sysdeps/windows/amd-mesa/CMakeLists.txt#L201-L212)
   as build-only dependencies. Any consumer discovering that `.pc` file receives
   flags for files that do not exist.
2. `libva.pc` contains `driverdir=/bin`, an absolute root path that is neither
   the artifact's driver location nor relocatable. The driver is actually under
   `${prefix}/bin` (`lib/rocm_sysdeps/bin` after flattening).

The generic artifact-structure check passed because these are semantic metadata
errors, not classifier overlap errors. The published
[`dev` archive](https://therock-ci-artifacts.s3.amazonaws.com/32059182958-windows/sysdeps-amd-mesa_dev_generic.tar.zst)
has 36 files / 699,377 payload bytes; the invalid `.pc` files are directly
observable there. The completed local artifact reproduces both defects:
`pkg-config --variable=driverdir libva` prints `/bin`, and
`pkg-config --libs DirectX-Headers` returns both deleted library names while
none of the corresponding `.lib` or `.a` files exists.

**Required action:** remove `DirectX-Headers.pc` together with the other
build-only DirectX outputs, patch libva's pkg-config generation so `driverdir`
resolves relocatably to `${prefix}/bin`, and add an artifact-content assertion
that catches both conditions.

### BLOCKING: The default Windows build now requires undocumented, unchecked tools

The reusable CI workflow installs `winflexbison3` only for the new media stage,
which proves that `win_flex` and `win_bison` are required. A user following
[`windows_support.md`](https://github.com/ROCm/TheRock/blob/b9710077d4e4173d316df56175daa5988a2c57e3/docs/development/windows_support.md#L191-L235)
is not told to install it, and
[`validate_windows_install.ps1`](https://github.com/ROCm/TheRock/blob/b9710077d4e4173d316df56175daa5988a2c57e3/build_tools/validate_windows_install.ps1#L538-L544)
checks optional pkg-config but not `win_flex`/`win_bison`. The root
[`README.md`](https://github.com/ROCm/TheRock/blob/b9710077d4e4173d316df56175daa5988a2c57e3/README.md#L222)
also still says `THEROCK_ENABLE_SYSDEPS_AMD_MESA` is Linux-only.

Because this PR enables the sysdep by default with the media feature group, this
is stale setup documentation for the ordinary Windows build, not an optional
extra.

The successful local retry does not disprove the prerequisite gap. Although no
packages were installed specifically for this build, Meson found pre-existing
`win_flex.exe` and `win_bison.exe` under `C:\ProgramData\chocolatey\bin` (and
the wrapper found `pkg-config.exe` through the user's WinGet links directory).
The local environment therefore already satisfied the undocumented flex/bison
requirement.

**Required action:** add `winflexbison3` to the Windows package-manager and
manual prerequisite instructions, update the validator to check both
executables, and update the README flag description. The CMake configure should
also fail fast with an actionable message when the tools are absent rather than
waiting for Meson to fail during the build.

### BLOCKING: The supported legacy source fetch omits a now-default Windows source

A local checkout of this branch reproduced a CI-hidden source-selection gap.
The user had run `fetch_sources.py` through its supported legacy
`--media-libs-projects` path, but that argument still
[defaults to an empty list on Windows](https://github.com/ROCm/TheRock/blob/b9710077d4e4173d316df56175daa5988a2c57e3/build_tools/fetch_sources.py#L883-L896).
Consequently, the newly required `amd-mesa` submodule remained empty even
though this PR enables `THEROCK_ENABLE_SYSDEPS_AMD_MESA` by default. CMake then
configured successfully, copied the empty source directory, and failed much
later in `therock-amd-mesa_build.log` with:

```text
ERROR: Neither source directory '.../build' nor build directory
'.../patch_source' contain a build file meson.build.
```

CI does not exercise this path. It uses `fetch_sources.py --stage media-libs`,
which resolves the stage's `media-libs` artifact group and its
[`["amd-mesa", "rocm-systems"]` source sets](https://github.com/ROCm/TheRock/blob/b9710077d4e4173d316df56175daa5988a2c57e3/BUILD_TOPOLOGY.toml#L342-L346).
The stage-aware path therefore fetches Mesa on Windows while the supported
legacy path does not. `fetch_sources.py --stage media-libs` is the immediate
local workaround, but requiring users to know that distinction is not a valid
integration result.

**Required action:** update the legacy media-libs selection so enabling media
libraries fetches `amd-mesa` on Windows, preferably by deriving it from the same
topology/source-set data as stage-aware mode instead of maintaining another
platform-specific list. Add a Windows unit test proving the legacy and
stage-aware media selections both include `amd-mesa`. Also check for
`${_source_dir}/meson.build` at configure time and issue an actionable fetch
instruction so an incomplete checkout cannot degrade into an opaque Meson
build error.

### IMPORTANT: The PR test record is incomplete and the latest CI summary is red

The PR body has a duplicated/truncated **Test Result** section, refers to a Mesa
pointer (`75b4d6b0`) that is not the reviewed gitlink (`d32e7c099c`), and claims
a downstream rocDecode link/run without providing the command or output. That
is not sufficient evidence for the runtime path patch.

The latest Multi-Arch CI summary also fails. The only failing substantive job
is the Windows Python wheel test, which reports 384 hipBLASLt library files
missing from `devel`. This PR does not touch hipBLASLt or the wheel layout, the
Windows sanity test and artifact-structure validation pass, and an earlier PR
run passed end-to-end, so the failure does not presently look caused by this
change. It is still a red required check and should not simply be ignored.

**Recommendation:** repair the PR test/result text with exact commands, outputs,
durations, artifact links, and the downstream runtime result. Rerun the failed
wheel job on the current base or link a tracking issue/maintainer disposition
showing that the hipBLASLt failure is independently understood.

### SUGGESTION: Remove the pkg-config discovery branch unless a real dependency requires it

The Windows CMake wrapper spends substantial logic finding a native
`pkg-config.exe` and warns that the build may fail without one. The successful
CI log explicitly reports `Found pkg-config: NO`, then builds the forced libva
and DirectX-Headers fallbacks successfully. This makes the current branch look
unnecessary and leaves users unsure whether pkg-config is required.

Either remove the discovery/warning path, or document and test the concrete
configuration that needs it. Do not retain optional compatibility logic without
an exercised consumer.

## CI Performance and Artifact Evidence

### Windows media-libs stage

* Final job: 8m15s wall time (`19:44:06` to `19:52:21` UTC).
* Actual `Build stage`: 2m50s; `therock-amd-mesa_build.log`: 164.99s.
* Earlier successful branch job: 9m15s total, 3m23s in `Build stage`.
* The final run is therefore not slower than the earlier successful branch
  datapoint. There is no pre-PR Windows baseline because this is a new stage.
* About 5m25s of the final job is checkout, Python/tool installation, source and
  inbound-artifact fetch, configure, reporting, and upload overhead. The stage
  runs parallel to the long math jobs, so it does not extend this run's critical
  path, but it consumes roughly eight additional Windows runner-minutes.
* The ccache log records 583 direct remote hits and one miss for Mesa sources
  (99.8% direct-hit rate). The 165-second build is therefore a warm-cache
  measurement and should not be presented as representative of a first local or
  cold-cache build.

### Linux relocation check

The final Linux media-libs job passed in 1m27s with a 27-second build step. A
recent pre-PR main run completed the same job in 1m08s with a 13-second build
step. The 14-second build-step delta is small in absolute terms and not enough
to call a regression from one sample, but it is the relevant baseline for the
shared-source relocation.

### Local Windows build

After fetching the missing `amd-mesa` submodule, the same configured build tree
completed successfully. The per-subproject log wrapper recorded 5.76s for
configure, 42.27s for the 655-step Meson/Ninja build, and 0.015s for install.
The post-build ccache counters showed 703 cacheable calls: 102 hits and 601
misses (14.5% hit rate). Because the counters were not captured immediately
before the build, they are not a rigorous per-run delta, but their scale closely
matches this subproject and makes the local result a useful cache-poor
datapoint. Machine capacity differs, so the 42-second local result should not be
used as a direct runner benchmark; it does show that the CI's 165-second
warm-cache result is dominated by more than compiler cache misses alone.

Both local and CI build logs print
`ninja: error: failed recompaction: Permission denied` during each of the two
Meson setup passes, yet Meson returns success and the subsequent compile
completes. This is noisy but reproducible across environments rather than a
local-only failure.

### Artifact sizes and contents

| Artifact | Compressed | Payload | Files | Key contents |
| --- | ---: | ---: | ---: | --- |
| `sysdeps-amd-mesa_dev_generic` | 143,653 B | 699,377 B | 36 | 29 VA headers, 3 import libraries, 3 pkg-config files |
| `sysdeps-amd-mesa_lib_generic` | 2,557,024 B | 14,498,866 B | 4 | `rocm_sysdeps_va.dll`, `rocm_sysdeps_va_win32.dll`, `vaon12_drv_video.dll` |

The payload adds about 2.7 MB compressed / 15.2 MB uncompressed, which is
reasonable for the intended component. No DirectX headers or static libraries
leak into the archives, but the dangling DirectX pkg-config file and incorrect
libva driver path must be corrected as described above.

The unpacked local artifact agrees closely with CI: the dev component is exactly
36 files / 699,377 bytes, and the lib component is 4 files / 14,499,890 bytes
(1,024 bytes larger than the CI payload, with the entire difference in
`vaon12_drv_video.dll`). No files are missing or added; its classification and
semantic metadata defects are otherwise the same.

## Verification Evidence

* `pre-commit`: passed.
* Unit Tests on Ubuntu 24.04 and Windows Server 2022: passed.
* Windows media-libs build: passed.
* Linux media-libs build after common-source relocation: passed.
* Windows artifact-structure validation: passed, but does not validate semantic
  pkg-config correctness.
* Windows GPU sanity test: passed, but does not exercise amd-mesa/libva.
* Published build log inspected, including all 655 Meson/Ninja steps and ccache
  statistics.
* Published `dev` and `lib` archives downloaded and enumerated without
  extraction; pkg-config contents inspected directly.
* Local build failure inspected from
  `D:\projects\TheRock\build\logs\therock-amd-mesa_build.log`; root cause was
  the legacy Windows media source selection omitting `amd-mesa`, before any
  missing-package check.
* Local build completed after fetching `amd-mesa`: configure 5.76s, build
  42.27s, install 0.015s; the staged artifacts match CI in layout and nearly
  exactly in size.
* All three local staged DLLs passed a manual `LoadLibraryExW`/`FreeLibrary`
  probe with load-directory and System32 dependency search enabled.
* Local `pkg-config` queries reproduced `/bin` as libva's driver directory and
  references to the removed DirectX libraries.

## Recommended Retest

1. Exercise both `fetch_sources.py --stage media-libs` and the legacy Windows
   media-libs selection; verify both fetch `amd-mesa`.
2. Configure Windows with media enabled and disabled; verify the generated leaf
   feature follows the group in both cases.
3. Run a clean Windows media-libs build from a documented environment after the
   validator passes, and record cold- and warm-cache durations.
4. Run a blocking staged-DLL load test for all three runtime files.
5. Assert the dev artifact has no DirectX-Headers metadata/files and that
   `pkg-config --variable=driverdir libva` resolves inside the staged prefix.
6. Run a downstream rocDecode/VA initialization smoke test on a Windows GPU
   runner with only the published artifacts and normal ROCm environment setup.
7. Rerun the failed Windows wheel test on the current base.

## Conclusion

The core build integration works in the stage-aware CI path and has modest
artifact and CI costs, but the current configuration semantics, divergent local
source selection, skipped Windows validation, broken artifact metadata, and
missing prerequisite documentation are merge blockers. Address those issues
and replace the PR body's incomplete test narrative with durable evidence before
requesting another review.

**Approval status: CHANGES REQUESTED**

Generated with Codex
