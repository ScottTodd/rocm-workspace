# Windows DLL Loading as It Relates to ROCm

## Purpose

This document explains the Windows loader behavior behind TheRock issue #7132,
the immediate test-harness options, and the longer-term deployment choices for
ROCm applications. It distinguishes startup imports, explicit runtime loading,
application-local deployment, and transitional System32 compatibility.

## The central loader distinction

For an ordinary unpackaged application using the default safe DLL search mode,
Windows does not search `PATH` first. Microsoft documents special factors such
as DLL redirection, API sets, side-by-side manifests, the loaded-module list,
Known DLLs, and the package dependency graph before the ordinary filesystem
locations. The important ordinary locations for this investigation are:

1. Directory containing the executable.
2. System directory, normally `C:\Windows\System32`.
3. Other Windows directories.
4. Current working directory.
5. Directories in `PATH`.

See:
[Dynamic-link library search order](https://learn.microsoft.com/en-us/windows/win32/dlls/dynamic-link-library-search-order).

Consequences:

- Prepending `<rocm-root>/bin` to `PATH` cannot override a same-named DLL in
  `System32`.
- Changing `cwd` is not equivalent to moving the executable; the executable
  directory and current working directory are distinct search locations.
- A DLL beside the executable normally wins over a same-named DLL in
  `System32`, unless an earlier special factor such as Known DLL handling
  applies.
- The loader may reuse a same-named module already loaded in the process,
  independent of its original directory.

This explains both sides of PR #7143: `PATH` failed to select the artifact HIP
runtime, while copying DLLs beside the executable gave them higher precedence.

## Ordinary imports happen before `main`

When an executable links normally against `amdhip64_7.lib`, the import library
records a dependency on `amdhip64_7.dll` in the PE import table. Windows must
locate that DLL and its ordinary dependencies while starting the process,
before the executable's `main()` function runs.

Therefore, code placed at the start of `main()` cannot change how the loader
resolved those ordinary imports. To configure loading from inside the
application, the application must instead use one of these designs:

- Mark the dependency for linker-supported delay loading, configure the search
  path first, and only then call HIP.
- Load a fully qualified path explicitly with `LoadLibraryExW` and suitable
  restricted search flags, then resolve entry points or trigger a delay import.
- Use a bootstrap executable with no HIP imports. The bootstrap discovers and
  configures the runtime before loading or starting the real HIP program.
- Package the required DLLs application-locally so startup needs no custom
  configuration.

## `SetDllDirectoryW` in a parent test runner

[`SetDllDirectoryW`](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-setdlldirectoryw)
adds one directory to the calling process's DLL search path. For an ordinary
unpackaged process, Microsoft explicitly documents that it also affects the DLL
search order of child processes started while the setting is active.

With a non-null directory, the relevant alternate order is:

1. Application/executable directory.
2. Directory supplied to `SetDllDirectoryW`.
3. System directory.
4. Remaining Windows directories.
5. `PATH`.

The current directory is removed from that order. While a directory is set,
safe DLL search mode is effectively disabled. Calling `SetDllDirectoryW(NULL)`
restores the default order and safe-mode behavior.

### Why the Python call looks unusual

Python has no high-level standard-library wrapper for this particular API, so
the test runner can call it through `ctypes`, Python's foreign-function
interface:

```python
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
set_dll_directory = kernel32.SetDllDirectoryW
set_dll_directory.argtypes = [ctypes.c_wchar_p]
set_dll_directory.restype = ctypes.c_bool
```

Line by line:

- `ctypes.WinDLL("kernel32", ...)` loads the core Windows DLL that exports the
  API and returns a Python object exposing native functions.
- `use_last_error=True` tells `ctypes` to preserve the Windows thread-local
  last-error value for `ctypes.get_last_error()`.
- Attribute access finds the Unicode `SetDllDirectoryW` export.
- `argtypes` declares the native `LPCWSTR` parameter as a wide-character string
  pointer.
- `restype` declares the native `BOOL` success/failure return value. Declaring
  the ABI avoids unsafe default conversions.

A dedicated sequential test runner can then do:

```python
if not set_dll_directory(str(rocm_bin)):
    raise ctypes.WinError(ctypes.get_last_error())
try:
    subprocess.run(command, check=True)
finally:
    if not set_dll_directory(None):
        raise ctypes.WinError(ctypes.get_last_error())
```

### Scope and limitations

`SetDllDirectoryW` is a good match for `test_hipthreads_examples.py` because the
runner already owns all child creation and is single-threaded. It is not an
application packaging solution:

- The child executable does not record the selected ROCm directory.
- Running the child directly outside the test runner again uses the default
  search order and can fail or silently select System32.
- The setting is process-global, so it can affect other DLL loads in a
  multithreaded or multipurpose launcher.
- `SetDllDirectoryW(NULL)` restores the default, not an arbitrary previous
  custom directory. The simple helper assumes a dedicated runner that began in
  the default state.

## Application-local deployment

For a portable Windows application, the simplest deterministic model is to
place the supported runtime closure beside the executable:

```text
MyApplication/
  MyApplication.exe
  amdhip64_7.dll
  rocm_kpack.dll
  amd_comgr.dll
  other supported runtime files and data
```

The executable directory precedes System32, so this bundle selects its own
runtime even while a legacy compatibility DLL remains installed globally.

Application-local deployment is legitimate and common for large native
applications and games. It differs fundamentally from a test runner copying
all ROCm DLLs at runtime:

- The application owns the bundled files.
- Files are staged during build, packaging, or installation, not while running.
- The closure is explicit and validated.
- Multiple application executables can share one directory and one copy.
- The application owns security updates and servicing of its private runtime.
- The external ROCm SDK/install remains read-only.

## Static linking

Static linking can make a native application more self-contained by placing
library implementation code into the executable at link time. If the entire
HIP user-space runtime and its required static closure were supported this way,
there would be no `amdhip64_7.dll` startup lookup for that application.

That hypothetical should not be confused with linking `amdhip64.lib` on
Windows. A `.lib` file can be either a static implementation archive or an
import library describing symbols supplied by a DLL. In the supplied
distribution:

```text
lib/amdhip64.lib          166,948 bytes
bin/amdhip64_7.dll     16,563,200 bytes
```

The installed CMake package declares:

```cmake
add_library(hip::amdhip64 SHARED IMPORTED)
set_target_properties(hip::amdhip64 PROPERTIES
  IMPORTED_IMPLIB_RELEASE "${_IMPORT_PREFIX}/lib/amdhip64.lib"
  IMPORTED_LOCATION_RELEASE "${_IMPORT_PREFIX}/bin/amdhip64_7.dll"
)
```

`llvm-ar t amdhip64.lib` reports 720 import members, all named
`amdhip64_7.dll`. The small `.lib` supplies link-time symbol stubs; application
execution still requires the DLL.

The CLR source contains a `BUILD_SHARED_LIBS=OFF` branch that creates a static
`amdhip64` target. This is useful implementation evidence but not a supported
SDK promise. The reviewed TheRock distribution uses the default shared build,
does not ship that static archive, and AMD's current
[Windows deployment guidance](https://rocm.docs.amd.com/projects/install-on-windows/en/develop/conceptual/deployment-guidelines.html)
says static linking to HIP SDK components is unsupported.

A supported static model would need substantially more than publishing a large
archive:

- A complete static dependency closure, including HSA/PAL, COMGR, kpack, LLVM
  or compiler services used by runtime compilation, and supported OS/toolchain
  libraries.
- Clear behavior for components discovered at runtime, profiling/interposition,
  plugins, kernel packages, and driver interfaces.
- Consistent MSVC CRT and C++ runtime choices across application and ROCm code.
- License/notice and redistribution terms for every incorporated component.
- A security and servicing model: fixing a private static runtime generally
  requires rebuilding and redistributing the application.
- Exported CMake targets, documented compiler/link flags, and Windows CI for
  downstream programs.

Static linking could therefore be a worthwhile future deployment option, but
it is not an implementable alternative for hipthreads examples consuming the
current Windows tarball.

### The closure must be defined, not guessed

Local PE inspection of the supplied `amdhip64_7.dll` found these direct
non-Windows imports:

```text
amdhip64_7.dll
├── rocm_kpack.dll
└── amd_comgr.dll
```

Those three files total 138,716,672 bytes (132.29 MiB) in the reviewed build.
This is a direct import closure, not necessarily the full supported
redistribution closure:

- `amdhip64_7.dll` imports `LoadLibraryA` and `LoadLibraryExW`.
- Runtime behavior may load optional modules not visible in the import table.
- Required data, kernel packages, configuration, or license files are not
  represented in a DLL import graph.
- Tool output depends on the review machine's installed system and Visual C++
  runtimes.

ROCm should publish the supported closure as a machine-readable manifest,
component package, or CMake staging helper. Application authors should not have
to infer the contract from `Dependencies.exe`, `dumpbin`, `ldd`, or a glob.

## Using a centrally installed ROCm runtime

The draft Windows packaging RFC proposes versioned installation roots and
registry-based discovery. Discovery alone is insufficient for a normally
imported HIP DLL because the loader runs before application code can inspect
the registry.

A complete central-runtime design requires one of:

- A supported bootstrap launcher that discovers a pinned ROCm installation,
  configures loading, and starts the real program.
- A supported delay-load shim that performs discovery before first HIP use.
- A stable loader library/API that loads a fully qualified runtime and exposes
  the HIP entry points.
- A Windows package dependency mechanism that puts the chosen runtime in the
  process package graph.

Environment variables such as `ROCM_PATH` can communicate an install root to a
build system or bootstrapper. They do not by themselves change startup DLL
resolution. Globally adding ROCm `bin` to `PATH` is also insufficient for the
System32 collision and creates global ordering and preloading concerns.

## Explicit loading APIs

For a library intentionally loaded after process startup, prefer an absolute
path with
[`LoadLibraryExW`](https://learn.microsoft.com/en-us/windows/win32/api/libloaderapi/nf-libloaderapi-loadlibraryexw)
and appropriate `LOAD_LIBRARY_SEARCH_*` flags. In particular,
`LOAD_LIBRARY_SEARCH_DLL_LOAD_DIR` allows dependencies of the explicitly loaded
DLL to be found in that DLL's directory, while other flags can retain the
application and System32 locations.

Important caveat: Microsoft documents that dependencies are otherwise searched
by module name even when the top-level DLL was loaded by full path. Loading only
`C:\...\amdhip64_7.dll` is not a complete isolation design unless its
dependencies use the intended search locations too.

### Why `LoadLibraryExW` in the existing `main()` is too late

The current examples do not themselves call a loader API. Linking through
`hip::host`/`amdhip64.lib` creates ordinary PE imports on `amdhip64_7.dll`, so
the Windows loader selects it while creating the process.

Inspection of a representative compiled HIP executable in the supplied
distribution found ordinary imports including:

```text
__hipRegisterFatBinary
__hipRegisterFunction
__hipUnregisterFatBinary
__hipPushCallConfiguration
__hipPopCallConfiguration
hipLaunchKernel
```

The registration functions are compiler/runtime plumbing for embedded device
code and can be used by static initialization. Therefore this pattern cannot
repair the existing executable:

```cpp
int main() {
  LoadLibraryExW(known_amdhip64_path, ...);  // ordinary import was resolved earlier
  // ... existing HIP program ...
}
```

### Known-path designs that can work

#### Bootstrap executable

Ship a small launcher that has no HIP imports:

```text
MyApplication/
  launcher.exe             # no HIP import
  app/
    my_hip_application.exe # ordinary HIP import
```

The launcher:

1. Determines its own directory using `GetModuleFileNameW`, not `cwd`.
2. Selects an allowed ROCm version from an application-relative location,
   explicit configuration, or a supported central-runtime discovery API.
3. Resolves and validates the runtime `bin` directory.
4. Establishes a restricted DLL search policy or calls
   `SetDllDirectoryW(runtime_bin)`.
5. Creates the real process while that setting is active.

This converts the test-runner technique into a distributable application-owned
activation mechanism. The launcher should pass the selected runtime identity to
the child and the child should record/verify the loaded runtime when useful.

#### Host executable plus HIP implementation DLL

A same-process bootstrap can load the runtime itself instead of creating a
child:

```text
MyApplication/
  host.exe                 # no HIP imports
  app/
    hip_application.dll    # compiled HIP code and exported app entry point
```

The host performs this sequence:

1. Discover and validate the selected runtime directory.
2. Call `LoadLibraryExW` on the absolute `amdhip64_7.dll` path with restricted
   dependency-search flags.
3. Load `hip_application.dll` by absolute path.
4. Resolve an application-owned entry point such as `app_main` and call it.

When Windows resolves `hip_application.dll`'s `amdhip64_7.dll` imports, its
loaded-module check can reuse the runtime already loaded by the host. The HIP
module's static constructors and fat-binary registration run as that application
DLL is loaded, after the runtime is present.

This is materially simpler than resolving every HIP API with `GetProcAddress`,
but it changes the application shape and introduces a host-to-implementation
ABI. It also needs a complete dependency-search policy: the absolute path for
`amdhip64_7.dll` does not alone control later basename-only loads performed by
the runtime.

#### Delay-loaded HIP runtime

The linker can mark `amdhip64_7.dll` as delay-loaded. Application startup then
does not load it until a referenced symbol is first needed, allowing earlier
code to configure the search path.

For compiled HIP code, this requires explicit toolchain support because
compiler-generated fat-binary registration may be the first reference and may
run before `main()`. A custom delay-load notification hook can in principle
resolve and return the absolute-path module when that first delay thunk runs,
including during static initialization. A correct supported implementation
needs the linker options, delay-helper linkage, hook lifetime/ABI, dependent-DLL
policy, and compiler-generated registration paths validated together.
Initialization ordering across ordinary translation units is not a suitable
substitute for such a hook.

#### Explicit loader and dispatch table

An application can avoid a PE import on `amdhip64_7.dll` entirely, call
`LoadLibraryExW` with an absolute path and restricted flags, and obtain API
entry points with `GetProcAddress`. For HIP applications this also has to handle
compiler-generated registration and every API used by dependent libraries.

This is best exposed as a ROCm-owned stable loader/shim or API table. Requiring
each downstream project to duplicate hundreds of function signatures, version
negotiation, registration hooks, and error handling would create a new ABI and
security problem in every application.

### What “known path” should mean

Do not embed the developer SDK path found by CMake into the executable. That
path is machine-specific and commonly disappears after packaging. A
redistributable known path should be one of:

- Relative to an application-controlled installation root.
- Selected from versioned central installations by a documented ROCm discovery
  mechanism.
- Supplied through explicit administrator/application configuration and then
  canonicalized and validated.

If the runtime has dependent DLLs in the same directory, use
`LOAD_LIBRARY_SEARCH_DLL_LOAD_DIR` for the explicit load and a defined process
policy for later dynamic loads. Loading the top-level DLL by absolute path does
not automatically make every future basename-only plugin load deterministic.

Other APIs and patterns:

- `SetDefaultDllDirectories` and `AddDllDirectory` can establish a restricted
  process search policy for later loads.
- Python extensions loaded after interpreter startup can use
  [`os.add_dll_directory`](https://docs.python.org/3/library/os.html#os.add_dll_directory),
  retaining the returned handle for the necessary lifetime.
- Linker-supported
  [delay loading](https://learn.microsoft.com/en-us/cpp/build/reference/linker-support-for-delay-loaded-dlls)
  is necessary if application code must configure search behavior before an
  otherwise ordinary import is loaded.
- DLL redirection and side-by-side/package mechanisms exist but introduce
  additional packaging complexity and do not remove the need to own an
  explicit dependency set.

## System32 compatibility and the packaging RFC

[TheRock PR #3973](https://github.com/ROCm/TheRock/pull/3973) proposes a draft
Windows packaging RFC with these directions:

- New ROCm user-space runtimes live primarily under a versioned package root's
  `bin` directory.
- New components must not rely on System32 or global `PATH` for discovery.
- A dedicated compatibility MSI keeps HIP 5, HIP 6, and HIP 7 runtime entries
  in System32 during their support lifetimes.
- Package-local HIP 6 and HIP 7 runtimes already coexist with the compatibility
  surface.
- HIP 8 will not be installed in System32.
- Applications targeting HIP 8 need a secure package-local or explicit loading
  mechanism.

The RFC explicitly says the final HIP 8 mechanism is still to be determined;
candidate approaches include registry discovery, application-local deployment,
and fully qualified loading. Therefore, registry discovery should not yet be
documented as though it were a complete startup-loading solution.

The RFC also calls for versioned `amdhip64`, comgr, and hipRTC basenames where
their ABIs require coexistence. The reviewed artifact's `amdhip64_7.dll`
directly imports unversioned `amd_comgr.dll`, which is at least an apparent gap
between the current package-local build and the proposed redistributable
surface. The intended naming and transition should be clarified.

Current public HIP SDK deployment documentation still describes the legacy
model in which applications do not redistribute the HIP runtime and instead
use the driver-provided copy. That documentation must be updated in
coordination with the RFC and new installers; otherwise downstream developers
will receive contradictory guidance.

## ROCm project guidance

### Positive patterns

- Install ROCm-owned prebuilt tools and directly runnable tests in
  `<rocm-root>/bin` when they intentionally use the same runtime distribution.
- Keep test data and discovery metadata under `share` or `tests`; pass their
  locations as arguments or set `cwd` separately.
- For ephemeral runtime-built tests, use a dedicated parent launcher and a
  trusted, resolved artifact `bin` path.
- For redistributable examples/applications, stage one supported runtime
  closure into a temporary or application-owned output tree.
- Verify loaded paths, not only exit status.
- Test with a conflicting same-named System32 DLL present.

### Negative patterns

- Prepending `PATH` and assuming it overrides System32.
- Changing `cwd` and assuming it changes the executable directory.
- Copying all DLLs from a merged ROCm `bin` directory.
- Copying selected files into an extracted SDK/install while tests run.
- Calling loader configuration from `main()` for normal startup imports.
- Ignoring loader configuration or copy failures and continuing.
- Deriving a redistribution contract solely from static import scanning.

## Security considerations

- Accept loader directories only from trusted, validated configuration.
- Resolve paths and verify they are directories before use.
- Avoid user-controlled search directories in elevated processes.
- Prefer explicit/restricted search policies over global `PATH` changes.
- Remember that writable directories earlier in a search order can enable DLL
  preloading attacks.
- Treat application-local runtime copies as owned software that must receive
  security and compatibility updates.
- Do not assume a successfully loaded DLL is the expected build; record its
  path and, where appropriate, version or hash.

---

Prepared with OpenAI Codex.
