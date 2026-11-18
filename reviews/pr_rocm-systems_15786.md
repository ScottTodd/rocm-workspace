# Review: rocm-systems PR 15786

- PR: https://github.com/ROCm/rocm-systems/pull/15786
- Reviewed head: `98a18048be89a906d1c0e6139ad0a7cdf20b8bbd`
- Base: `develop`, `600a0c83ac60e0d1394da3bb97b89a10468c2be4`
- Reviewed: 2026-11-18
- Scope: linked issue evidence, extraction and transformation contracts, both splitters, test quality, related edge cases, and CI.

## Assessment

**APPROVED. No blocking findings or newly introduced correctness bugs found in this revision.** The change addresses the sparse per-architecture TOC numbering described in the issue. The staging-directory fix also addresses the same-basename overwrite discussed in the PR comments. There is a confirmed, separate pre-existing host-transform problem, described below; approval should not be read as saying all multi-TU layouts now work.

## Findings and follow-ups

### FUTURE WORK: Derive host indices from the referenced bundle, rather than wrapper position

The [ELF transform writes wrapper position into reserved1](https://github.com/ROCm/rocm-systems/blob/98a18048be89a906d1c0e6139ad0a7cdf20b8bbd/shared/kpack/python/rocm_kpack/elf/kpack_transform.py#L175), and the [COFF transform does the same](https://github.com/ROCm/rocm-systems/blob/98a18048be89a906d1c0e6139ad0a7cdf20b8bbd/shared/kpack/python/rocm_kpack/coff/kpack_transform.py#L193). A wrapper is not necessarily a distinct offload bundle: device linking can leave multiple registration wrappers pointing at one linked bundle.

Independently checked the existing Linux `cov5/libtest_multi_wrapper.so` fixture. Wrapper 0 uses an R_X86_64_RELATIVE relocation; wrapper 1 uses R_X86_64_64. Resolving both shows that they reference offset zero of `.hip_fatbin`. Extraction produces only bundle index 0, for gfx1100 and gfx1201. Rewriting assigns wrapper indices `[0, 1]`, so the second wrapper requests a nonexistent `#1` instead of sharing `#0`. Merely comparing wrapper and bundle counts would detect this example but would not resolve permutations or aliases in general.

**Impact:** kernels registered through the second wrapper remain unavailable after splitting this valid RDC layout. The same issue affects reordered wrapper/bundle layouts if encountered. This is pre-existing: the old per-architecture counters also produce just `#0` for this fixture. It is therefore a separate follow-up, not a reason to reject this fix. The [latest author comment](https://github.com/ROCm/rocm-systems/pull/15786#issuecomment-6993883944) explicitly acknowledges it, and the new [source comment](https://github.com/ROCm/rocm-systems/blob/98a18048be89a906d1c0e6139ad0a7cdf20b8bbd/shared/kpack/python/rocm_kpack/binutils.py#L199) now accurately states the assumption.

**Recommended follow-up:** resolve original wrapper pointers, including applicable relocations, to actual bundle offsets before replacing them; use the corresponding bundle index for reserved1. Support aliases and reordered references, or reject unsupported mappings before emitting an unusable split binary. Add a static regression using this real RDC fixture and a reordered-reference case.

### SUGGESTION: Automate the host-wrapper-to-archive contract test

The new [wheel regression](https://github.com/ROCm/rocm-systems/blob/98a18048be89a906d1c0e6139ad0a7cdf20b8bbd/shared/kpack/tests/test_wheel_splitter.py#L400) and [artifact regression](https://github.com/ROCm/rocm-systems/blob/98a18048be89a906d1c0e6139ad0a7cdf20b8bbd/shared/kpack/tests/test_artifact_splitter_integration.py#L1640) write standalone fatbin bytes to files named `.so`. They exercise the real parser and extraction logic, but those files contain no ELF headers, wrapper segment, or pointer relocations. Consequently they cannot detect disagreement between transformed reserved1 values and archive keys. The existing transform test separately asserts wrapper ordinal numbering, which also cannot detect that disagreement.

**Recommendation:** preserve the reported three-TU real HIP reproducer as a fixture or reproducible test, split it, and statically compare each transformed wrapper index with the appropriate architecture's extracted payload. No GPU is needed for that assertion. Keep the current small synthetic tests; they are useful and are not redundant with such a contract test. The manual real-binary validation provides sufficient evidence for this PR, so this is an optional improvement.

## Does the change address the linked issue?

The [issue](https://github.com/ROCm/rocm-systems/issues/15656) supplies three complementary forms of evidence:

1. Static inspection shows 1,258 host wrappers but compacted architecture-specific TOCs. The first missing architecture at AsyncMM shifts the subsequent gloo objects; the much larger gfx90a gap places CK GEMM objects under `#224..#234` while runtime requests `#1218..#1228`.
2. Runtime probes distinguish an object before the gap from objects after it. Remapping only archive keys restores function-attribute lookup and correct gloo/CK BLAS behavior. This isolates the numbering problem more strongly than a generic successful rebuild would.
3. The [PR's real-build validation](https://github.com/ROCm/rocm-systems/pull/15786#issuecomment-6913903533) reports successful gloo output and CK SDPA forward/backward checks after using the fixed splitter.

The implementation matches that diagnosis:

- `extract_code_objects_from_fatbin` enumerates parsed bundles before skipping host entries. An architecture missing from a bundle does not renumber later bundles.
- `BundledBinary.unbundle` builds target names, filenames, and the new index list from the same code-object sequence after optional architecture filtering. Length validation protects the parallel-list contract at construction.
- Both splitters use that source index directly. Artifact `gpu_targets` filtering no longer needs to maintain a counter, and does not alter retained indices.
- [Runtime lookup](https://github.com/ROCm/rocm-systems/blob/98a18048be89a906d1c0e6139ad0a7cdf20b8bbd/shared/kpack/runtime/src/loader.cpp#L289) constructs an exact `kernel_name#co_index` key; it does not require contiguous indices. Therefore large gaps, such as the gfx90a case, are handled by the same fix as a one-bundle gap.
- Full overlay-relative staging directories distinguish binaries with identical basenames before archive creation. Caller paths are generated relative to the scanned overlay root; I found no new uncontrolled absolute-path input introduced by this change.

I verified the linked [TheRock build job](https://github.com/ROCm/TheRock/actions/runs/43474181780/job/132053748547) succeeded. Its logs show `USE_ROCM_CK_SDPA_GFX11=ON`, checkout of rocm-systems `e4f83c5f577d478f8d0ee7b45bdc25c666c976c5`, installation of kpack, and invocation of `rocm_kpack.tools.split_python_wheels`, followed by split completion. This corroborates the build/split provenance; the GPU correctness results remain author-reported. The build's automated PyTorch wheel-test jobs were skipped, so the successful build alone does not establish those runtime results. I did not download the large PyTorch wheels or reproduce GPU execution locally.

## Are the added tests meaningful?

Yes. All six new parameterized cases use real parsing and file contents:

- The binutils test verifies target, original bundle index, and bytes together, and checks that architecture filtering retains `[0, 2]`.
- The wheel index test checks all five architecture/key/payload combinations across three bundles. A compact per-architecture counter would place the last gfx1100 object at `#1` and fail it.
- The two artifact cases make the same assertions both with and without architecture filtering.
- The two same-basename cases retain references from both extraction operations, create an actual archive, and read both payloads back. They detect deferred staging-file overwrites that immediate extraction assertions would miss. The identical-layout case covers the pre-existing collision; the heterogeneous layout covers the collision made possible by the new numbering.

The helper extraction from `test_ccob_parser.py` preserves the original CCOB construction and updates its callers. The tests do not mock the parser, substitute expected results for extraction, or require a GPU. Their main limitation is the missing automated wrapper/TOC contract test above.

## Verification and CI

Source review used an isolated source archive in `D:/scratch/codex/review-15786`, without switching or editing the user's rocm-systems checkout. Its LFS fixtures were hydrated from the local checkout only after verifying each fixture's SHA-256 against the PR archive's LFS pointer (21 matches, none unavailable).

Local regression command, from `D:/scratch/codex/review-15786/ROCm-rocm-systems-98a1804/shared/kpack`:

```powershell
$env:PYTHONPATH='D:/scratch/codex/review-15786/ROCm-rocm-systems-98a1804/shared/kpack/python;D:/scratch/codex/review-15786/ROCm-rocm-systems-98a1804/python/rocm-bootstrap/python'
D:/projects/TheRock/.venv/Scripts/python.exe -m pytest --override-ini=cache_dir=D:/scratch/codex/pytest-cache/rocm-systems-15786 -x tests/test_binutils.py::test_unbundle_reports_source_bundle_indices tests/test_wheel_splitter.py::TestExtractSingleBinary tests/test_artifact_splitter_integration.py::TestArtifactSplitterIntegration::test_toc_index_is_bundle_index -v
```

Output (Python 3.13.5, pytest 8.4.2):

```text
collected 6 items
tests/test_binutils.py::test_unbundle_reports_source_bundle_indices PASSED
tests/test_wheel_splitter.py::TestExtractSingleBinary::test_toc_index_is_bundle_index PASSED
tests/test_wheel_splitter.py::TestExtractSingleBinary::test_same_basename_binaries_keep_their_payloads[bundles_a0-bundles_b0] PASSED
tests/test_wheel_splitter.py::TestExtractSingleBinary::test_same_basename_binaries_keep_their_payloads[bundles_a1-bundles_b1] PASSED
tests/test_artifact_splitter_integration.py::TestArtifactSplitterIntegration::test_toc_index_is_bundle_index[None] PASSED
tests/test_artifact_splitter_integration.py::TestArtifactSplitterIntegration::test_toc_index_is_bundle_index[gpu_targets1] PASSED
6 passed in 0.18s
```

Initial sandboxed attempts encountered filesystem/test-environment problems and were interrupted; the successful run above was outside the sandbox. These were not classified as product failures. Only the six new cases were completed locally; full-suite results below come from CI.

Additional static probe command:

```powershell
D:/projects/TheRock/.venv/Scripts/python.exe D:/scratch/codex/review-15786/probe.py
```

Full output:

```text
uncompressed, host-only middle bundle [('hipv4-amdgcn-amd-amdhsa--gfx1100', 0), ('hipv4-amdgcn-amd-amdhsa--gfx1100', 2)]
mixed compressed/uncompressed with padding [('hipv4-amdgcn-amd-amdhsa--gfx1100', 0), ('hipv4-amdgcn-amd-amdhsa--gfx1100', 2)]
feature target after initial gap [('hipv4-amdgcn-amd-amdhsa--gfx90a:sramecc+:xnack-', 1)]
RDC fixture wrapper pointer targets (offset into fatbin): {0: 0}
Resolved wrapper 0 relocation type 8 fatbin offset 0x0
Resolved wrapper 1 relocation type 1 fatbin offset 0x0
RDC fixture extracted (target, bundle_index): [('hipv4-amdgcn-amd-amdhsa--gfx1100', 0), ('hipv4-amdgcn-amd-amdhsa--gfx1201', 0)]
RDC fixture transformed wrapper indices: [0, 1]
```

CI evidence inspected through authenticated `gh api` job logs:

- [Linux Python 3.10](https://github.com/ROCm/rocm-systems/actions/runs/44414802556/job/135192156973): **719 passed, 4 skipped in 3.16s**; all six new cases appear individually as passed.
- [Windows Python 3.10](https://github.com/ROCm/rocm-systems/actions/runs/44414802556/job/135192156640): **719 passed, 4 skipped in 8.48s**.
- All four Linux/Windows Python 3.10/3.12 checks and both C++ runtime checks passed.
- At the last checks snapshot, broader CI still had one in-progress and three queued checks. The [policy bot failure](https://github.com/ROCm/rocm-systems/actions/runs/44414799656/job/135192149490) is a 900-second timeout waiting for required checks; its log does not report a kpack test failure. It should not be described as a completely green PR yet.

Saved evidence: `D:/scratch/codex/review-15786/{linux-tests.log,windows-tests.log,bot.log,pytorch-build.log,checks.json,pytorch-build.json,probe.py,probe.log}`. Metadata and logs were obtained with `gh pr checks`, `gh run view`, and `gh api repos/<owner>/<repo>/actions/jobs/<job-id>/logs` using the job IDs linked above.

Generated with Codex.
