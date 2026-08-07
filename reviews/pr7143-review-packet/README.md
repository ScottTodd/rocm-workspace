# TheRock PR #7143: Windows DLL Loading Review Packet

This directory captures the investigation and design discussion around
[ROCm/TheRock PR #7143](https://github.com/ROCm/TheRock/pull/7143), which
changes the hipthreads example test runner to copy every DLL from the merged
ROCm artifact `bin` directory beside each example executable on Windows.

The packet is intended to be shareable with the hipthreads team and useful to
future reviewers, documentation authors, and implementation agents. It
separates the immediate PR decision from the broader runtime packaging design.

## Snapshot

- Reviewed: 2026-08-06
- PR state: open, not draft
- PR head: `019f1d87a941264bafbd1583d1fe5e5caef17d2d`
- Base: `main`
- Changed files: one
- Net diff: eight additions
- Related failure: [TheRock issue #7132](https://github.com/ROCm/TheRock/issues/7132)
- Windows packaging RFC: [TheRock PR #3973](https://github.com/ROCm/TheRock/pull/3973), still draft/open at this snapshot

The PR head was refreshed before writing this packet and was unchanged from the
earlier investigation.

## Bottom line

The diagnosis is correct: prepending the artifact `bin` directory to `PATH`
does not override a same-named DLL in `System32`. The proposed fix is too broad:
it copies an unbounded set of unrelated DLLs into each example build directory,
mutates the extracted ROCm installation, and scales badly when artifacts are
merged into a full distribution.

Two acceptable directions emerged:

1. For the narrow PR fix, have the existing single-threaded test runner call
   `SetDllDirectoryW(<artifact-root>/bin)` around its child-process launches.
   This is the Windows analogue, in architectural role, to the runner's current
   Linux use of `LD_LIBRARY_PATH`. It makes execution through the harness
   reliable but does not make the resulting executable independently
   redistributable.
2. For the fuller example/deployment design, make each example CMake project
   stage an explicitly supported HIP runtime closure into a temporary binary or
   install tree, then execute that self-contained result. The runner should
   build outside the artifact/install tree. This requires an authoritative ROCm
   redistribution manifest or helper; neither a `bin/*.dll` glob nor PE-import
   scanning alone is a sufficient contract.

A third deployment architecture is a known-path loader. The practical form for
ordinary compiled HIP programs is an application-owned bootstrap executable
that locates a selected ROCm runtime, configures a restricted DLL search path,
and then starts the real HIP executable. A same-process variant can load the
selected runtime by absolute path and then load a HIP application-implementation
DLL. Calling `LoadLibraryExW` from the current example's `main()` is too late
because its ordinary HIP imports,
including compiler-generated fat-binary registration APIs, are resolved before
`main`. A fully in-process design would require delay loading plus sufficiently
early setup, or a ROCm-provided explicit loader/dispatch ABI.

Static linking was also investigated as a possible redistributable-application
model. It is not an available solution from the reviewed Windows SDK: the
packaged `amdhip64.lib` is an import library for `amdhip64_7.dll`, the CMake
target is exported as `SHARED`, and current AMD Windows deployment guidance says
static linking to HIP SDK components is unsupported. It remains a possible
future product capability if ROCm deliberately builds, packages, licenses, and
supports a complete static runtime closure.

## File map

- [01-pr-review.md](01-pr-review.md): Review findings, CI evidence, acceptable
  fixes, and a ready-to-post review comment.
- [02-windows-dll-loading-and-rocm.md](02-windows-dll-loading-and-rocm.md):
  Windows loader behavior, ROCm implications, application-local deployment,
  central-install options, and the packaging RFC transition.
- [03-windows-vs-linux-runtime-loading.md](03-windows-vs-linux-runtime-loading.md):
  Cross-platform comparison covering `SetDllDirectoryW`, `LD_LIBRARY_PATH`,
  ELF RUNPATH/`$ORIGIN`, system packages, and portable application bundles.
- [04-hipthreads-examples-architecture.md](04-hipthreads-examples-architecture.md):
  Current build/test flow, target-neutral artifact constraint, recommended
  immediate and longer-term architectures, and test criteria.
- [05-local-evidence-and-reproduction.md](05-local-evidence-and-reproduction.md):
  Exact local paths, measurements, loader collision proof, dependency scans,
  commands, outputs, and limitations.
- [06-documentation-and-policy-followups.md](06-documentation-and-policy-followups.md):
  Proposed project-wide testing and packaging guidance, migration candidates,
  unresolved design questions, and alternatives considered.
- [sources.md](sources.md): Annotated primary references and project links.
- [probes/report_loaded_module.py](probes/report_loaded_module.py): Generic
  Windows probe that loads a DLL by basename and prints its resolved path.
- [probes/run_child_with_dll_directory.py](probes/run_child_with_dll_directory.py):
  Generic parent launcher demonstrating inherited `SetDllDirectoryW` behavior.
- [probes/README.md](probes/README.md): Usage, expected experiment shape, and
  limitations for the reusable probes.

## Evidence labels

The documents use these distinctions:

- **Verified locally:** observed using the supplied artifacts on the review
  machine.
- **Verified from PR/CI metadata:** observed through the GitHub REST API or PR
  diff.
- **Documented platform behavior:** supported by Microsoft, Linux manual pages,
  CMake, FHS, AppImage, or Flatpak documentation.
- **Recommendation:** a proposed design choice rather than existing policy.
- **Open question:** not settled by current implementation or the draft RFC.

## Scope exclusions

The Linux/Windows `matrices.tgz` Git LFS size discrepancy is intentionally
excluded. It is tracked separately in
[TheRock issue #7171](https://github.com/ROCm/TheRock/issues/7171).

## Sharing notes

The local paths in the evidence file identify the exact inputs used for the
measurements. They are not expected to exist on another machine. The source
links, commands, hashes, byte counts, and generic probes allow the important
results to be independently reproduced with another extracted ROCm build.

---

Prepared with OpenAI Codex.
