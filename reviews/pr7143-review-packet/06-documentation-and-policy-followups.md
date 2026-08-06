# Documentation and Policy Follow-ups

This file separates project-wide follow-up work from the change needed in
[PR #7143](https://github.com/ROCm/TheRock/pull/7143). The PR should solve the
hipthreads example failure without waiting for every broader packaging question
to be settled. The broader questions should nevertheless have an explicit home
so that hipthreads, hip-tests, and future projects converge on the same model.

## Recommended documentation structure

### 1. `docs/development/windows_support.md`

Keep this page focused on Windows platform facts, short recipes, and gotchas:

- Explain that the executable directory is not the process current directory.
- Explain why putting an artifact `bin` directory first on `PATH` does not
  override a same-named module in `System32` under the ordinary unpackaged-app
  search order.
- Show a short parent-runner `SetDllDirectoryW` example and state that the
  setting is inherited by child processes.
- Warn that `SetDllDirectoryW` changes process-global state and should be scoped
  with `try`/`finally` in a runner that launches children sequentially.
- Distinguish a harness execution fix from a redistributable application.
- Link to the cross-platform native-application packaging guide for the fuller
  deployment discussion.

The page should not grow into a complete native packaging manual. It is the
place for the Windows-specific loader behavior that developers need to remember
while writing build and test infrastructure.

### 2. A native-application guide under `docs/packaging/`

Add a consumer-facing guide analogous in purpose to the “Using Packages from
Frameworks” section of `python_packaging.md`. A possible name is
`docs/packaging/native_application_packaging.md`.

Suggested outline:

1. Build-time discovery is not runtime discovery.
2. Choose a deployment model deliberately.
3. Windows application-local deployment.
4. Windows centrally installed ROCm deployment.
5. Linux system packages and loader cache.
6. Linux relocatable bundles using `$ORIGIN`-relative RUNPATH.
7. Framework, container, AppImage, and Flatpak integration.
8. ROCm project responsibilities.
9. Downstream application responsibilities.
10. Packaging and loader tests.
11. Common anti-patterns.

The deployment-model section should make the main choices concrete:

| Model | Windows | Linux | Primary responsibility |
|---|---|---|---|
| Application-local bundle | EXE and supported DLL closure in an app-controlled directory | Executable plus private libraries with an `$ORIGIN`-relative RUNPATH | Application packager |
| Centrally installed runtime | A documented activation/bootstrap mechanism is still needed | Distribution packages plus `ldconfig`, or an administrator-managed prefix | Runtime/distribution installer |
| Test harness | Scoped loader configuration for child processes | Scoped `LD_LIBRARY_PATH` or a packaged RUNPATH | Test infrastructure |
| Container/framework bundle | Framework-specific layout and startup | Container/AppImage/Flatpak conventions | Framework or image author |

The guide should say explicitly that “CMake found the package” proves only the
build-time relationship. It does not prove that the resulting program can find
the runtime libraries when launched from Explorer, a shell, a service, another
working directory, or a clean machine.

### 3. Testing policy under issue #6711

The testing-policy document should establish these defaults:

- Treat an extracted install or artifact tree as immutable test input.
- Create all build directories, logs, generated data, caches, and staged
  runtime bundles in a unique temporary workspace.
- A test may configure the child process environment, but the required setup
  must be explicit and scoped to that process tree.
- If installed executables are claimed to be directly runnable, test direct
  invocation without relying on a repository-only wrapper.
- If an executable is only supported through a harness, document that contract
  and test the harness.
- Verify which module was loaded where same-named system or older ROCm modules
  can mask a packaging bug. Success alone is not always sufficient evidence.
- Fail fast when staging or execution fails. Do not log an exception and then
  continue with a partially prepared runtime tree.
- Exercise both a minimal dependency artifact composition and a fully merged
  distribution. This catches assumptions that accidentally work only because
  CI downloaded fewer components.

These requirements still allow temporary application-local staging. The
important boundary is that the test owns and can discard the mutable directory;
the extracted installation remains unchanged.

### 4. Producer-facing packaging documentation

`docs/packaging/native_packaging.md` currently concerns how TheRock assembles
artifacts. It should link to the new consumer/deployment guide and clearly state
the distinction:

- Producer packaging decides what belongs in each artifact and distribution.
- Consumer packaging decides what runtime closure an application carries and
  how its loader is activated.
- Test infrastructure validates both contracts but should not silently repair
  either one by mutating the installation under test.

## Policy wording that can be reused

The following is draft normative language:

> Tests must treat an extracted ROCm installation as immutable input. Test
> runners may create temporary build and staging trees and may configure the
> environment inherited by their child processes. They must not add, replace,
> or edit files in the installation merely to make an installed test pass.

> Installed test executables must either be directly runnable under the
> documented installed-runtime activation model, or be explicitly documented
> as harness-managed executables. A harness-managed test must configure loader
> behavior without modifying the installation and must fail if that setup is
> incomplete.

> Windows applications distributed with ROCm runtime libraries must stage the
> supported redistributable closure supplied by ROCm packaging metadata or a
> ROCm-provided build helper. They must not infer that closure by copying every
> DLL in a shared installation directory.

> Linux relocatable application bundles should use an application-owned library
> directory and an `$ORIGIN`-relative RUNPATH. `LD_LIBRARY_PATH` is appropriate
> for controlled test or activation environments, but should not be the only
> runtime contract of a generally redistributable application.

The words “supported redistributable closure” are intentional. A raw PE import
scan finds only statically recorded dependencies. It can miss optional,
delay-loaded, plugin, or data-driven modules and says nothing about which files
ROCm supports an application redistributing.

## Migration candidates

These are follow-up candidates, not reasons to expand PR #7143.

### `test_hiptests.py`

At the 2026-08-06 snapshot, `copy_dlls_exe_path()` globs four name families
(`amdhip64*`, `amd_comgr*`, `hiprtc*`, and `rocm_kpack*`) and copies matches from
`bin` into `share/hip/catch_tests`. Copy exceptions are logged and suppressed.
This has three policy problems:

1. It mutates the extracted installation.
2. A failed copy can produce an ambiguous later failure or allow an unintended
   system module to load.
3. The name patterns encode a runtime closure independently of authoritative
   packaging metadata.

Candidate migrations are to install ROCm-owned catch-test executables in the
same runtime directory as their DLLs, or use a scoped runner activation while
keeping test executables in their current data layout. The former gives direct
invocation stronger semantics; the latter may be an easier transition.

### `test_hipthreads.py`

The hipthreads lit runner currently stages headers under
`<artifact-root>/hipthreads/inc` and hard-links or copies the static library to
`<artifact-root>/hipthreads/lib`, because the packaged lit configuration expects
those paths. This mutates the artifact tree even though the DLL issue is not the
reason. Repointing lit at the packaged include and library locations is the
cleanest eventual fix. Until then, stage the compatibility layout in a temporary
test workspace and point lit there.

### `test_hipthreads_examples.py`

The example runner configures each project into a `build` subdirectory beneath
the packaged example source tree and writes stdout logs there. Move those build
and log paths to a unique temporary directory. Then choose either the immediate
scoped loader approach or the application-local example packaging approach
described in [04-hipthreads-examples-architecture.md](04-hipthreads-examples-architecture.md).

### Other installed tests

Many Windows tests are already installed into `bin` beside the ROCm DLLs. That
is a useful positive pattern for ROCm-owned test executables when namespace
crowding is acceptable and the installed test is intended to run directly.
It does not mean that every third-party/downstream application should install
itself into ROCm's shared `bin` directory.

## Gaps for the Windows packaging RFC

[PR #3973](https://github.com/ROCm/TheRock/pull/3973) correctly moves ROCm away
from treating `System32` as the home of the full user-space HIP runtime. The
following details would make its downstream contract more actionable:

1. Define an authoritative, machine-readable redistributable closure for
   application-local deployment. A CMake helper can consume that metadata.
2. Specify how an application locates and activates a centrally installed ROCm
   runtime before its ordinary imports are resolved. Registry discovery by
   application code is too late for a normal, non-delay-loaded import.
3. Define the servicing and side-by-side-version policy for application-local
   copies, including whether applications may redistribute them and which
   notices/licenses must accompany them.
4. Describe dependencies that are loaded dynamically, not visible in the
   ordinary PE import table.
5. Specify versioned dependencies such as COMGR consistently and state how
   basename conflicts are prevented.
6. Identify non-ROCm prerequisites such as the supported Visual C++ runtime and
   the kernel driver boundary.
7. Update the public HIP Windows deployment documentation that still describes
   the legacy `System32` installation model when the transition is ready.

The compatibility shim in `System32` should be narrow enough that accidentally
loading it remains safe and diagnostic. It should not recreate the old policy by
making `System32` the preferred deployment location for the full user-space
runtime.

## Suggested work sequence

1. Land a bounded fix for PR #7143, preferably scoped `SetDllDirectoryW`, and
   move example build output to temporary storage if feasible in the same PR.
2. Add the Windows loader gotcha and test-harness guidance to
   `windows_support.md`.
3. Adopt the install-immutability language in the testing-policy work tracked by
   issue #6711.
4. Add the cross-platform native-application packaging guide.
5. Define ROCm-owned redistribution metadata/helper as part of or immediately
   after the Windows packaging RFC.
6. Convert hip-tests and remaining mutating runners, with targeted regression
   tests for same-basename system collisions.

## Alternatives Considered

### Install all test executables into ROCm `bin`

This is often correct for ROCm-owned, prebuilt test executables because Windows
then finds their adjacent runtime DLLs naturally. It is not a universal answer
for copyable examples: a user application should own its deployment directory,
and examples compiled on a target-specific test runner need not become permanent
members of the ROCm installation.

### Copy every DLL from the installation

Rejected. It is unbounded, duplicates unrelated components, obscures the actual
dependency contract, can change behavior as the merged artifact set changes,
and has a measured worst case of more than 12 GiB of duplicate data for the
three examples in the supplied full distribution.

### Copy only `amdhip64_7.dll`

Rejected as a general rule. The ordinary import table already shows direct ROCm
dependencies on `rocm_kpack.dll` and `amd_comgr.dll`; dynamic dependencies may
add more. One guessed DLL fixes neither packaging completeness nor supportability.

### Rely on `PATH`

Rejected for the reported failure. Under the ordinary Windows search order,
`System32` precedes `PATH`, so a stale same-named `amdhip64_7.dll` can win.

### Call `AddDllDirectory` or `LoadLibraryEx` in ordinary application `main`

Insufficient for normal load-time imports: the loader resolves those before
`main` begins. These APIs become architectural options only with an earlier
launcher/bootstrap or with delay-loaded/explicitly loaded components.

### Static-link the entire runtime

Not treated as an available general solution. It changes the ROCm distribution,
licensing, servicing, and plugin model and is not the runtime contract established
by the current packages.

---

Prepared with OpenAI Codex.
