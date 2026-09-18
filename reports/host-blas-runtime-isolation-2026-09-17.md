# Managed host-BLAS runtime isolation assessment

Date: 2026-09-17. PR: [TheRock #8260](https://github.com/ROCm/TheRock/pull/8260). CI: [run 35147659193](https://github.com/ROCm/TheRock/actions/runs/35147659193), head `83e127c94a5a59d6cd7745c2dfe5e2dff3b1bbf7`.

## Conclusion

The packaging load-order fix works for the tested builds, but does not establish symbol isolation. TheRock's PyTorch already uses the managed LP64 OpenBLAS as its CPU BLAS, rather than introducing a second MKL BLAS alongside it in this PR. Linux additionally has a pre-existing hipSOLVER -> CHOLMOD/SuiteSparse -> host-BLAS runtime path. The change makes shared LAPACK a direct hipSOLVER dependency and subjects its GEEV calls to shared-symbol resolution.

For a distribution intended to coexist with arbitrary application BLAS libraries, recommend sysdep-equivalent isolation. Moving directories alone is unnecessary and insufficient. Private symbol names provide stronger isolation than a private SONAME or an ELF version node alone. This is not a claim that a wrong numerical result or binding was reproduced: Linux binaries were inspected on Windows, not executed.

## CI and configuration evidence

[Windows PyTorch job 105008300355](https://github.com/ROCm/TheRock/actions/runs/35147659193/job/105008300355) and [Linux release/2.12 job 105030547257](https://github.com/ROCm/TheRock/actions/runs/35147659193/job/105030547257) explicitly report finding the SDK's rocm-openblas import/shared library, USE_BLAS=1, and no enabled USE_MKL value. USE_MKLDNN=ON refers to oneDNN, not selection of MKL as BLAS. Saved excerpts: [Windows PyTorch evidence](D:/scratch/codex/host-blas-runtime-risk/windows-pytorch-evidence.log) and [Linux PyTorch evidence](D:/scratch/codex/host-blas-runtime-risk/linux-pytorch-evidence.log). These local evidence files remain in scratch and are not included in this repository.

The build script sets `BLAS=OpenBLAS`, `OpenBLAS_HOME=<SDK>/lib/host-math` and `OpenBLAS_LIB_NAME=rocm-openblas`. These settings and OpenBLAS preloading already existed in the parent of the integration commit (`git show 1c4cef227^:external-builds/pytorch/build_prod_wheels.py`). Therefore the former dependency was not purely test-only across the distribution. hipBLASLt clients are not evidence of a hipBLASLt runtime dependency; previous local inspection found OpenBLAS in hipblaslt-bench.exe imports, not libhipblaslt.dll's direct imports.

The installed-wheel sanity check executes only:

```python
import torch
print(torch.cuda.is_available())
```

A false GPU availability result is accepted. Successful builds/imports do not test GEEV correctness, mixed-BLAS loading, import-order effects, or CPU linear algebra. The run also passes ROCm wheel load tests; the overall run is marked failure for other checks, so do not call the entire workflow green.

## Inspected Linux artifact facts

Downloaded [host-blas_lib_generic.tar.zst](https://therock-ci-artifacts.s3.amazonaws.com/35147659193-linux/host-blas_lib_generic.tar.zst) (28,556,682 bytes) and [solver_lib_generic.tar.zst](https://therock-ci-artifacts.s3.amazonaws.com/35147659193-linux/solver_lib_generic.tar.zst) (3,790,811 bytes). Extracted only the regular `.so.0.3` OpenBLAS files and `libhipsolver.so.1.4` into `D:/scratch/codex/host-blas-runtime-risk/`.

| Library | Dynamic dependency / definitions |
|---|---|
| libhipsolver.so.1.4 | DT_NEEDED librocm-openblas.so.0; unversioned undefined sgeev_, dgeev_, cgeev_, zgeev_; also depends on libcholmod.so.5 |
| librocm-openblas.so.0.3 | SONAME librocm-openblas.so.0; unversioned definitions dgeev_, dgemm_, cblas_dgemm, openblas_get_config |
| librocm-openblas64.so.0.3 | SONAME librocm-openblas64.so.0; the same unversioned symbol spellings despite ILP64 ABI |

Both OpenBLAS DSOs have libc/libm/pthread dependencies, but no libgomp/libiomp or libgfortran in their direct DT_NEEDED entries. This avoids attributing a new OpenMP runtime to these specific builds; threaded BLAS resource use remains relevant. Both contain GLIBC version requirements but no export-version definition table: those GLIBC requirements are not ROCm symbol isolation. LP64 OpenBLAS contains PLT jump-slot relocations for dgemm_, dgemv_, dgeev_ and dgetrf_, showing that internal calls also participate in dynamic binding.

TheRock's host-blas CMake explicitly has a TODO for Linux symbol versioning. SYMBOLPREFIX/SYMBOLSUFFIX are not set. Local Windows ILP64 exports likewise retain unsuffixed dgeev_, dgemm_, cblas_dgemm names, but Windows resolves normal imports by DLL plus symbol rather than the ELF global lookup model.

## Risk model

1. **Library discovery versus symbol binding:** a private filename/SONAME and RPATH help load the intended file. They do not guarantee that an ELF relocation binds to a definition from that file. A system library merely being installed is not enough to cause a collision; it must enter the process/search path in a relevant way, for example via another extension, application linkage, loader environment, or global preloading.
2. **Linux mixed providers:** earlier global MKL/OpenBLAS/BLAS symbols can potentially satisfy ROCm's ordinary symbol references, and ROCm's globally loaded OpenBLAS can satisfy later consumers' references. Same-ABI providers can change backend behavior/performance; LP64 versus ILP64 mismatches can cause bad dimensions, memory access, corruption, or crashes. Load order and visibility determine whether this occurs. Not all NumPy/SciPy installations expose bare BLAS symbols; prefixed builds reduce this risk.
3. **Windows:** the private rocm-openblas.dll name is materially stronger isolation for normal imports. mkl_rt.dll/openblas.dll are not selected solely because they export dgemm_. Remaining concerns include another incompatible rocm-openblas.dll of the same name already loaded, path/packaging errors, and shared runtime/thread controls. The prior failure was missing dependency resolution, not observed symbol interposition.
4. **Shared state:** hipSOLVER's formerly single-threaded private dependency is replaced by the same threaded BLAS used by PyTorch CPU operations. Thread settings affect that shared instance. Concurrent workloads and oversubscription warrant tests independently of symbol correctness. Existing measured Windows performance differences remain a separate issue.
5. **Loading is enough:** direct DT_NEEDED loads the shared dependency even if an application never calls GEEV. A future rocSOLVER GEEV replacement does not by itself resolve existing PyTorch/SuiteSparse host-BLAS isolation.

## Isolation choices and alternatives considered

- **Preferred robust isolation:** private BLAS/LAPACK/control symbol names, with distinct LP64/ILP64 namespaces, private SONAMEs, correct RPATH/package closure, and consistent consumer linkage. OpenBLAS offers SYMBOLPREFIX/SYMBOLSUFFIX; its own redistribution guide recommends suffixing ILP64 to avoid clashes. Consumers must be updated too: hipSOLVER hand-declares geev_ functions, and PyTorch/SuiteSparse/clients and threading introspection cannot simply be assumed to adapt. Audit final exports, imports, and internal relocations; do not assume an option covers every symbol and every platform.
- **Existing sysdep-style ELF version nodes:** useful for recording required provider versions with lower source churn, but not identical to renaming symbols. A default-versioned export can remain eligible for unversioned lookups, and glibc has compatibility rules allowing unversioned interposers. Distinct LP64/ILP64 version nodes are necessary if using this strategy. Verify with deliberate mixed-provider binding tests before claiming full privacy.
- **Centrally built hidden static LAPACK:** preserves dependency provenance/no-fetch benefits while isolating hipSOLVER, if all relevant symbols and archive members are actually hidden/localized. Must verify exported symbols/internal binding, not assume static linkage alone is sufficient. Duplicates code and may require a dedicated single-thread configuration; does not fix the broader shared host-BLAS exposure already used by PyTorch.
- **RTLD_LOCAL / reordered preloads:** useful loading controls, not a complete ELF namespace boundary. RTLD_LOCAL does not prevent resolution against previously global definitions. Reordering merely changes who wins.
- **-Bsymbolic-functions alone:** can bind internal calls locally but does not privatize exported names or protect every consumer relocation; not a full solution.
- **dlmopen / RTLD_DEEPBIND:** not recommended as a small cross-platform fix; separate namespaces and altered lookup can complicate runtime integration and do not fit Windows.
- **Move to third-party/sysdeps:** reasonable organization/policy choice, but not technically required. Equivalent protections can be implemented under host-blas, retaining host-math CMake package compatibility.

## Proposed validation before broad coexistence claims

Use fresh processes for every order/configuration. Start with the exact CI wheels on Linux and Windows, record torch.__config__.show(), torch.backends.mkl.is_available(), BLAS config, loaded modules and thread counts. Exercise CPU matmul, solve and eig in all relevant dtypes, plus the hipSOLVER DnXgeev path directly or through a verified PyTorch dispatch. Do not assume torch.linalg.eig on ROCm reaches this particular implementation; inspect dispatch or run the hipSOLVER tests explicitly.

Test torch alone, NumPy/SciPy before and after torch, an available MKL-linked consumer in both orders, and isolated adversarial LP64/ILP64 loader probes. On Linux use LD_DEBUG=libs,bindings and/or an LD_AUDIT probe to capture actual GEEV and transitive BLAS binding (a dlsym result alone need not prove a PLT relocation's provider). On Windows inspect module paths/import tables. Test threading changes and concurrent CPU/GEEV workloads separately. Add artifact assertions for symbol namespaces/version requirements so isolation regressions fail without requiring GPU execution.

No repository implementation changes were made during this investigation.

## Sources

- [OpenBLAS redistribution guidance](https://www.openmathlib.org/OpenBLAS/docs/distributing/): LP64/ILP64 symbol isolation recommendation.
- [OpenBLAS build options](https://github.com/OpenMathLib/OpenBLAS/blob/develop/docs/build_system.md): naming controls.
- [Linux dlopen semantics](https://man7.org/linux/man-pages/man3/dlopen.3.html): global/local symbol lookup.
- [Windows loader search](https://learn.microsoft.com/en-us/windows/win32/dlls/dynamic-link-library-search-order): dependency lookup and loaded-module handling.
- [GNU ld version scripts](https://sourceware.org/binutils/docs/ld/VERSION.html): export version nodes and local visibility.
- [glibc symbol matching](https://github.com/bminor/glibc/blob/master/elf/dl-lookup.c): check_match compatibility behavior for unversioned definitions.
- [SciPy maintainer discussion](https://discuss.python.org/t/native-lib-loader-documentation-and-best-practices-on-using-native-libraries-in-python-wheels/98111): production use of both library and symbol renaming with consumer build metadata.
- [PyTorch backends](https://docs.pytorch.org/docs/stable/backends.html): MKL and oneDNN are distinct backend capabilities.

### Inspection commands

GitHub evidence was fetched with authenticated `gh api repos/ROCm/TheRock/actions/jobs/105008300355/logs` and the corresponding Linux job 105030547257, filtered into the evidence logs. Artifact download links are above. Run the following commands from `D:/scratch/codex/host-blas-runtime-risk/`, with LLVM tools from `D:/projects/TheRock/build/core/clr/dist/lib/llvm/bin` on `PATH`:

```powershell
Set-Location D:/scratch/codex/host-blas-runtime-risk
llvm-readobj.exe --dynamic-table --version-info third-party/host-blas/host-blas/stage/lib/host-math/lib/librocm-openblas.so.0.3
llvm-nm.exe -D --defined-only third-party/host-blas/host-blas/stage/lib/host-math/lib/librocm-openblas.so.0.3
llvm-readobj.exe --relocations third-party/host-blas/host-blas/stage/lib/host-math/lib/librocm-openblas.so.0.3
llvm-readobj.exe --dynamic-table math-libs/BLAS/hipSOLVER/stage/lib/libhipsolver.so.1.4
llvm-nm.exe -D math-libs/BLAS/hipSOLVER/stage/lib/libhipsolver.so.1.4
```

Repeat the OpenBLAS commands for `third-party/host-blas/host-blas64/stage/lib/host-math/lib/librocm-openblas64.so.0.3`. Dynamic tables and selected symbols remain in scratch: [LP64 dynamic table](D:/scratch/codex/host-blas-runtime-risk/host-blas-dynamic.txt), [LP64 symbols](D:/scratch/codex/host-blas-runtime-risk/host-blas-symbols.txt), [ILP64 dynamic table](D:/scratch/codex/host-blas-runtime-risk/host-blas64-dynamic.txt), and [ILP64 symbols](D:/scratch/codex/host-blas-runtime-risk/host-blas64-symbols.txt). Key output is transcribed above.

Generated with Codex.
