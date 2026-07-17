# PR Review: rocm-libraries #8397

* **PR:** https://github.com/ROCm/rocm-libraries/pull/8397
* **State:** merged on 2026-06-20
* **Merge commit:** `fb7e6d5511c4f8caf47367b182d2183e34a245de`
* **Reviewed:** 2026-06-26
* **Scope:** host-ASAN / xnack behavior and CI validation

## Overall Assessment

**CHANGES REQUESTED post-merge** - The PR conflates `HOST_ASAN` with device-side ASAN. That contradicts TheRock's sanitizer contract and weakens the value of host-only ASAN. This may contribute to the hipBLASLt HOST_ASAN build-time problem, but the available timing data does not prove it is the root cause.

## Findings

### BLOCKING: `HOST_ASAN` is incorrectly treated as requiring `xnack+`

The PR adds `THEROCK_SANITIZER STREQUAL "HOST_ASAN"` to hipBLASLt's sanitizer target path, both for default `all` expansion and explicit target normalization:

- [`tensilelite_supported_architectures.cmake`](https://github.com/ROCm/rocm-libraries/blob/14148b55bb5257286f97ec950696a2ac2d598f52/projects/hipblaslt/cmake/tensilelite_supported_architectures.cmake#L39-L48)
- [`tensilelite_supported_architectures.cmake`](https://github.com/ROCm/rocm-libraries/blob/14148b55bb5257286f97ec950696a2ac2d598f52/projects/hipblaslt/cmake/tensilelite_supported_architectures.cmake#L104-L118)
- [`CMakeLists.txt`](https://github.com/ROCm/rocm-libraries/blob/14148b55bb5257286f97ec950696a2ac2d598f52/projects/hipblaslt/CMakeLists.txt#L122-L123)

That directly contradicts TheRock's documented semantics: `HOST_ASAN` is host-only, has no device-side instrumentation, does not need xnack-capable hardware, and is supposed to avoid `xnack+` kernel variants:

- [`sanitizers.md`](https://github.com/ROCm/TheRock/blob/bc80c55fb94450959f542b65c004ab1886d20241/docs/development/sanitizers.md#L7-L11)
- [`sanitizers.md`](https://github.com/ROCm/TheRock/blob/bc80c55fb94450959f542b65c004ab1886d20241/docs/development/sanitizers.md#L22-L33)
- [`therock_sanitizers.cmake`](https://github.com/ROCm/TheRock/blob/bc80c55fb94450959f542b65c004ab1886d20241/cmake/therock_sanitizers.cmake#L65-L74)

Impact: host-only ASAN builds now get device target rewriting, narrower `all` target coverage, and potentially more expensive code generation. This changes the meaning of `HOST_ASAN` for hipBLASLt and makes a host-only build behave like a partial device-ASAN build. The existing logs show the slow run includes this behavior, but additional before/after data is needed to quantify the build-time impact of the `xnack+` rewrite itself.

**Required action:** remove `HOST_ASAN` from `tensilelite_sanitizer_requires_xnack()` and the ASAN-only default architecture branch. If full device ASAN needs `xnack+`, key it on full `ASAN` / `HIPBLASLT_ENABLE_ASAN`, not `HOST_ASAN`.

### BLOCKING: the CI test forces `HSA_XNACK=1` while claiming to test `HOST_ASAN`

The new workflow configures hipBLASLt with `-DhipBLASLt_SANITIZER=HOST_ASAN`, then unconditionally exports `HSA_XNACK=1` for the test:

- [`hipblaslt-asan-ci.yml`](https://github.com/ROCm/rocm-libraries/blob/14148b55bb5257286f97ec950696a2ac2d598f52/.github/workflows/hipblaslt-asan-ci.yml#L131)
- [`hipblaslt-asan-ci.yml`](https://github.com/ROCm/rocm-libraries/blob/14148b55bb5257286f97ec950696a2ac2d598f52/.github/workflows/hipblaslt-asan-ci.yml#L246-L258)

This appears to be the root cause the PR should have challenged. If a host-only ASAN test fails only because the workflow forces an xnack runtime, the fix is to stop forcing the device-ASAN runtime for `HOST_ASAN`, not to change hipBLASLt device library generation to match that forced runtime.

hipDNN has the expected split: ASAN defines are shared, but `HSA_XNACK=1` is only required for device-side ASAN, not `HOST_ASAN`:

- [`Sanitizers.cmake`](https://github.com/ROCm/rocm-libraries/blob/14148b55bb5257286f97ec950696a2ac2d598f52/projects/hipdnn/cmake/Sanitizers.cmake#L120-L128)

**Required action:** set `HSA_XNACK=1` only for full device-ASAN tests. For `HOST_ASAN`, validate that bare `gfx942` device code loads without forcing `HSA_XNACK=1`, or create a separate full-ASAN leg if the intent is to test device-ASAN.

### BLOCKING: the final PR did not validate the gfx942 path it claimed to fix

The workflow only includes gfx942 when manually dispatched or when the PR has the `ci:asan` label:

- [`hipblaslt-asan-ci.yml`](https://github.com/ROCm/rocm-libraries/blob/14148b55bb5257286f97ec950696a2ac2d598f52/.github/workflows/hipblaslt-asan-ci.yml#L46-L59)

The final workflow also marks gfx942 `continue-on-error`:

- [`hipblaslt-asan-ci.yml`](https://github.com/ROCm/rocm-libraries/blob/14148b55bb5257286f97ec950696a2ac2d598f52/.github/workflows/hipblaslt-asan-ci.yml#L62-L66)
- [`hipblaslt-asan-ci.yml`](https://github.com/ROCm/rocm-libraries/blob/14148b55bb5257286f97ec950696a2ac2d598f52/.github/workflows/hipblaslt-asan-ci.yml#L180-L184)

Live `gh pr checks` for the merged PR showed `Build (hipBLASLt | gfx90a | HOST_ASAN)` and `Test hipBLASLt HOST_ASAN | gfx90a (quick)` passing, but no gfx942 HOST_ASAN job from this workflow. The PR metadata also did not include `ci:asan`; it only had unrelated labels such as `ci:hipsparselt-fast`.

This matters because the review approval explicitly said the ASAN legs gated the merge and that the gfx942 HOST_ASAN leg was the key signal to watch, but a later commit made gfx942 opt-in and non-gating:

- [approval review](https://github.com/ROCm/rocm-libraries/pull/8397#pullrequestreview-4498390427)
- [`dffad8278b329e750869f69d38b3fcfe424032b7`](https://github.com/ROCm/rocm-libraries/commit/dffad8278b329e750869f69d38b3fcfe424032b7)

**Required action:** do not treat this PR's green checks as validation of the gfx942 behavior. A follow-up should provide an actual gfx942 run, and if the change is specifically for gfx942 correctness, it should either gate or be clearly separated from the semantic change to `HOST_ASAN`.

## Recommendation

Start with a narrow follow-up that restores the sanitizer contract:

1. Remove `HOST_ASAN` from hipBLASLt's `xnack+` target normalization.
2. Stop forcing `HSA_XNACK=1` in `HOST_ASAN` tests.
3. Keep any full device-ASAN `xnack+` behavior under full `ASAN` only.
4. Re-run a gfx942 `HOST_ASAN` build/test and confirm it uses bare `gfx942` in the hipBLASLt device library commands.

The likely correct root-cause split is: `HOST_ASAN` may need the ASAN runtime preloaded for build-time Python native extensions, but it should not require device-side `xnack+` code objects.

## Build-Time Evidence Caveat

PR #8397 should not be treated as the root cause of the slow HOST_ASAN hipBLASLt build without more data. A pre-#8397 TheRock HOST_ASAN run already showed the same order-of-magnitude problem:

- TheRock run [`27697825394`](https://github.com/ROCm/TheRock/actions/runs/27697825394), commit `50082e1554bd5b24e5b71333ee60c57dc2b5e4cb`, used rocm-libraries `be5adb9ba3c978b388b4b5943daac6cdf9db839a`.
- `be5adb9` does not contain PR #8397.
- Its hipBLASLt configure log used `--architecture=gfx942`, not `gfx942:xnack+`, while still setting `LD_PRELOAD=...libclang_rt.asan-x86_64.so`.
- Its hipBLASLt build log reported `TensileLogic --check-all` at 3731.9s and `Generating assembly kernels` at 10739.8s for 176527 tasks, total 16391.05s.

The June 25 post-#8397 run `28189306689` used `gfx942:xnack+` and was still very slow, but the comparable phases were not worse: `TensileLogic --check-all` was 3832.9s and `Generating assembly kernels` was 6418.3s for 176550 tasks, total 12129.10s.

This supports treating #8397 as a sanitizer-semantics bug, not as the primary build-time regression. The stronger build-time lead remains the HOST_ASAN Python/codegen environment, especially ASAN-preloaded Python importing sanitized native extensions.

---

Generated by Codex.
