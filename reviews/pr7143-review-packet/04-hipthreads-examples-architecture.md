# hipthreads Examples Build and Test Architecture

## Goals

The hipthreads examples serve at least two purposes:

1. Validate that the installed hipthreads headers/library and ROCm toolchain can
   build and execute representative programs on the target GPU.
2. Provide source examples that developers may fork into their own
   applications.

Those purposes overlap but are not identical. A test harness may legitimately
configure a temporary loader environment, while a user-facing redistributable
example should demonstrate how its produced application runs independently.

## Current artifact facts

The supplied Linux and Windows `hipthreads_test_generic` artifacts each contain
606 files and 17 `CMakeLists.txt` files. Neither contains an `.exe`, `.dll`, or
`.so` test binary.

That is intentional in the current runner. The source script explains that:

- `libhipthreads.a`/the hipthreads artifact is target-neutral.
- Each example executable embeds device code for a concrete GPU architecture.
- Prebuilding the examples would make the test artifact target-specific.
- Therefore the GPU test runner configures and builds examples after detecting
  a concrete architecture.

The runner currently executes three GPU examples:

| Name | Source subdirectory | Executable |
|---|---|---|
| `saxpy` | `saxpy/step3-simdize` | `saxpy[.exe]` |
| `inOneWeekend` | `InOneWeekendRaytracer/step4-simdize` | `inOneWeekend[.exe]` |
| `spmm` | `sparse-mat-mul/step3-hipthread-port` | `spmm[.exe]` |

## Current lifecycle

The important flow in
[`test_hipthreads_examples.py`](https://github.com/ROCm/TheRock/blob/019f1d87a941264bafbd1583d1fe5e5caef17d2d/build_tools/github_actions/test_executable_scripts/test_hipthreads_examples.py)
is:

```text
Extract/flatten selected ROCm artifacts
  |
  +-- <artifact-root>/hipthreads/examples/...       source input
  +-- <artifact-root>/include, lib, bin, compiler   SDK/runtime input
  |
Detect concrete GPU architecture with offload-arch
  |
For each selected example:
  |
  +-- configure CMake
  |     source: <artifact-root>/hipthreads/examples/<example>
  |     build:  <source>/build
  |
  +-- build executable into <source>/build/bin
  |
  +-- run executable with source directory as cwd
  |
  +-- write stdout log into <source>/build
```

Environment construction currently includes:

- `ROCM_PATH=<artifact-root>`
- `HIP_PATH=<artifact-root>`
- `HIP_DEVICE_LIB_PATH=<artifact-root>/lib/llvm/amdgcn/bitcode`
- `CMAKE_PREFIX_PATH=<artifact-root>`
- `PATH` containing tool directories
- Linux: `<artifact-root>/lib` prepended to `LD_LIBRARY_PATH`
- Windows: `<artifact-root>/bin` prepended to `PATH`

The Linux setting changes runtime-library precedence as intended. The Windows
setting does not override a same-named DLL in System32.

## Existing architecture concerns

### The extracted artifact is used as a build tree

`build_dir = source_dir / "build"` places CMake caches, objects, executables,
and logs inside the extracted artifact/install tree. This predates PR #7143 but
conflicts with a useful project-wide invariant:

> Tests consume extracted installs as read-only inputs and place mutable build,
> output, cache, and log state in harness-owned temporary directories.

Consequences of the current arrangement include:

- A test run changes the artifact under test.
- Repeated runs may reuse stale CMake state.
- Parallel or interrupted runs can interfere.
- It is harder to prove that a packaged install was complete before testing.
- Cleanup semantics are unclear.

### `cwd` carries test-data semantics

The runner intentionally uses the example source directory as `cwd` so relative
data paths work. That is valid test behavior, but it should not dictate the DLL
search design. The Windows loader's executable directory and process working
directory are distinct.

A cleaner design can retain the source/data directory as `cwd` or pass absolute
data paths while keeping build and runtime files in a temporary tree.

### GPU detection is also a runtime consumer

Before building examples, the script launches `offload-arch`. On Windows it
globally prepends the artifact `bin` directory to the runner's `PATH` because
`offload-arch.exe` loads ROCm DLLs. This has the same System32-precedence
limitation as the examples.

If the runner adopts `SetDllDirectoryW`, the scope should include GPU detection
and other relevant ROCm child processes, not only `run_example()`.

## Recommended immediate architecture

Use the test runner as the single supported entry point for this test and make
the platform-specific runtime selection explicit.

```text
Resolve read-only artifact root
  |
Create temporary work root
  |
Select artifact runtime for children
  +-- Linux: child env with LD_LIBRARY_PATH=<artifact>/lib
  +-- Windows: parent SetDllDirectoryW(<artifact>/bin)
  |
Detect GPU architecture
  |
Configure/build examples under temporary work root
  |
Run and log under temporary work root
  |
Restore Windows default DLL directory
```

Properties:

- No DLL copies.
- Same architectural contract on Linux and Windows: the runner selects the
  artifact runtime.
- Test outputs are disposable and isolated.
- The extracted artifact remains read-only.
- The result validates source compatibility and execution through the harness.
- Direct execution of the temporary binaries is not promised.

### Suggested temporary layout

```text
<temp>/hipthreads-examples/
  saxpy/
    build/
    saxpy.stdout.log
  inOneWeekend/
    build/
    inOneWeekend.stdout.log
  spmm/
    build/
    spmm.stdout.log
```

The runner can pass `-B <temp>/<name>/build` while retaining the extracted
example directory as `-S`. Test data can be passed as resolved paths or the
existing source-directory `cwd` can remain temporarily.

## Recommended redistributable-example architecture

Examples that are expected to teach downstream packaging should produce a
staged application tree and test it through direct execution.

### Windows

```text
<temp>/install/bin/
  saxpy.exe
  inOneWeekend.exe
  spmm.exe
  amdhip64_7.dll
  rocm_kpack.dll
  amd_comgr.dll
  other supported HIP runtime files/data
```

All examples can share one `bin` directory and one runtime copy. The set shown
is illustrative; only an official redistribution closure can be normative.

### Linux

```text
<temp>/install/
  bin/
    saxpy
    inOneWeekend
    spmm
  lib/
    libamdhip64.so...
    other supported HIP runtime shared objects
```

The installed executables use an appropriate relative RUNPATH such as
`$ORIGIN/../lib`, and bundled libraries have paths for their own transitive
dependencies.

### CMake responsibility

The example project—not the test runner—owns application packaging behavior.
That keeps deployment logic with the application and makes it visible to users
who copy the example.

Prefer an SDK-owned abstraction or component manifest. An illustrative future
API could be:

```cmake
rocm_stage_runtime(
  TARGET saxpy
  COMPONENTS hip
)
```

This is a design sketch, not an existing supported CMake command.

Avoid these incomplete substitutes:

- `file(GLOB "<rocm>/bin/*.dll")`
- Hardcoding every current ROCm DLL in each example
- Assuming `$<TARGET_RUNTIME_DLLS>` discovers runtime `LoadLibrary` calls and
  required non-DLL data
- Running `Dependencies.exe` or `ldd` during every downstream build and treating
  the output as a licensing/redistribution contract

## Choosing between the approaches for PR #7143

### Approach 1 is appropriate now when

- The desired scope is a minimal CI reliability fix.
- The runner remains the supported entry point.
- ROCm has not yet published a supported redistribution manifest/helper.
- The team is prepared to test and restore the process-global Windows loader
  setting carefully.

### Approach 2 is appropriate now when

- The team wants to establish application deployment semantics in the example
  CMake projects.
- It can define and support the copied runtime closure.
- It can test direct execution on clean target machines.
- Licensing, servicing, version selection, and driver compatibility are
  understood.

Approach 2 is the better end state for user-facing examples, but requiring it
as the only acceptable immediate PR fix would pull unresolved ROCm-wide
packaging policy into a small CI repair.

### Static linking would be a third model only if ROCm supports it

A truly static HIP runtime could make each example executable independent of
`amdhip64_7.dll`. The current Windows distribution cannot demonstrate that
model: it ships an import library plus the DLL and exports `hip::amdhip64` as a
shared imported target. Current AMD deployment guidance also says static
linking to HIP SDK components is unsupported.

The example project should not attempt to reach into ROCm build trees and link
unpublished object or static archives. If ROCm later ships a supported static
target, static examples should be separate configurations with tests that:

1. Confirm the executable has no `amdhip64_*.dll` import.
2. Exercise runtime compilation, kpack, profiling, and other dynamic feature
   paths relevant to the supported static profile.
3. Document the remaining driver and operating-system runtime prerequisites.
4. Include required licenses/notices and a rebuild-based servicing plan.
5. Compare executable size and per-application duplication against the shared
   application-local bundle.

Static linking would trade loader simplicity for larger executables, duplicate
runtime code across applications, and application-owned security updates. It
should be offered as an intentional SDK product, not inferred from an upstream
build switch.

### Known-path loading is a distinct central-runtime model

An application-owned loader could let forked examples select a versioned
central ROCm runtime without copying it. The current example executable cannot
perform that setup in `main()`: compiling HIP code gives it normal imports on
the runtime, including generated fat-binary registration APIs.

The teachable architecture would be:

```text
example-launcher.exe       no HIP imports
  |
  +-- discover and validate ROCm runtime root
  +-- configure restricted runtime bin search
  +-- launch example-real.exe
        ordinary HIP imports resolve under selected policy
```

This can be redistributable if the launcher uses a documented runtime-discovery
contract. It differs from application-local packaging: the runtime can be
shared and serviced centrally, while the launcher owns activation and version
selection.

For the current test, Python already fills the launcher role. Replacing it with
a C++ launcher would not make the inner executable directly runnable and would
add another artifact to maintain. A reusable ROCm-provided launcher or loader
could change that tradeoff; a one-off launcher in every example would be a poor
project-wide pattern.

A same-process variant can build the example body as a DLL:

```text
example-host.exe           no HIP imports
  |
  +-- LoadLibraryExW(<absolute-runtime>/amdhip64_7.dll)
  +-- LoadLibraryExW(example-implementation.dll)
  +-- GetProcAddress(example_main)
```

This is closer to “the application explicitly loads HIP” and allows generated
HIP registration to occur when the implementation DLL is loaded. It avoids a
manual HIP dispatch table, but every example would need a host/implementation
split unless ROCm supplied a reusable host library or launcher pattern.

A more ambitious in-process design would require the HIP toolchain to support
delay loading or a loader/dispatch API that also owns generated device-code
registration. That should be designed and tested by the HIP runtime/toolchain,
not improvised in hipthreads examples.

## Proposed acceptance tests

### Harness-mode test

1. Make the extracted artifact directory read-only where practical.
2. Create a fresh temporary work directory.
3. Configure and build all three selected examples.
4. On Windows, ensure a different same-named `amdhip64_7.dll` is available in
   System32 or another controlled collision fixture.
5. Run through the harness.
6. Record the loaded HIP runtime path and require it to be under the selected
   artifact `bin` directory.
7. Require the output marker and exit zero.
8. Confirm no files were added or modified under the artifact root.

### Redistributable-mode test

1. Configure/build/install into a clean temporary prefix.
2. Remove ROCm-specific loader environment configuration.
3. Run the installed executable directly.
4. Verify all ROCm user-space libraries resolve from the staged application.
5. Repeat with another ROCm version or System32 compatibility runtime present.
6. Validate dynamically loaded features, not only process startup.
7. Verify package contents against the authoritative redistribution manifest.

### Composition tests

- Minimal hipthreads plus declared dependency artifacts.
- Full merged ROCm installation.
- Clean target without a developer SDK.
- A supported GPU driver older/newer within the published compatibility range.

## Longer-term artifact option

The existing comment suggests that once hipthreads ships a shared library, the
example compilation can move to a target-specific build-stage test artifact.
That can reduce GPU-runner compilation, but it does not by itself solve runtime
packaging. Prebuilt test executables still need one of:

- Installation in the ROCm runtime `bin` directory.
- A self-contained application-local package.
- A supported central-runtime loader contract.

Artifact target specificity and runtime discovery are related but separate
decisions.

## Separation of responsibilities

| Layer | Responsibility |
|---|---|
| hipthreads example source/CMake | Express build, install, and any supported application-local staging behavior |
| TheRock test runner | Select artifacts, create temporary state, launch children, capture evidence, and leave inputs unchanged |
| ROCm runtime packaging | Define redistributable components, versions, dependencies, licensing, and supported loader mechanism |
| Windows compatibility installer | Preserve explicitly scoped legacy System32 behavior during migration |
| Downstream application | Choose central versus application-local deployment and service its owned runtime copies |
| ROCm loader/bootstrap component, if created | Discover/version a central runtime and activate it before ordinary HIP imports or expose a stable explicit dispatch ABI |

Keeping these responsibilities separate prevents a CI workaround from becoming
an accidental downstream packaging contract.

---

Prepared with OpenAI Codex.
