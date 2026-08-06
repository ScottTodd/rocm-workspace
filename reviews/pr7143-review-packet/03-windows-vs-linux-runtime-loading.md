# Windows DLL Loading Compared with Linux Shared Objects

## Executive comparison

Both platforms support centrally installed libraries and self-contained
application bundles. Linux has an important extra capability for relocatable
native applications: an ELF executable can embed a path relative to itself via
`$ORIGIN` in `DT_RUNPATH` or `DT_RPATH`. Windows ordinary imports have no direct
equivalent to an ELF relative RUNPATH.

| Concern | Linux/ELF | Windows/PE |
|---|---|---|
| Test-runner override | `LD_LIBRARY_PATH` | Parent-scoped `SetDllDirectoryW`; `PATH` is not sufficient against System32 |
| Relative packaged library directory | `$ORIGIN/../lib` in RUNPATH/RPATH | Usually place DLLs beside `.exe`, or use a launcher/package mechanism |
| Central package-manager libraries | DEB/RPM dependencies and loader cache/default paths | MSI/package installation plus a loader/discovery contract |
| App-local package | `bin/` plus private `lib/` | `.exe` plus DLL closure, commonly in the same directory |
| Configuration before normal imports | Embedded ELF metadata participates in loading | Application `main()` is too late; use app-local DLLs, launcher, or delay/explicit load |
| Environment-path precedence | `LD_LIBRARY_PATH` is normally before RUNPATH/cache/default paths | `PATH` is after System32 in the default safe order |
| Transitive dependency caveat | `DT_RUNPATH` applies only to direct dependencies; children need their own paths | Dependencies are searched by basename unless appropriate `LoadLibraryExW` flags/package rules are used |

## The hipthreads test-harness analogy

`test_hipthreads_examples.py` currently constructs one environment for its
configure, build, and run subprocesses.

On Linux it prepends:

```text
<artifact-root>/lib
```

to `LD_LIBRARY_PATH`. This selects the extracted artifact libraries without
registering the temporary installation with `ldconfig`.

On Windows it prepends:

```text
<artifact-root>/bin
```

to `PATH`. This is similar in intent but not in precedence: System32 remains
earlier. A parent-scoped `SetDllDirectoryW` is the closest architectural
counterpart for this runner because it selects the artifact runtime for the
children before System32.

Both harness mechanisms have the same deployment limitation:

- A Linux binary run directly without the runner may fail unless it has a
  suitable RUNPATH or the user configures `LD_LIBRARY_PATH`.
- A Windows binary run directly without the runner may fail or silently use a
  System32 DLL unless it has an application-local runtime or another supported
  loading mechanism.

This is acceptable for ephemeral tests whose supported entry point is the test
runner. It is not a redistributable application design.

## Linux loader model

The Linux dynamic loader's documented order for a dependency without a slash
includes:

1. `DT_RPATH`, when present and `DT_RUNPATH` is absent.
2. `LD_LIBRARY_PATH`, except in secure-execution mode.
3. `DT_RUNPATH` for the requesting object's direct dependencies.
4. `/etc/ld.so.cache`.
5. Default paths such as `/lib` and `/usr/lib` or architecture-qualified
   variants.

See [`ld.so(8)`](https://man7.org/linux/man-pages/man8/ld.so.8.html).

`$ORIGIN` expands to the directory containing the executable or shared object.
This enables a relocatable package:

```text
my-application/
  bin/
    my-application
  lib/
    libamdhip64.so.7
    libamd_comgr.so...
```

The executable can be linked with:

```text
-Wl,-rpath,'$ORIGIN/../lib'
```

or configured through CMake:

```cmake
set_target_properties(
  my_application
  PROPERTIES INSTALL_RPATH "$ORIGIN/../lib"
)
```

Because `DT_RUNPATH` applies only to an object's direct `DT_NEEDED` entries,
bundled shared libraries may also need a suitable `$ORIGIN` RUNPATH for their
own private dependencies. A package must test the full graph rather than assume
the executable's RUNPATH applies transitively.

## Linux distribution models

### Distribution-managed DEB/RPM dependencies

The conventional distro model is:

1. The application package declares a dependency on the appropriate runtime
   package.
2. The package manager installs the runtime in an architecture-specific system
   library directory.
3. The system loader cache/default paths resolve it.
4. The package manager owns upgrades, dependency solving, and removal.

The application does not copy files into `/usr/lib` at runtime.

### `/usr/local`

The Filesystem Hierarchy Standard reserves `/usr/local` for software installed
by the local system administrator, commonly through a source installation. It
is not a scratch area for an application to mutate when it runs, and it usually
requires administrative ownership. A vendor application's test should not add
libraries to `/usr/local/lib` as an execution setup step.

See:
[FHS `/usr/local`](https://refspecs.linuxfoundation.org/FHS_3.0/fhs/ch04s09.html).

### `/opt`

Vendor/add-on applications commonly install a self-contained hierarchy under
`/opt/<vendor>/<application>`. They can keep private libraries under that tree
and use relative RUNPATHs or an official wrapper. The FHS says the package must
function without relying on optional front-end links in `/opt/bin` or
`/opt/lib`.

See:
[FHS `/opt`](https://refspecs.linuxfoundation.org/FHS_3.0/fhs/ch03s13.html).

### Portable application formats

- AppImage builds an AppDir with executables, shared libraries, and other
  resources, commonly in an FHS-like `usr/bin` and `usr/lib` structure, and
  enters it through `AppRun`.
- Flatpak combines an automatically installed versioned runtime with
  application-bundled dependencies that are absent from or intentionally
  different from the runtime.
- Games often bundle private shared objects or target a standardized game
  runtime.
- Containers bundle most of user space while using host kernel and GPU driver
  interfaces.

These models show that bundling shared objects is normal on Linux when
portability or version isolation matters. Linux is also comfortable with
central package-manager libraries, especially for open-source distro packages.

## Windows distribution models

### Application-local runtime

The Windows counterpart to the Linux `bin/` plus `lib/` bundle usually places
the DLL closure directly beside the executable:

```text
my-application/
  my-application.exe
  amdhip64_7.dll
  rocm_kpack.dll
  amd_comgr.dll
```

This uses the executable-directory search rule and works without environment or
registry setup. Multiple executables can share one application directory.

### Centrally installed runtime

A central Windows runtime MSI can own installation and servicing, but an
application still needs a startup-loading contract. Registry discovery tells a
launcher or delay-load shim where ROCm is; it cannot execute before normal
imports by itself.

Potential complete mechanisms include:

- Bootstrap launcher.
- Delay-loaded HIP import plus SDK discovery.
- Explicit `LoadLibraryExW` through a supported loader abstraction.
- Windows package dependency graph or other package identity mechanism.

Global `PATH` modification is neither deterministic nor sufficient against the
legacy System32 collision.

## What should and should not be bundled

Neither platform should blindly bundle every library visible in a developer
SDK.

A supported runtime closure needs to distinguish:

- ROCm user-space runtime libraries intended for redistribution.
- Dynamically loaded runtime modules.
- Required device/kernel packages and data.
- Compiler/development-only files that should not be shipped.
- OS libraries that must come from the operating system.
- Toolchain runtimes, such as the Microsoft Visual C++ runtime, that can be
  satisfied through a supported redistributable package or allowed
  application-local deployment.
- Kernel/display-driver interfaces that remain host prerequisites.
- License and notice files.

On Linux, bundling glibc indiscriminately is generally unsafe because of its
relationship with the host kernel, NSS, and distribution ABI expectations.
Portable packages normally establish an explicit base-runtime policy rather
than copying all output from `ldd`. Windows applications similarly should not
copy arbitrary System32 or SDK DLLs.

## Cross-platform CMake direction

A future ROCm-owned abstraction could conceptually provide:

```cmake
rocm_stage_runtime(
  TARGET my_application
  COMPONENTS hip
)
```

This name is illustrative, not an existing API. Its implementation would:

- On Windows, stage the supported DLL/data closure into the application's
  binary directory.
- On Linux, stage supported shared objects under `lib` and ensure appropriate
  relative RUNPATHs.
- Use package-owned metadata, not a filesystem glob.
- Produce install/package metadata for downstream installers.
- Exclude system and development-only dependencies.
- Fail when a declared dependency is missing.

Until such an abstraction exists, projects should document their exact chosen
model and avoid presenting ad hoc dependency scans as an official
redistribution contract.

## Testing both models

### Test-harness execution

- Linux: pass the intended artifact `lib` through `LD_LIBRARY_PATH`.
- Windows: scope the intended artifact `bin` with `SetDllDirectoryW` around
  child creation.
- Use temporary mutable build/output directories.
- Verify actual loaded paths.

### Redistributable application execution

- Run directly from the staged install tree with no test-runner setup.
- Remove ROCm-specific `LD_LIBRARY_PATH`, `PATH`, and convenience variables.
- Test with another ROCm version already installed.
- On Windows, test with a same-named System32 compatibility DLL present.
- On Linux, test on supported distributions without a developer SDK installed.
- Validate both ordinary imports and dynamically loaded modules/data.

## Key conclusion for hipthreads

Approach 1 (`SetDllDirectoryW`) is consistent with the existing Linux
`LD_LIBRARY_PATH` test architecture. Approach 2 should deliberately go beyond
that test architecture: it should make the example output directly runnable by
staging a supported runtime closure and, on Linux, embedding relative RUNPATHs.

---

Prepared with OpenAI Codex.
