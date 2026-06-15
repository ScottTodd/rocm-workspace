# PR Review: ROCm/TheRock#5650

* **PR:** https://github.com/ROCm/TheRock/pull/5650
* **Title:** `[origami] add origami to mathlibs`
* **Author:** `davidd-amd`
* **Branch:** `users/davidd-amd/reland-origami`
* **Base:** `main`
* **Reviewed:** 2026-06-08
* **Head SHA:** `5c59c0d1c171f95e2fdd7ed3ae3125787b226cdb`
* **Net changes:** +367 / -4 across 9 files

---

## Summary

This PR re-lands origami as a `math-libs/BLAS` subproject, wires it into
hipBLASLt and hipSPARSELt, adds artifact descriptor entries for origami, adds a
new origami executable test configuration, and introduces an artifact-accounting
audit intended to catch staged files that are not claimed by any artifact
component.

## Overall Assessment

**CHANGES REQUESTED** - The origami wiring itself is plausible, but the new
artifact-accounting guard is not actually exercised by the current CI paths, so
the central regression prevention promised by the PR can silently skip. There
are also two cleanup issues in changed files.

## Findings

### BLOCKING: Artifact accounting audit is not wired into a non-skipped CI path

The new audit test is added as
[`tests/test_artifact_accounting.py`](https://github.com/ROCm/TheRock/blob/5c59c0d1c171f95e2fdd7ed3ae3125787b226cdb/tests/test_artifact_accounting.py#L21-L24),
but it skips unless `THEROCK_BINARY_DIR` or `THEROCK_BUILD_DIR` already points to
an existing build tree. The green Unit Tests check does not collect this file:
the workflow runs `pytest` from `build_tools/` only, at
[`unit_tests.yml`](https://github.com/ROCm/TheRock/blob/main/.github/workflows/unit_tests.yml#L45-L49).
The artifact-structure workflow also only invokes
[`tests/test_artifact_structure.py`](https://github.com/ROCm/TheRock/blob/main/.github/workflows/test_artifacts_structure.yml#L106-L109),
not the new accounting test.

Impact: this PR's main safeguard against the previous origami artifact-accounting
bug is currently easy to miss. A PR or release build can still pass Unit Tests
without ever running the new audit against staged output, and the current CI run
did not reach downstream artifact validation because stage jobs failed or were
skipped.

**Required action:** Wire the audit into a build-backed CI path that always has
the stage tree available, for example by invoking
`python build_tools/audit_artifact_accounting.py --root-dir "$BUILD_DIR" --strict`
after staged artifacts are produced, or by explicitly running the pytest with
`THEROCK_BINARY_DIR` set in an artifact/build validation workflow. If the pytest
is kept, make sure it is explicitly collected by CI rather than only living in
top-level `tests/`.

### IMPORTANT: Descriptor discovery uses POSIX-only path filtering

[`discover_descriptors()`](https://github.com/ROCm/TheRock/blob/5c59c0d1c171f95e2fdd7ed3ae3125787b226cdb/build_tools/audit_artifact_accounting.py#L13-L20)
filters generated and internal paths with string checks such as `"/build/"`.
That works on Linux paths, but not on native Windows paths like
`D:\projects\TheRock\build\...`. The common local Windows build tree is inside
the checkout, so a Windows audit can recurse into `build/` and scan generated or
copied descriptors that should have been excluded.

**Recommendation:** Filter with `Path.relative_to(repo).parts` or another
separator-independent path check, and add coverage for a repo containing
`build/artifact-*.toml` so the intended exclusion is enforced on Windows and
Linux.

### IMPORTANT: `math-libs/BLAS/CMakeLists.txt` loses its license header

At the PR head,
[`math-libs/BLAS/CMakeLists.txt`](https://github.com/ROCm/TheRock/blob/5c59c0d1c171f95e2fdd7ed3ae3125787b226cdb/math-libs/BLAS/CMakeLists.txt#L1-L4)
now starts directly with the body comment. The diff removes the existing
`Copyright Advanced Micro Devices, Inc.` and `SPDX-License-Identifier: MIT`
header from that file.

**Recommendation:** Restore the two-line header.

## CI Evidence

`gh pr checks` showed `pre-commit` and Unit Tests passing. Several Linux stage
jobs were failing, and one Windows math-libs job was still pending at review
time. The failing logs I could inspect for Linux `gfx1151`, `gfx120X-all`,
`gfx94X-dcgpu`, and profiler-apps ended with runner/container shutdown signals
or exit code 130, so I am not treating those as proof of a code failure.
However, because those stage jobs failed, downstream artifact validation and
test jobs were skipped, so the PR does not yet have end-to-end CI evidence for
the new origami artifacts and tests.

## Required Before Merge

1. Make the artifact-accounting audit run in CI against an actual build/stage
   tree.
2. Restore the `math-libs/BLAS/CMakeLists.txt` license header.
3. Fix descriptor discovery to exclude generated/internal directories
   portably.
4. Re-run CI after the Linux stage runner failures are cleared so artifact
   structure and origami tests get real coverage.

Generated with Codex.
