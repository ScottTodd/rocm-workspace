# Local Evidence and Reproduction

## Environment and inputs

Review date: 2026-08-06

Local inputs supplied for inspection:

```text
D:\scratch\codex\hipthreads\linux_hipthreads_test_generic
D:\scratch\codex\hipthreads\windows_hipthreads_test_generic
D:\scratch\codex\hipthreads\therock-dist-windows-multiarch-tests-10.1.0a20260806
```

Additional minimal PR dependency artifacts were downloaded and flattened into:

```text
D:\scratch\codex\hipthreads\minimal_dlls_31094954012
```

Relevant tools:

```text
D:\tools\Dependencies_x64_Release\Dependencies.exe
D:\projects\TheRock\.venv\Scripts\python.exe
```

The artifact-size discrepancy caused by the `matrices.tgz` Git LFS object is
excluded and tracked in TheRock issue #7171.

## PR and CI snapshot commands

```powershell
gh api repos/ROCm/TheRock/pulls/7143
gh pr diff 7143 --repo ROCm/TheRock
gh api repos/ROCm/TheRock/issues/7132
gh api `
  -H "Accept: application/vnd.github+json" `
  "repos/ROCm/TheRock/commits/019f1d87a941264bafbd1583d1fe5e5caef17d2d/check-runs?per_page=100"
gh api repos/ROCm/TheRock/actions/jobs/92642280035
```

Observed PR metadata:

```text
Number:        7143
State:         open
Draft:         false
Head:          019f1d87a941264bafbd1583d1fe5e5caef17d2d
Base:          main
Additions:     8
Deletions:     0
Changed files: 1
```

Observed Windows example job:

```text
Job:          92642280035
Conclusion:   success
Runner:       azure-windows-11-gfx1101-gpu-rocm-runner-18
Runner group: default
Labels:       windows-gfx110X-gpu-rocm
```

Issue #7132 says the failure reproduces consistently on `CS-RORDMZ`, while
Azure runners could already pass. No affected-group validation was attached to
the PR at this snapshot.

## hipthreads artifact inventory

Command pattern:

```powershell
$files = Get-ChildItem -LiteralPath <artifact> -File -Recurse
$files.Count
($files | Where-Object Extension -eq '.exe').Count
($files | Where-Object Extension -eq '.dll').Count
($files | Where-Object { $_.Name -match '\.so(\.|$)' }).Count
($files | Where-Object Name -eq 'CMakeLists.txt').Count
```

Results:

| Artifact | Files | `.exe` | `.dll` | `.so*` | `CMakeLists.txt` |
|---|---:|---:|---:|---:|---:|
| Linux hipthreads test artifact | 606 | 0 | 0 | 0 | 17 |
| Windows hipthreads test artifact | 606 | 0 | 0 | 0 | 17 |

This confirms that the example executables are not packaged in the generic
test artifact; the GPU runner builds them.

## DLL copy-impact measurement

Measurement logic:

```powershell
$dlls = Get-ChildItem -LiteralPath <root>\bin -Filter '*.dll' -File
$dllBytes = ($dlls | Measure-Object Length -Sum).Sum
$threeCopies = 3 * $dllBytes
```

Results:

| Input | DLL count | DLL bytes | DLL size | Three copies |
|---|---:|---:|---:|---:|
| Full Windows multi-arch tests dist | 40 | 4,458,080,768 | 4.152 GiB | 13,374,242,304 bytes / 12.456 GiB |
| PR CI dependency set | 9 | 189,901,824 | 181.10 MiB | 569,705,472 bytes / 543.31 MiB |

Full tree impact:

```text
Original tree:       22,117,773,524 bytes (20.599 GiB)
Three DLL copies:    13,374,242,304 bytes (12.456 GiB)
Logical result:      35,492,015,828 bytes (33.055 GiB)
Logical growth:      60.47%
```

Allocated disk usage can differ due to compression or deduplication. The byte
count accurately represents logical copied data and copy I/O.

### Minimal PR CI DLL set

| DLL | Bytes | MiB |
|---|---:|---:|
| `amd_comgr.dll` | 121,972,224 | 116.32 |
| `amdhip64_7.dll` | 16,563,200 | 15.80 |
| `amdocl64.dll` | 11,760,640 | 11.22 |
| `cltrace.dll` | 480,256 | 0.46 |
| `hiprand.dll` | 17,408 | 0.02 |
| `hiprtc0715.dll` | 1,295,872 | 1.24 |
| `hiprtc-builtins0715.dll` | 943,616 | 0.90 |
| `rocm_kpack.dll` | 181,248 | 0.17 |
| `rocrand.dll` | 36,687,360 | 34.99 |

The presence of hipRAND, hipRTC, OpenCL-related, and rocRAND files illustrates
that even the minimal flattened set already includes DLLs unrelated to the
direct hipthreads example import graph.

### Full distribution DLL set

| DLL | Bytes | MiB |
|---|---:|---:|
| `amd_comgr.dll` | 121,972,224 | 116.32 |
| `amdhip64_7.dll` | 16,563,200 | 15.80 |
| `amdocl64.dll` | 11,760,640 | 11.22 |
| `cltrace.dll` | 480,256 | 0.46 |
| `fftw3.dll` | 953,856 | 0.91 |
| `fftw3f.dll` | 933,888 | 0.89 |
| `hipblas.dll` | 801,280 | 0.76 |
| `hipdnn_backend.dll` | 2,312,704 | 2.21 |
| `hipfft.dll` | 154,112 | 0.15 |
| `hipfftw.dll` | 274,432 | 0.26 |
| `hiprand.dll` | 17,408 | 0.02 |
| `hiprtc0715.dll` | 1,295,872 | 1.24 |
| `hiprtc-builtins0715.dll` | 943,616 | 0.90 |
| `hipsolver.dll` | 1,540,096 | 1.47 |
| `hipsparse.dll` | 219,648 | 0.21 |
| `hiptensor.dll` | 65,302,016 | 62.28 |
| `libhipblaslt.dll` | 6,302,208 | 6.01 |
| `MIOpen.dll` | 493,969,408 | 471.09 |
| `MIOpenCKGroupedConv_gfx1100.dll` | 357,542,912 | 340.98 |
| `MIOpenCKGroupedConv_gfx1101.dll` | 357,542,912 | 340.98 |
| `MIOpenCKGroupedConv_gfx1102.dll` | 357,542,912 | 340.98 |
| `MIOpenCKGroupedConv_gfx1150.dll` | 308,094,976 | 293.82 |
| `MIOpenCKGroupedConv_gfx1151.dll` | 307,915,264 | 293.65 |
| `MIOpenCKGroupedConv_gfx1152.dll` | 308,082,688 | 293.81 |
| `MIOpenCKGroupedConv_gfx1153.dll` | 308,090,880 | 293.82 |
| `MIOpenCKGroupedConv_gfx1200.dll` | 326,323,712 | 311.21 |
| `MIOpenCKGroupedConv_gfx1201.dll` | 326,323,712 | 311.21 |
| `MIOpenCKGroupedConv_gfx908.dll` | 283,338,752 | 270.21 |
| `MIOpenCKGroupedConv_gfx90a.dll` | 279,434,240 | 266.49 |
| `OpenCL.dll` | 124,416 | 0.12 |
| `origami.dll` | 368,128 | 0.35 |
| `rocalution.dll` | 5,694,464 | 5.43 |
| `rocblas.dll` | 21,053,952 | 20.08 |
| `rocfft.dll` | 27,508,736 | 26.23 |
| `rocm_kpack.dll` | 181,248 | 0.17 |
| `rocm-openblas.dll` | 11,719,680 | 11.18 |
| `rocm-openblas64.dll` | 11,926,528 | 11.37 |
| `rocrand.dll` | 36,686,848 | 34.99 |
| `rocsolver.dll` | 24,983,040 | 23.83 |
| `rocsparse.dll` | 71,803,904 | 68.48 |

MIOpen and architecture-specific grouped-convolution DLLs dominate the copied
size and are unrelated to the hipthreads examples.

## Same-basename loader collision experiment

### Collision inputs

```text
C:\Windows\System32\OpenCL.dll
  Length:      247,232 bytes
  FileVersion: 3.0.6.0
  SHA-256:     943CF553C4FF480810CA4DD2B1CBBD894C36E21C2B203A87470461BE54FA5471

<full-rocm-dist>\bin\OpenCL.dll
  Length:      124,416 bytes
  FileVersion: 2.2.6.0
  SHA-256:     B9052A34658F5E29B8C07DCF2633C87A6B4369896703B79D9FFDBC7238D4C1D9
```

The files were distinct by path, length, version, and hash.

### Child probe

The generic probe in `probes/report_loaded_module.py`:

1. Calls `ctypes.WinDLL(<basename>)` without an absolute path.
2. Calls `GetModuleFileNameW` with the loaded module handle.
3. Prints the resolved path.

### Observed output

With the ROCm `bin` prepended to the child `PATH`:

```text
PATH-only child:
C:\Windows\SYSTEM32\OpenCL.dll
```

After the parent called `SetDllDirectoryW(<full-rocm-dist>/bin)` and then
created the child:

```text
SetDllDirectoryW-inherited child:
D:\scratch\codex\hipthreads\therock-dist-windows-multiarch-tests-10.1.0a20260806\bin\OpenCL.dll
```

After the parent called `SetDllDirectoryW(NULL)`:

```text
Restored search state:
C:\Windows\SYSTEM32\OpenCL.dll
```

The Python implementation matching the documentation sample was also executed
directly:

```text
D:\scratch\codex\hipthreads\therock-dist-windows-multiarch-tests-10.1.0a20260806\bin\OpenCL.dll
C:\Windows\SYSTEM32\OpenCL.dll
```

The first line is the child launched inside the configured scope. The second is
a fresh child after the parent restored the default.

### Why OpenCL was used

The local machine did not have a colliding `amdhip64_7.dll` in System32, but it
did have two distinct `OpenCL.dll` files. The experiment tests Windows' generic
same-basename loader ordering. It does not claim that OpenCL and HIP have the
same ABI or dependency graph.

## `amdhip64_7.dll` dependency inspection

Command:

```powershell
& 'D:\tools\Dependencies_x64_Release\Dependencies.exe' `
  -imports `
  'D:\scratch\codex\hipthreads\therock-dist-windows-multiarch-tests-10.1.0a20260806\bin\amdhip64_7.dll'
```

Direct imports included Windows system DLLs plus:

```text
rocm_kpack.dll
  kpack_free_code_object
  kpack_load_code_object
  kpack_cache_create

amd_comgr.dll
  amd_comgr_get_version
```

`Dependencies.exe -modules` resolved both ROCm dependencies from the same
extracted `bin` directory.

Further direct-import scans found:

- `rocm_kpack.dll` imports Windows/UCRT and Microsoft Visual C++ runtime DLLs,
  but no further ROCm DLL.
- `amd_comgr.dll` imports Windows/UCRT and Microsoft Visual C++ runtime DLLs,
  but no further ordinary ROCm DLL.
- The Microsoft runtime dependencies observed include `MSVCP140.dll`,
  `VCRUNTIME140.dll`, and `VCRUNTIME140_1.dll`.

Sizes:

| File | Bytes | MiB | File version |
|---|---:|---:|---|
| `amdhip64_7.dll` | 16,563,200 | 15.80 | 10.0.3581.0 |
| `rocm_kpack.dll` | 181,248 | 0.17 | not populated |
| `amd_comgr.dll` | 121,972,224 | 116.32 | 3.3.0.0 |
| **Total** | **138,716,672** | **132.29** | |

### Static-analysis limitation

The imported-symbol list for `amdhip64_7.dll` includes `LoadLibraryA` and
`LoadLibraryExW`. A strings scan also found names of optional driver/runtime
modules, but strings are not proof that a module is required or loaded in a
given configuration. Static import tools cannot establish the full behavioral
redistribution closure.

An authoritative closure must also account for:

- Dynamically loaded modules.
- Device/kernel packages and data.
- Configuration and license files.
- Optional feature paths.
- Supported Visual C++ redistributable requirements.
- Driver/runtime compatibility.

## Static-linking inspection

The full Windows distribution contains:

| File | Bytes | Role established by installed CMake metadata |
|---|---:|---|
| `lib/amdhip64.lib` | 166,948 | Import library |
| `bin/amdhip64_7.dll` | 16,563,200 | Shared runtime implementation |
| `lib/amd_comgr.lib` | 20,972 | Import library |
| `bin/amd_comgr.dll` | 121,972,224 | Shared COMGR implementation |
| `lib/rocm_kpack.lib` | 4,756 | Import library |
| `bin/rocm_kpack.dll` | 181,248 | Shared kpack implementation |

The installed target files say:

```text
lib/cmake/hip/hip-targets.cmake:
  add_library(hip::amdhip64 SHARED IMPORTED)

lib/cmake/hip/hip-targets-release.cmake:
  IMPORTED_IMPLIB_RELEASE = <prefix>/lib/amdhip64.lib
  IMPORTED_LOCATION_RELEASE = <prefix>/bin/amdhip64_7.dll
```

Archive inspection:

```powershell
& '<dist>\lib\llvm\bin\llvm-ar.exe' t '<dist>\lib\amdhip64.lib'
```

Observed:

```text
Exit code:       0
Archive members: 720
Unique name:     amdhip64_7.dll
```

This is the expected shape of a PE/COFF import library. It is not a static copy
of the 16.56 MB runtime implementation.

At local rocm-systems commit
`90cbfbd55d944e16a6d9b1d6a0ed451f96831715`, CLR's
`hipamd/src/CMakeLists.txt` does contain a `BUILD_SHARED_LIBS=OFF` branch that
creates `amdhip64` as `STATIC`. The same static branch also has explicit
transitive dependency setup. No such static HIP artifact or CMake target is
present in the reviewed distribution. Source support for a build mode is not
evidence that a released SDK supports downstream applications linking it,
especially on Windows.

## Ordinary HIP imports and pre-`main` loading

To evaluate whether an existing HIP program could call `LoadLibraryExW` from
`main()`, an installed HIP executable containing GPU code was inspected:

```powershell
& 'D:\tools\Dependencies_x64_Release\Dependencies.exe' `
  -imports `
  '<full-dist>\bin\copy.hip.exe'
```

Its ordinary import table names `amdhip64_7.dll` and includes:

```text
__hipPopCallConfiguration
__hipPushCallConfiguration
__hipRegisterFatBinary
__hipRegisterFunction
__hipUnregisterFatBinary
hipLaunchKernel
hipMalloc
hipMemcpy
hipFree
```

The file also contains `.hipFatB` and `.hip_fat` PE sections. These observations
are consistent with compiler-generated embedded device code and registration.
Most importantly for loader design, `amdhip64_7.dll` is an ordinary import, so
Windows must select it during process initialization before `main()`.

This does not rule out known-path loading. It rules out adding an ordinary
`LoadLibraryExW` call to the beginning of the current program while leaving the
normal import unchanged. A bootstrap process, correctly arranged delay load,
or no-import explicit dispatch design is required.

## Reproducing with the generic probes

Report the default resolution:

```powershell
D:\projects\TheRock\.venv\Scripts\python.exe `
  .\probes\report_loaded_module.py OpenCL.dll
```

Run the same probe through a parent with a selected DLL directory:

```powershell
D:\projects\TheRock\.venv\Scripts\python.exe `
  .\probes\run_child_with_dll_directory.py `
  D:\path\to\rocm\bin `
  D:\projects\TheRock\.venv\Scripts\python.exe `
  .\probes\report_loaded_module.py `
  OpenCL.dll
```

Then run `report_loaded_module.py` directly again to verify that the parent
restored its default state.

## Evidence limitations

- GitHub Actions job logs could not be downloaded through the logs endpoint in
  the earlier investigation because it returned HTTP 403. Job metadata, steps,
  PR/issue bodies, and supplied failure logs remained available.
- The successful PR job ran on Azure, not the affected runner group.
- Local loader proof used `OpenCL.dll` as the collision basename.
- Dependency scanning cannot see all runtime dynamic loads.
- The full distribution represents one nightly composition and should be used
  to demonstrate unbounded scaling, not as a permanent DLL-count expectation.

---

Prepared with OpenAI Codex.
