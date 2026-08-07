# Sources and Reference Index

This index favors primary documentation and permalinks. Access dates for all
web references are 2026-08-06 unless a snapshot is embedded in the URL.

## TheRock project material

- [PR #7143: fix dll issue in examples test](https://github.com/ROCm/TheRock/pull/7143)
  is the reviewed change.
- [PR #7143 patch](https://github.com/ROCm/TheRock/pull/7143.patch) is a compact
  machine-readable view of the change.
- [Issue #7132: hipThreads examples test fails on CS-RORDMZ Windows runner](https://github.com/ROCm/TheRock/issues/7132)
  records the original failure and the unintended `System32` module resolution.
- [Actions run 31094954012](https://github.com/ROCm/TheRock/actions/runs/31094954012?pr=7143)
  is the PR CI run used in this packet.
- [Windows hipthreads_examples job 92642280035](https://github.com/ROCm/TheRock/actions/runs/31094954012/job/92642280035)
  passed on an Azure Windows runner; it does not reproduce the affected
  CS-RORDMZ machine state.
- [PR #3973: Windows packaging requirements RFC](https://github.com/ROCm/TheRock/pull/3973)
  describes the proposed move away from installing the full HIP user-space
  runtime in `System32` and the compatibility-shim direction.
- [RFC0012 at the inspected PR commit](https://github.com/ROCm/TheRock/blob/2c6084ebe158d994cd900fd7942a3e6ea080aa8b/docs/rfcs/RFC0012-Windows_Packaging_Requirements.md)
  is the stable snapshot used during this review.
- [Issue #6711: testing policies](https://github.com/ROCm/TheRock/issues/6711)
  tracks the parallel testing-policy work.
- [Issue #7171: matrices Git LFS discrepancy](https://github.com/ROCm/TheRock/issues/7171)
  tracks the intentionally excluded artifact-size issue.
- [`test_hipthreads_examples.py` at the reviewed PR head](https://github.com/ROCm/TheRock/blob/019f1d87a941264bafbd1583d1fe5e5caef17d2d/build_tools/github_actions/test_executable_scripts/test_hipthreads_examples.py)
  provides the exact runner context.
- [`test_hiptests.py` on `main`](https://github.com/ROCm/TheRock/blob/main/build_tools/github_actions/test_executable_scripts/test_hiptests.py)
  contains the existing catch-test DLL-copy workaround discussed as migration
  work.
- [`windows_support.md` on `main`](https://github.com/ROCm/TheRock/blob/main/docs/development/windows_support.md)
  is the intended home for concise Windows platform guidance.
- [`native_packaging.md` on `main`](https://github.com/ROCm/TheRock/blob/main/docs/packaging/native_packaging.md)
  documents producer-side artifact packaging.
- [`python_packaging.md` on `main`](https://github.com/ROCm/TheRock/blob/main/docs/packaging/python_packaging.md)
  contains the “Using Packages from Frameworks” model that motivates a parallel
  native-application consumer guide.
- [HIP Windows installation documentation](https://rocm.docs.amd.com/projects/HIP/en/latest/install/install.html#windows)
  is relevant to the transition from the legacy deployed layout. It must be read
  together with the in-progress RFC while that transition is not complete.
- [Windows HIP SDK application deployment guidelines](https://rocm.docs.amd.com/projects/install-on-windows/en/develop/conceptual/deployment-guidelines.html)
  describe current ISV deployment expectations and explicitly state that static
  linking to HIP SDK components is unsupported.
- [CLR `amdhip64` target construction at the inspected rocm-systems commit](https://github.com/ROCm/rocm-systems/blob/90cbfbd55d944e16a6d9b1d6a0ed451f96831715/projects/clr/hipamd/src/CMakeLists.txt)
  contains both the default shared target and the upstream
  `BUILD_SHARED_LIBS=OFF` implementation branch. This is source capability, not
  by itself a Windows SDK support commitment.
- [CLR HIP packaging logic at the same commit](https://github.com/ROCm/rocm-systems/blob/90cbfbd55d944e16a6d9b1d6a0ed451f96831715/projects/clr/hipamd/packaging/CMakeLists.txt)
  switches installed library kind for static builds and helps identify the work
  that would be involved in producing a distinct static SDK configuration.
- [HIP documentation: creating static libraries](https://rocm.docs.amd.com/projects/HIP/en/docs-6.1.5/how-to/programming_manual.html#creating-static-libraries)
  concerns archiving application/library HIP code. Its examples still link the
  final application to `amdhip64`; it should not be interpreted as proof that
  the HIP runtime itself is statically linked.

## Microsoft Windows loader documentation

- [Dynamic-link library search order](https://learn.microsoft.com/en-us/windows/win32/dlls/dynamic-link-library-search-order)
  is the authoritative overview for packaged and unpackaged applications, safe
  DLL search mode, altered search paths, and the standard factors considered
  before ordinary directory searching.
- [`SetDllDirectoryW`](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-setdlldirectoryw)
  documents the process-wide directory setting, child-process inheritance, safe
  search-mode effect, and restoration behavior.
- [`AddDllDirectory`](https://learn.microsoft.com/en-us/windows/win32/api/libloaderapi/nf-libloaderapi-adddlldirectory)
  adds directories for search operations using the appropriate loader flags.
- [`SetDefaultDllDirectories`](https://learn.microsoft.com/en-us/windows/win32/api/libloaderapi/nf-libloaderapi-setdefaultdlldirectories)
  establishes a restricted process search policy.
- [`LoadLibraryExW`](https://learn.microsoft.com/en-us/windows/win32/api/libloaderapi/nf-libloaderapi-loadlibraryexw)
  documents explicit load flags such as `LOAD_LIBRARY_SEARCH_*`.
- [`GetProcAddress`](https://learn.microsoft.com/en-us/windows/win32/api/libloaderapi/nf-libloaderapi-getprocaddress)
  retrieves an exported function from an explicitly loaded module and is the
  primitive behind a manual dispatch-table design.
- [`GetModuleFileNameW`](https://learn.microsoft.com/en-us/windows/win32/api/libloaderapi/nf-libloaderapi-getmodulefilenamew)
  lets a bootstrap locate its own executable and derive application-relative
  paths without depending on the process working directory.
- [Linker support for delay-loaded DLLs](https://learn.microsoft.com/en-us/cpp/build/reference/linker-support-for-delay-loaded-dlls)
  describes the design that permits application code to run before a selected
  import is loaded.
- [Dynamic-link library security](https://learn.microsoft.com/en-us/windows/win32/dlls/dynamic-link-library-security)
  explains DLL preloading/binary-planting risk and mitigation principles.
- [Dynamic-link library redirection](https://learn.microsoft.com/en-us/windows/win32/dlls/dynamic-link-library-redirection)
  describes `.local` redirection, an older mechanism that is relevant background
  but not the recommended primary ROCm contract here.

## Linux loader and deployment documentation

- [`ld.so(8)`](https://man7.org/linux/man-pages/man8/ld.so.8.html) documents ELF
  dynamic-loader search behavior, `DT_RPATH`, `LD_LIBRARY_PATH`, `DT_RUNPATH`,
  the loader cache, default directories, token expansion, and secure-execution
  restrictions.
- [GNU `ld` runtime search path options](https://sourceware.org/binutils/docs/ld/Options.html#index-rpath)
  document `-rpath`/`-rpath-link` behavior used to create RUNPATH/RPATH metadata.
- [Filesystem Hierarchy Standard `/opt`](https://refspecs.linuxfoundation.org/FHS_3.0/fhs/ch03s13.html)
  describes add-on application packages.
- [Filesystem Hierarchy Standard `/usr/local`](https://refspecs.linuxfoundation.org/FHS_3.0/fhs/ch04s09.html)
  describes locally installed software under administrator control.
- [AppImage concepts](https://docs.appimage.org/introduction/concepts.html)
  describe an application bundle intended to run without traditional
  installation.
- [`linuxdeploy`](https://github.com/linuxdeploy/linuxdeploy) is a common tool for
  creating AppDir/AppImage-style application bundles by collecting dependencies
  and adjusting their runtime layout.
- [Flatpak basic concepts](https://docs.flatpak.org/en/latest/basic-concepts.html)
  describe the application/runtime model used instead of relying directly on a
  host-wide `/usr/local` deployment.

## CMake deployment mechanisms

- [`install()`](https://cmake.org/cmake/help/latest/command/install.html)
  is the base mechanism for defining application install trees.
- [`INSTALL_RPATH`](https://cmake.org/cmake/help/latest/prop_tgt/INSTALL_RPATH.html)
  controls the runtime path embedded in installed ELF targets.
- [`BUILD_RPATH_USE_ORIGIN`](https://cmake.org/cmake/help/latest/prop_tgt/BUILD_RPATH_USE_ORIGIN.html)
  helps make build-tree runtime paths relative on platforms supporting `$ORIGIN`.
- [`$<TARGET_RUNTIME_DLLS:tgt>`](https://cmake.org/cmake/help/latest/manual/cmake-generator-expressions.7.html#genex:TARGET_RUNTIME_DLLS)
  exposes the DLLs known through CMake's target dependency graph. This can help
  stage target dependencies, but it does not on its own define ROCm's supported
  redistributable closure or discover arbitrary runtime/plugin loads.
- [`file(GET_RUNTIME_DEPENDENCIES)`](https://cmake.org/cmake/help/latest/command/file.html#get-runtime-dependencies)
  can scan installed executables and libraries. CMake explicitly frames it as an
  install-time dependency-resolution mechanism; the same static-analysis limits
  apply to runtime-discovered modules.

## Inspection tools

- [Dependencies](https://github.com/lucasg/Dependencies) is the PE dependency
  inspection tool used locally through `Dependencies.exe -imports`.
- [Microsoft `dumpbin` `/DEPENDENTS`](https://learn.microsoft.com/en-us/cpp/build/reference/dependents)
  is another way to display imported DLL names when Visual Studio tools are
  available.

Static import tools answer “what does this PE file record in its import tables?”
They do not constitute a redistribution manifest and cannot prove the absence of
optional, plugin, delay-loaded, or programmatically loaded modules.

---

Prepared with OpenAI Codex.
