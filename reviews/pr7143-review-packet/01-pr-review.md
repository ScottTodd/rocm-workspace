# PR Review: ROCm/TheRock #7143

- **PR:** https://github.com/ROCm/TheRock/pull/7143
- **Title:** `ci(fix): Fix Windows hipThreads examples loading the driver's HIP runtime (#7132)`
- **Head:** `019f1d87a941264bafbd1583d1fe5e5caef17d2d`
- **Base:** `main`
- **Reviewed:** 2026-08-06
- **Focus:** Windows DLL loading, installed-test architecture, correctness,
  determinism, disk/I/O impact, and local reproducibility

## Summary

The PR correctly identifies why the failing Windows example loads the wrong HIP
runtime: `System32` precedes `PATH` in the ordinary unpackaged Windows DLL
search order. It adds a loop that copies every top-level DLL from the merged
artifact `bin` directory beside each of the three example executables.

The copy loop fixes precedence because the executable directory is searched
before `System32`, but it makes the test's dependency set depend on unrelated
artifacts, can copy gigabytes per example, and mutates the extracted ROCm
installation. A scoped loader configuration or an explicitly defined
application-local runtime closure solves the same problem without the unbounded
glob.

## Overall assessment

**CHANGES REQUESTED** — remove the `bin/*.dll` copy loop. Either of the two
approaches under [Acceptable fixes](#acceptable-fixes) is appropriate, with
approach 1 being the smallest reliable change for this PR.

## Finding

### BLOCKING: Copying every install-tree DLL into every example is unbounded

The changed code at
[`test_hipthreads_examples.py` lines 177-181](https://github.com/ROCm/TheRock/blob/019f1d87a941264bafbd1583d1fe5e5caef17d2d/build_tools/github_actions/test_executable_scripts/test_hipthreads_examples.py#L177-L181)
effectively does:

```python
for dll in (OUTPUT_ARTIFACTS_PATH / "bin").glob("*.dll"):
    shutil.copy2(dll, binary.parent)
```

The copied set is determined by whichever artifacts happen to have been
flattened into the shared install prefix. It is not determined by hipthreads'
declared runtime dependencies.

Verified local measurements:

| Input installation | Top-level DLLs | DLL bytes copied per example | Bytes copied for 3 examples |
|---|---:|---:|---:|
| PR CI dependency composition | 9 | 189,901,824 (181.10 MiB) | 569,705,472 (543.31 MiB) |
| Full Windows multi-arch tests distribution | 40 | 4,458,080,768 (4.152 GiB) | 13,374,242,304 (12.456 GiB) |

The supplied full distribution contains 22,117,773,524 bytes before the test.
The three copies would increase its logical size to 35,492,015,828 bytes, a
60.47% increase. Repeated runs overwrite the copies but still perform the same
12.46 GiB of copy I/O. Filesystem compression or deduplication may change
allocated size but does not repair the dependency or mutation problems.

Other correctness and maintenance effects:

- The extracted install is no longer read-only test input.
- A DLL produced by an example can be overwritten if its basename collides.
- Every unrelated copied DLL receives application-directory precedence.
- A full merged install behaves differently from the minimal CI composition.
- Undeclared runtime dependencies can be hidden because any coincidentally
  present DLL is copied.
- The example test can leave large stale files after failure or interruption.

**Required action:** remove the all-DLL glob and use one of the bounded designs
below.

## Acceptable fixes

### Approach 1: Scope `SetDllDirectoryW` around child creation

This is the recommended immediate fix.

The Python runner already owns the complete configure/build/run lifecycle and
executes it sequentially. On Linux, `build_environment()` selects the artifact
runtime by passing `<artifact-root>/lib` in `LD_LIBRARY_PATH` to the child
processes. On Windows, `PATH` cannot provide equivalent precedence because
`System32` is searched first. A parent-scoped `SetDllDirectoryW` supplies the
intended Windows-specific behavior.

Microsoft documents that, for ordinary unpackaged processes, calling
`SetDllDirectoryW` in the parent also affects the DLL search order of children
started while it is set. The relevant portion of the alternate order becomes:

1. Child executable directory.
2. Directory supplied to `SetDllDirectoryW`.
3. `System32`.
4. Remaining Windows directories.
5. `PATH`.

Implementation requirements:

- Resolve and validate `<artifact-root>/bin` before passing it to the API.
- Declare the native function signature when calling through `ctypes`.
- Check the API return value and raise `ctypes.WinError` on failure.
- Restore the default with `SetDllDirectoryW(NULL)` in `finally`.
- Keep the runner single-threaded while the process-global setting is active.
- Do not perform unrelated DLL loads while the directory is set.
- Apply the scope to every child that may load ROCm DLLs, including
  `offload-arch`, CMake/compiler subprocesses where relevant, and the final
  examples. A common subprocess helper or one narrow sequential phase is less
  error-prone than configuring only one of these calls.
- Keep `PATH` configuration for locating tools; do not describe it as a way to
  override a same-named `System32` DLL.

This approach preserves the current harness contract. Like the Linux
`LD_LIBRARY_PATH` setup, it does not make a built example independently
runnable outside the harness.

### Approach 2: Make example build/install outputs application-local

This is the more complete design for examples intended to teach downstream
application development.

Each example CMake project can stage the supported HIP runtime redistribution
closure into its binary or temporary install directory. The runner then invokes
the self-contained result without special loader setup.

Requirements:

- Configure and build in a temporary root outside `OUTPUT_ARTIFACTS_PATH`.
- Prefer one temporary install prefix shared by the examples, rather than a
  private copy of the runtime beside every executable.
- Stage only a supported, explicitly defined runtime closure.
- Obtain that closure from an SDK-owned manifest or CMake helper when one is
  available.
- Do not glob the entire ROCm `bin` directory.
- Do not assume that `$<TARGET_RUNTIME_DLLS>` or PE-import scanning discovers
  dynamically loaded libraries and non-DLL data.
- Treat the source ROCm installation as read-only.
- Test direct execution of the installed/staged result.

This design additionally demonstrates how a forked example can become a
redistributable Windows application. It may reasonably be a follow-up if ROCm
does not yet expose an authoritative redistribution closure.

## CI evidence

### The reported failure is runner-group-specific

[Issue #7132](https://github.com/ROCm/TheRock/issues/7132) records:

- Azure Windows runners generally passed before this PR.
- `CS-RORDMZ` runners consistently loaded
  `C:\WINDOWS\SYSTEM32\amdhip64_7.dll` and failed with `0xC0000005`.

The PR's successful Windows `hipthreads_examples` check ran on:

```text
azure-windows-11-gfx1101-gpu-rocm-runner-18
```

Job:
https://github.com/ROCm/TheRock/actions/runs/31094954012/job/92642280035

That result shows the modified test passes on the Azure group, but the issue
already established that Azure could pass before the change. It does not
validate behavior on the affected `CS-RORDMZ` group.

At the review snapshot:

- Windows `hipthreads_examples`: success.
- Windows `hipthreads`: cancelled.
- Linux `hipthreads_examples`: success.
- Linux `hipthreads`: success.
- Overall CI summary: failure for unrelated or unconfirmed jobs; this review
  does not attribute those failures to the eight-line change.

### Required validation

Re-run `hipthreads_examples` on a `CS-RORDMZ` runner and record the resolved
path of `amdhip64_7.dll`, for example with `GetModuleFileNameW`. Exit zero alone
does not prove that the runtime under test was loaded.

## Local loader proof

Two different `OpenCL.dll` files were already present on the review machine:

| DLL | File version | SHA-256 |
|---|---|---|
| `C:\Windows\System32\OpenCL.dll` | 3.0.6.0 | `943CF553C4FF480810CA4DD2B1CBBD894C36E21C2B203A87470461BE54FA5471` |
| `<full-rocm-dist>\bin\OpenCL.dll` | 2.2.6.0 | `B9052A34658F5E29B8C07DCF2633C87A6B4369896703B79D9FFDBC7238D4C1D9` |

A child loaded `OpenCL.dll` by basename and printed its resolved path with
`GetModuleFileNameW`:

```text
PATH-only child:
C:\Windows\SYSTEM32\OpenCL.dll
SetDllDirectoryW-inherited child:
<full-rocm-dist>\bin\OpenCL.dll
Restored search state:
C:\Windows\SYSTEM32\OpenCL.dll
```

`OpenCL.dll` is only the convenient same-basename collision used to exercise
the loader. The ordering behavior is the same mechanism involved in the
reported `amdhip64_7.dll` collision.

## Existing architecture exposed by the PR

The runner already writes mutable outputs into the extracted artifact:

```python
source_dir = EXAMPLES_ROOT / example["subdir"]
build_dir = source_dir / "build"
```

It also writes stdout logs into that build tree. Moving these outputs to a
harness-owned temporary directory is desirable regardless of which DLL fix is
chosen. Because this mutation predates the PR, it can be tracked as follow-up
work if approach 1 removes the newly added DLL copies.

The separate `test_hipthreads.py` and `test_hiptests.py` runners also contain
install-tree mutation patterns. They are broader policy/migration work and
should not be used to justify adding another instance here.

## Ready-to-post review comment

> **Blocking:** Could we avoid copying every
> `OUTPUT_ARTIFACTS_PATH/bin/*.dll` into each example directory? The copied set
> depends on unrelated artifacts in the merged installation, mutates the
> extracted install, and can add 12.46 GiB for the three examples in a full
> Windows tests distribution. Even the minimal PR CI composition copies 181.10
> MiB three times.
>
> I think either of these approaches would address the loader issue:
>
> 1. As the narrow fix, have the existing single-threaded Python runner scope
>    `SetDllDirectoryW(<resolved-artifacts>/bin)` around its child-process
>    launches, checking the API result and restoring the default in `finally`.
>    This is the Windows analogue in role to the runner's existing Linux
>    `LD_LIBRARY_PATH` setup: it selects the artifact runtime for configure,
>    build, and execution without copying files.
> 2. As the fuller example/deployment design, have the example CMake projects
>    stage their supported HIP runtime dependency closure into a binary or
>    temporary install directory. The runner should build/install outside
>    `OUTPUT_ARTIFACTS_PATH` and execute that self-contained result. Ideally the
>    closure would come from an SDK-owned redistribution manifest or CMake
>    helper, not a `bin/*.dll` glob or a list duplicated by each example.
>
> The first option validates examples through their existing harness; the
> second additionally demonstrates how a forked example can become an
> independently runnable Windows application. In either case, the extracted
> ROCm install should be read-only. Please also validate on the affected
> `CS-RORDMZ` runner group and record the resolved `amdhip64_7.dll` path: the
> passing PR job ran on the Azure group that issue #7132 says already passed
> before this change.

## Approval criteria

The PR is ready for re-review when:

1. The all-DLL copy loop is removed.
2. One of the bounded approaches above is implemented with fail-fast error
   handling.
3. The implementation proves that the artifact `amdhip64_7.dll` is loaded on
   an affected runner or in an equivalent same-basename collision test.
4. The resulting test does not add or copy files into the extracted ROCm
   installation beyond any explicitly tracked pre-existing mutation.

---

Prepared with OpenAI Codex.
