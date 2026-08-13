# ROCm `libatomic` dependency audit

**Date:** 2026-08-13  
**Primary source scope:** `D:/projects/TheRock/rocm-systems/projects/{rocprofiler,rocprofiler-sdk,roctracer}`  
**Packaging scope:** `D:/projects/TheRock` and its bundled Linux system-dependency mechanism  
**Binary scope:** `D:/scratch/codex/therock-dist-linux-gfx950-dcgpu-10.1.0a20260813`  
**Input inventory:** `D:/scratch/codex/libatomic_users.txt`

## Executive summary

The `libatomic.so.1` runtime dependency can be removed from the inspected ROCm Linux distribution without bundling `libatomic` as a new system dependency.

The August 13 distribution has one active shipped-code cause: `lib/roctracer/libroctracer_tool.so` uses a 16-byte `std::atomic<WriteIndex>` in roctracer's `TraceBuffer`. On x86-64, the selected compiler configuration lowers that compound atomic's load, store, and compare-exchange operations to symbols supplied by `libatomic.so.1`. The corresponding `trace_buffer` test has the same dependency. A second test, `memory_pool`, records a direct dependency only because CMake links `atomic` explicitly; it has no undefined `libatomic` symbols.

The rocprofiler-sdk family listed in `libatomic_users.txt` does **not** depend on `libatomic.so.1` in the inspected August 13 distribution. The inventory therefore describes a different artifact and is consistent with a source state or branch that predates the fix. Commit `83c6ceb242674551fba360d6d6c2fc2fb7ee2385` (2026-07-14) removed an SDK-wide `atomic` interface link and replaced the only large atomic object, an approximately 40-byte `std::atomic<ptrace_data_t>`, with ordinary data synchronized by existing release/acquire flag operations.

The old `projects/rocprofiler` tree contains several explicit CMake links to `atomic` and a copy of the same compound `TraceBuffer` implementation. However, its active buffer instances were removed in 2024, and TheRock no longer builds that legacy project. These declarations appear stale and should be removed if the project remains buildable, but they do not explain the inspected distribution.

Recommended resolution:

1. Redesign roctracer's `TraceBuffer` to avoid a 16-byte atomic while preserving the concurrent reservation fast path.
2. Remove `atomic` from the roctracer tool and its two affected test link lines.
3. Remove the stale `atomic` declarations from legacy `projects/rocprofiler`, with a standalone build to catch any overlooked use.
4. Add distribution-level checks for both `DT_NEEDED: libatomic.so.1` and unresolved `__atomic_*@LIBATOMIC_*` symbols.
5. Remove `libatomic1` from the Linux installation prerequisite only after supported-architecture artifacts pass those checks.

This does not, by itself, permit removal of the entire documented `sudo apt install libatomic1 libquadmath0` command. `libquadmath.so.0` is a separate, genuine dependency of the packaged Flang drivers `bbc` and `flang-23` and needs its own source, linkage, or sysdeps solution.

## Problem statement and requirements

The current [ROCm Linux installation instructions](https://rocm.docs.amd.com/en/latest/install/rocm.html) tell users to install `libatomic1` and `libquadmath0` from the host distribution:

```console
sudo apt install libatomic1 libquadmath0
```

That conflicts with the portable-package goal used by TheRock:

- ROCm packages should be self-contained rather than depending on packages preinstalled by the host distribution.
- Necessary system-level libraries should normally be built and packaged privately through `third-party/sysdeps`.
- Private sysdeps are installed under `lib/rocm_sysdeps`, use ROCm-specific SONAMEs and symbol versions, and are found through origin-relative RPATHs.
- Dependencies that can be eliminated safely in source should be pruned instead of vendored.

The distinction between `std::atomic` and `libatomic` is important. Most `std::atomic<bool>`, `std::atomic<int>`, pointer atomics, and naturally aligned machine-word atomics compile to CPU instructions or compiler intrinsics and do not create a dynamic dependency. A compiler generally calls `libatomic` when the requested width or operation is not natively supported for the configured target. Therefore, the presence of other `std::atomic` code in ROCm is not evidence that ROCm must link `libatomic` globally.

For this audit, success means no shipped ELF object needs `libatomic.so.1`; it does not merely mean changing a dynamic dependency into a static one or supplying a copy under another path.

## Inspection method

### Source and build files

The inspection searched for:

- Explicit `atomic` entries in `target_link_libraries`.
- `std::atomic` objects wider than a native machine word.
- Compound atomic load, store, and compare-exchange operations.
- Actual template instantiations and calls, rather than header declarations alone.
- TheRock subprojects that determine what is built and packaged.
- Relevant source history explaining when dependencies were introduced or removed.

Representative commands:

```powershell
rg -n "atomic|WriteIndex|write_index_|TraceBuffer<" `
  D:\projects\TheRock\rocm-systems\projects\roctracer `
  D:\projects\TheRock\rocm-systems\projects\rocprofiler `
  D:\projects\TheRock\rocm-systems\projects\rocprofiler-sdk

rg -n "rocprofiler|roctracer" D:\projects\TheRock\profiler\CMakeLists.txt

git -C D:\projects\TheRock\rocm-systems show 83c6ceb242
git -C D:\projects\TheRock\rocm-systems show 3c4467274f
git -C D:\projects\TheRock\rocm-systems show b9bc6d7bd5
git -C D:\projects\TheRock\rocm-systems show f1bce685df
```

### Binary files

The extracted distribution was searched as binary data for the relevant SONAMEs. Every hit was then checked with `readelf` to distinguish a real ELF `DT_NEEDED` record from an incidental string and to find unresolved provider-specific symbols.

```powershell
rg -a -l "libatomic\.so\.1" `
  D:\scratch\codex\therock-dist-linux-gfx950-dcgpu-10.1.0a20260813

readelf -d <file>
readelf --dyn-syms --wide <file>
```

The `.so` and `.so.1` entries for rocprofiler-sdk in the Windows extraction are zero-length symbolic links. Inspection was performed on their real versioned targets, such as `librocprofiler-sdk.so.1.3.5`, rather than on the link placeholders.

Some archive directory symlinks, including the top-level `llvm` and `amdgcn` aliases, could not be traversed by `rg` in the Windows extraction. Their materialized target trees were inspected directly. This limitation should still be avoided in the final CI check by running the dependency scan on Linux, where archive symlinks have their normal semantics.

## Binary findings

### `libatomic.so.1`

Only three materialized ELF files in the inspected distribution contain a real `DT_NEEDED` entry for `libatomic.so.1`:

| Installed file | Undefined `libatomic` symbols | Classification |
|---|---|---|
| `lib/roctracer/libroctracer_tool.so` | `__atomic_load_16`, `__atomic_store_16`, `__atomic_compare_exchange` | Active runtime dependency |
| `share/roctracer/test/trace_buffer` | Same three operations | Active test dependency using the same implementation |
| `share/roctracer/test/memory_pool` | None | Unused direct link retained as `DT_NEEDED` |

All three are ELF64 x86-64 objects. `memory_pool` contains normal libstdc++ atomic/futex references, but no unresolved symbol versioned to `LIBATOMIC_1.0`; those libstdc++ symbols are not evidence of a `libatomic` code requirement.

The following components named in `libatomic_users.txt` were checked through their real versioned ELF files and do not have `DT_NEEDED: libatomic.so.1` or unresolved `__atomic_*@LIBATOMIC_*` symbols in the August 13 distribution:

- `librocprofiler-sdk.so.1`
- `librocprofiler-sdk-rocpd.so.1`
- `librocprofiler-sdk-roctx.so.1`
- `librocprofiler-sdk-attach.so.1`
- `librocprofiler-sdk-rocattach.so.1`
- `librocprofiler-sdk-tool.so.1`
- `librocprofiler-sdk-tool-kokkosp.so.1`
- `librocprofv3-list-avail.so.1`
- the packaged `libpyrocpd.cpython-*.so` Python extension variants

The direct-readelf inventory can be valid evidence for another artifact, but it is not the dependency closure of the supplied distribution. The most likely explanation is an older source state or a branch that does not contain the July fix.

### `libquadmath.so.0`

No `libatomic` or `libquadmath` shared library was found under the distribution's `lib/rocm_sysdeps` tree. Five LLVM executables have `DT_NEEDED: libquadmath.so.0`:

| Installed file | Undefined `QUADMATH_1.0` symbols | Classification |
|---|---|---|
| `lib/llvm/bin/bbc` | Many, including `logq`, `ctanhq`, `atan2q`, `y1q`, and `cacoshq` | Active dependency |
| `lib/llvm/bin/flang-23` | Same class of functions | Active dependency |
| `lib/llvm/bin/tco` | None found | Apparently retained/unused link |
| `lib/llvm/bin/fir-opt` | None found | Apparently retained/unused link |
| `lib/llvm/bin/fir-lsp-server` | None found | Apparently retained/unused link |

This is outside the original rocprofiler source question but directly relevant to removing the documented host-package prerequisite.

## Source findings by case

### Case 1: roctracer runtime tool — active compound atomic

**Source files inspected**

- `projects/roctracer/src/tracer_tool/trace_buffer.h`
  - Lines 187-231 implement reservation and buffer transitions.
  - Lines 259-271 declare `WriteIndex` and `std::atomic<WriteIndex>`.
- `projects/roctracer/src/tracer_tool/tracer_tool.cpp`
  - Lines 227, 268, and 407 instantiate buffers for ROCTX, HSA, and HIP records.
  - Lines 238, 285, and 426 call `Emplace` on those buffers.
- `projects/roctracer/src/CMakeLists.txt:232`
  - Unconditionally links `roctracer_tool` with `atomic`.

**Nature and reason for the dependency**

`WriteIndex` is:

```cpp
struct WriteIndex {
  uint64_t index;
  Entry* buffer;
};

std::atomic<WriteIndex> write_index_;
```

On the inspected 64-bit target this is a 16-byte atomic. It deliberately keeps the monotonically increasing reservation index and the pointer to the allocation containing that index consistent as one indivisible value. `GetEntry` uses atomic loads and a compare-exchange loop for ordinary reservations. At an allocation boundary, a writer takes `write_mutex_`, selects the free buffer, and atomically publishes the new `{index, buffer}` pair.

The design was introduced to correct real races. Commit `f1bce685dfb41e788900f8c0ecf1341295049dd7` records that the earlier index and data pointer could become inconsistent and that flushing could observe incompletely published records. Any replacement must preserve that invariant rather than simply changing the type.

The compiler emits calls to `__atomic_load_16`, `__atomic_store_16`, and generic `__atomic_compare_exchange`; these are the actual imports observed in `libroctracer_tool.so`.

**Recommended change**

Replace the compound atomic with separately represented state, using only native-width atomics:

```cpp
std::atomic<uint64_t> write_index_;
std::atomic<Entry*> write_buffer_;
```

A safe algorithm must preserve these ordering rules:

1. For an ordinary reservation, acquire-load the current index, load the current buffer pointer, and reserve by compare-exchanging only the index.
2. Treat a successful index CAS as validation that no buffer-boundary transition occurred between observing the index/pointer pair and claiming the slot. If it fails, reload both values and retry.
3. At a boundary, continue using `write_mutex_`. Publish the new atomic buffer pointer before a release-store of the advanced index.
4. Readers acquire-load the index before using the associated buffer pointer. Subsequent index read-modify-write operations must preserve the release sequence from the boundary publication.
5. Keep the entry-level release/acquire protocol that publishes record completion before flushing.

The exact memory-order implementation deserves focused review. It should be accompanied by an invariant comment because a later “simplification” to relaxed operations could reintroduce the race fixed in 2022.

After the source change, remove `atomic` from `projects/roctracer/src/CMakeLists.txt`.

**Tradeoffs and risks**

- The split state is more subtle than one compound atomic. Correctness depends on the reservation CAS proving that the pointer corresponds to the claimed index and on the boundary publication order.
- A pointer load can overlap a boundary update, so the pointer must itself be atomic unless every access is placed under the mutex. A plain pointer would create a C++ data race even when the subsequent index CAS fails.
- `uint64_t` and pointer atomics are natively supported on the intended 64-bit x86-64 and AArch64 classes of targets, but this must be verified for every supported Linux architecture. A future 32-bit port could again require `libatomic` for the 64-bit counter.
- CPU architecture and compiler target flags matter more than the Linux distribution. Debian versus RPM packaging does not change whether an atomic is lock-free, but different compiler baselines can change code generation.
- Forcing `CMPXCHG16B` with `-mcx16` is x86-specific, may raise the minimum CPU requirement, does not address other architectures, and is not recommended as the package-level solution.
- Replacing all reservations with a mutex is simpler to reason about but serializes every traced event and could regress tracing overhead. It is a reasonable fallback only if measurement shows the impact is acceptable.

### Case 2: roctracer `trace_buffer` test — active test dependency

**Files inspected**

- `projects/roctracer/test/directed/trace_buffer.cpp:57` instantiates the same `TraceBuffer` template.
- `projects/roctracer/test/CMakeLists.txt:144` explicitly links `atomic`.
- Packaged executable `share/roctracer/test/trace_buffer` imports the same three `libatomic` operations as the runtime tool.

**Recommended change**

The source redesign from Case 1 should remove the test's real symbol requirement. Remove `atomic` from its CMake link line at the same time.

This test is particularly valuable for validating the rewrite: it already creates multiple threads and a deliberately small buffer. It should be strengthened to stress repeated boundary transitions and to verify that each reserved entry is delivered exactly once, without gaps, duplicates, stale-buffer writes, or premature destruction.

**Tradeoffs and risks**

Removing the dependency without strengthening the concurrency assertions risks trading a visible package problem for a rare tracing corruption. Run the test repeatedly and under ThreadSanitizer where the supported build configuration permits it.

### Case 3: roctracer `memory_pool` test — unused retained dependency

**Files inspected**

- `projects/roctracer/test/directed/memory_pool.cpp:73` uses `std::atomic<int>` for a callback counter.
- `projects/roctracer/test/CMakeLists.txt:150` explicitly links `atomic`.
- Packaged executable `share/roctracer/test/memory_pool` has `DT_NEEDED: libatomic.so.1` but no unresolved `LIBATOMIC_1.0` symbols.

**Nature of the dependency**

The integer counter is a native-width atomic and does not require `libatomic` on the inspected target. The dynamic dependency is retained solely because of the unconditional CMake link under this target's linker settings; unused-library elimination did not remove it.

**Recommended change**

Remove `atomic` from `target_link_libraries(memory_pool ...)`. Keep `std::atomic<int>`; changing the counter to a non-atomic integer would be incorrect if callbacks can execute concurrently.

**Tradeoffs and risks**

This is a low-risk build-only cleanup. The test should continue to compile and link without `-latomic`. It also demonstrates why searching source for `std::atomic` produces false positives: a source-level atomic does not imply a dynamic `libatomic` dependency.

### Case 4: rocprofiler-sdk family — fixed dependency in an older inventory

**Files and history inspected**

- `D:/scratch/codex/libatomic_users.txt` lists the SDK core, rocpd, roctx, attach, rocattach, tool plugins, list tool, and Python bindings as direct users.
- Commit `83c6ceb242674551fba360d6d6c2fc2fb7ee2385`, “remove libatomic dependency from ROCm.”
- `projects/rocprofiler-sdk/cmake/rocprofiler_config_interfaces.cmake:85-90`, where only an empty historical “atomic library” section remains.
- `projects/rocprofiler-sdk/source/lib/rocprofiler-sdk-rocattach/ptrace_runner.cpp`, which now uses plain request/result data with release/acquire synchronization through atomic flags.
- The real versioned SDK and binding ELFs in the August distribution.

**Nature of the old dependency**

Before the July 2026 change, rocattach stored an approximately 40-byte `ptrace_data_t` as `std::atomic<ptrace_data_t>`. Such an object is not lock-free on the target and required `libatomic`. An interface target propagated the link widely through the SDK, so many outputs recorded direct `DT_NEEDED` entries even though only the ptrace runner needed large atomic operations.

The fix replaced the large atomic payload with ordinary data and used an existing atomic `running` flag as the publication protocol:

- Producer writes request data, then release-stores `running = true`.
- Worker acquire-loads `running`, reads the request, writes the result, then release-stores `running = false`.
- Producer observes completion with acquire semantics before reading the result.

The same commit removed the atomic interface and downstream CMake links.

**Recommended change**

No further code change is needed for the SDK components in the inspected tree. Preserve the fix and add binary closure checks so a broad interface link or another large atomic cannot silently reintroduce the dependency.

The empty “atomic library” comment block in `rocprofiler_config_interfaces.cmake` can be removed as cleanup; leaving it may incorrectly suggest that a target is missing.

**Tradeoffs and risks**

- Correctness now depends on the documented release/acquire handoff and the rule that only one request is in flight. Those comments and the in-flight guard should be retained.
- Binary validation must inspect the real versioned files, not zero-length symlink entries from a Windows extraction.
- The old inventory should retain its artifact identifier if used in future comparisons. A filename without build provenance can be mistaken for current state.

### Case 5: legacy `projects/rocprofiler` — stale source declarations

**Files inspected**

Explicit `atomic` links remain in:

- `projects/rocprofiler/src/api/CMakeLists.txt:326-331` for `rocprofiler-v2` / `librocprofiler64.so.2`.
- `projects/rocprofiler/src/tools/CMakeLists.txt:34-36` for `rocprofiler_tool`.
- `projects/rocprofiler/plugin/cli/CMakeLists.txt:44-45` for `cli_plugin`.
- `projects/rocprofiler/test/CMakeLists.txt:216-224` for a test library.
- `projects/rocprofiler/tests-v2/unittests/core/CMakeLists.txt:236-243` for core unit tests.
- `projects/rocprofiler/src/tools/rocprofv2/CMakeLists.txt:40-42`; this subdirectory is currently disabled by its parent CMake file.

The tree also retains `projects/rocprofiler/src/tools/trace_buffer.h`, including the same 16-byte compound atomic at lines 259-271. `tool.cpp` includes the header and invokes `TRACE_BUFFER_INSTANTIATE()`, but that macro only defines `TraceBufferBase` static members. It does not instantiate `TraceBuffer<Entry>`.

History confirms the distinction:

- Commit `4ba25a5c39` added three active buffer instances on 2023-05-11.
- Commit `bfa7ace4b4` removed those instances on 2024-05-31.
- The explicit CMake `atomic` links remained.

TheRock's `profiler/CMakeLists.txt` builds `projects/rocprofiler-sdk` and deprecated `projects/roctracer`; it does not declare `projects/rocprofiler` as a subproject. No legacy rocprofiler ELF from this source tree was present among the `libatomic` hits in the inspected distribution.

**Recommended change**

Remove the stale `atomic` entries and, if the legacy project is still expected to build independently, run its targeted libraries and tests through a no-`libatomic` link and ELF scan. Consider deleting the unused `trace_buffer.h` and its include/static-instantiation macro if no downstream build relies on that private header.

**Tradeoffs and risks**

- The project is not exercised by the inspected TheRock configuration, so source inspection alone cannot prove that every optional standalone configuration is clean.
- Linker `--as-needed` settings can hide stale declarations from `DT_NEEDED`, while other linkers or build modes retain them. Removing the declarations is preferable to relying on as-needed behavior.
- Because this is legacy code, the lowest-risk scope is build cleanup and deletion of provably unused private code rather than a new concurrency redesign.

### Case 6: `libquadmath` in packaged LLVM/Flang — independent system dependency

**Files inspected**

- Packaged `lib/llvm/bin/{bbc,flang-23,tco,fir-opt,fir-lsp-server}`.
- `DT_NEEDED` entries and versioned undefined dynamic symbols.
- The packaged `lib/rocm_sysdeps` tree.

**Nature of the dependency**

`bbc` and `flang-23` make real calls to GCC quad-precision math routines. The other three tools retain the SONAME without observed undefined quadmath symbols and may be cleanable through link-interface changes or `--as-needed` behavior.

**Recommended change**

Treat this as a separate compiler-toolchain audit:

1. Identify the LLVM/Flang CMake target that propagates `quadmath` to all five tools.
2. Remove unused propagation from `tco`, `fir-opt`, and `fir-lsp-server`.
3. For `bbc` and `flang-23`, decide whether to bundle a private compatible implementation through sysdeps, replace the implementation/linkage, or alter which tools are shipped.
4. Do not remove `libquadmath0` from the install instructions until the real Flang imports are satisfied within the distribution.

**Tradeoffs and risks**

- Unlike the stale links, removing `quadmath` from the two active users without a replacement will cause load or runtime failure.
- A bundled compiler-runtime library needs license review, stable private SONAME treatment, compatible symbol versions, and testing across the oldest supported glibc and CPU baselines.
- Omitting Flang tools reduces distribution functionality and should be an explicit packaging decision, not an incidental dependency fix.

## Alternatives considered

### Statically link `libatomic`

This was attempted in roctracer by commit `3c4467274f741bad0589259fb0e01d87f7f6c421` in 2024, using `-Wl,-Bstatic atomic -Wl,-Bdynamic` for the runtime tool and tests. Commit `b9bc6d7bd595dd57c762fe0cd7000c6369f44460` reverted it shortly afterward without a detailed rationale.

Static linkage would remove `DT_NEEDED: libatomic.so.1` but retain the code and licensing dependency. It also depends on the static archive being installed in the build toolchain and does not meet the stronger goal of pruning the dependency. It is not recommended.

### Bundle `libatomic` through `third-party/sysdeps`

This could make the runtime package self-contained, but it is a poor fit when one source data structure is the only active need. The July SDK removal commit explicitly says `libatomic` could not be included in the ROCm install because of licensing issues. A sysdeps solution would also require source provenance, license approval, private SONAME/symbol-version rewriting, RPATH integration, and cross-toolchain compatibility.

Bundling remains a fallback only if the roctracer concurrency design cannot be safely expressed using native-width atomics.

### Serialize all trace-buffer reservations with a mutex

This is the simplest correctness model and avoids compound atomics portably. Its cost is serialization on a high-frequency tracing path, potentially compounded by existing flush and buffer-transition work protected by `write_mutex_`. It should be considered only with trace-overhead measurements.

### Require a 16-byte native atomic instruction

Enabling `-mcx16` can change x86-64 code generation, but it changes the CPU contract and is not portable to AArch64 or other targets. Compiler behavior for 16-byte C++ atomics also varies by toolchain. This is not a distribution-wide solution.

## Portability and packaging considerations

- **Distribution independence:** Removing the dependency in source avoids differences in package names, installed paths, and default availability between Debian/Ubuntu, RHEL-family, SUSE, and container base images.
- **Architecture independence:** The proposed split assumes native pointer and 64-bit atomics. Verify x86-64 and AArch64 artifacts separately. If ROCm ever supports a 32-bit host ABI, reassess the counter width or use a different synchronization scheme.
- **Compiler independence:** Validate with every supported compiler/toolchain combination. Whether an atomic operation becomes a library call is a compiler and target decision, not solely a C++ source property.
- **Linker independence:** Do not treat `--as-needed` as the fix. A CMake dependency that is harmless with one linker can become a `DT_NEEDED` entry with another configuration.
- **Loader isolation:** If a compiler runtime is eventually bundled, it must follow the sysdeps private-SONAME and RPATH model. Shipping an unmodified `libatomic.so.1` or `libquadmath.so.0` beside ROCm libraries risks collision with host copies already loaded into a process.
- **Deprecation:** roctracer is described in TheRock as very old and deprecated, but it is still packaged for compatibility. Deprecation reduces the expected lifetime of the fix; it does not remove the need for correctness while the binary remains shipped.

## Recommended implementation and validation plan

### Source changes

1. Rework `projects/roctracer/src/tracer_tool/trace_buffer.h` to use native-width atomic state while preserving the index/buffer association invariant.
2. Remove `atomic` from the roctracer runtime and test CMake links.
3. Strengthen the trace-buffer test around concurrent boundary transitions.
4. Remove stale `atomic` links and unused buffer code from legacy `projects/rocprofiler`, subject to its standalone support expectations.
5. Remove the empty atomic section from the rocprofiler-sdk CMake interface file as optional cleanup.

### Targeted correctness testing

- Run the trace-buffer test repeatedly with many producer threads, a very small buffer, and enough entries to cross thousands of allocation boundaries.
- Assign a unique sequence value to every produced record and verify exactly-once delivery.
- Exercise concurrent explicit flushes while producers are active.
- Exercise construction, final flush, and destruction after all producers join.
- Run roctracer HIP, HSA, and ROCTX functional tracing tests.
- Run ThreadSanitizer where possible, recognizing that GPU/runtime integration may require isolating the CPU-only buffer test.
- Compare tracing overhead before and after the change; the hot path should remain a native-width atomic CAS rather than a global mutex acquisition.

### Build and packaging validation

Build with no linkable `libatomic` available and retain `-Wl,--no-undefined` on the roctracer tool. Then scan the materialized Linux install tree:

```bash
find "$ROCM_DIST" -type f -print0 |
  xargs -0 -r file |
  awk -F: '/ELF/{print $1}' |
  while IFS= read -r elf; do
    readelf -d "$elf" 2>/dev/null | grep -q 'libatomic\.so\.1' && echo "$elf"
  done
```

Also scan undefined dynamic symbols, since a missing `DT_NEEDED` can still indicate an incorrectly unresolved shared-library build:

```bash
readelf --dyn-syms --wide <elf> | grep 'UND.*__atomic_.*LIBATOMIC'
```

The release gate should require:

- No `DT_NEEDED: libatomic.so.1` in runtime, development, test, or Python artifacts.
- No unresolved `__atomic_*@LIBATOMIC_*` symbols.
- No explicit `-latomic`/`atomic` link interfaces in installed CMake package metadata.
- Successful dependency closure in a minimal Linux container without `libatomic1` installed.
- Equivalent scans for every supported host architecture.

Once those checks pass in release artifacts, remove `libatomic1` from the public installation instructions. Keep `libquadmath0` until its separate closure is resolved.

## Other relevant observations

1. **The authoritative answer is the packaged ELF closure.** Source searches find possible causes, but explicit links can be dropped by as-needed behavior and transitive interfaces can affect binaries whose own sources contain no atomics.
2. **Record artifact provenance with dependency inventories.** `libatomic_users.txt` was useful, but without a build commit or artifact ID it appeared to contradict the newer tarball. Future reports should include the artifact URL/hash, build commit, target architecture, and exact inspection command.
3. **Check installed CMake exports as well as ELFs.** A package can be runtime-clean while still exporting `atomic` to downstream developers, recreating the host dependency when users link their own tools.
4. **Generalize the closure test.** A small allowlist-based CI audit for non-ROCm SONAMEs would catch `libatomic`, `libquadmath`, and similar regressions earlier than installation documentation testing.
5. **Separate runtime and test closure, but validate both.** Test artifacts may not be installed for end users, yet they reveal source/build problems and can break CI on minimal builders.
6. **Do not remove normal `std::atomic` uses indiscriminately.** Native-width atomics are appropriate and do not imply `libatomic`. Changes should target large/non-lock-free atomic objects and unnecessary build links.

## Conclusion

For the inspected distribution, `libatomic1` is not a broad ROCm requirement. It is the consequence of one active 16-byte compound atomic in deprecated-but-shipped roctracer plus one test of that code, with a third test carrying a stale link. rocprofiler-sdk has already demonstrated the preferred remedy: express the synchronization protocol using ordinary data and native-width atomics, then remove broad CMake propagation.

Completing the roctracer redesign and enforcing ELF closure in CI should allow ROCm to remove the `libatomic1` host prerequisite without adding `libatomic` to sysdeps. `libquadmath0` remains an independent task before the complete installation command can be deleted.
