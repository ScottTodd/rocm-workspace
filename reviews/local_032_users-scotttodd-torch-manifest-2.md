# Branch Review: users/scotttodd/torch-manifest-2

* **Branch:** `users/scotttodd/torch-manifest-2`
* **Base:** `upstream/main`
* **Reviewed:** 2026-05-21
* **Commits:** 29 commits

---

## Summary

This branch adds upfront PyTorch manifest generation, manifest-driven checkout,
manifest upload/matrix preparation, a reusable Linux multi-arch PyTorch build
workflow, per-build quick-test dispatch, and developer/debugging docs.

**Net changes:** 3749 insertions, 553 deletions across 31 files.

Evidence checked:

- `D:/projects/TheRock/.venv/Scripts/python.exe -m pytest github_actions/tests/generate_pytorch_manifest_upfront_test.py github_actions/tests/checkout_from_manifest_test.py github_actions/tests/prepare_pytorch_manifests_test.py github_actions/tests/configure_pytorch_test_matrix_test.py github_actions/tests/write_pytorch_manifest_versions_test.py github_actions/tests/publish_pytorch_to_release_bucket_test.py github_actions/tests/determine_version_test.py github_actions/tests/expand_amdgpu_families_test.py`
  passed: 61 tests.
- `pre-commit run --files ...` across the changed workflow, Python, docs, JSON,
  README, and test files passed.
- Workflow run evidence from
  https://github.com/ROCm/TheRock/actions/runs/26195227273 showed manifest
  generation, manifest checkout, and multiple build cells reaching expected
  stages. Known quick-test failures are currently runner/index/package-runtime
  issues rather than manifest plumbing failures.

---

## Overall Assessment

**APPROVED FOR SPLITTING** - No remaining blocking issue is visible in the
script foundation after the fail-fast manifest pin fix. The Linux workflow PR
still needs careful scoping because it moves legacy shell-heavy build logic into
a new reusable workflow, but that can be handled as part of the workflow PR
rather than blocking the manifest script PR.

**Strengths:**

- Manifest generation now fails fast for missing/malformed stable pins instead
  of silently selecting branch heads.
- `prepare_pytorch_manifests.py` owns the workflow-facing lifecycle without
  adding a wrapper-only manager script.
- The manifest directory consume mode gives a path for future scheduler jobs
  that freeze commits before dispatching release workflows.
- Tests cover generation, upload/matrix output, manifest-directory consumption,
  checkout command construction, version outputs, publish outputs, and quick
  test matrix generation.

**Remaining non-blocking items:**

- IMPORTANT: the new Linux reusable workflow still contains copied inline shell
  logic for cache flags and kpack wheel splitting.
- IMPORTANT: the external frozen-manifest directory path is implemented in the
  script but not yet wired into workflow inputs.
- FUTURE WORK: Windows multi-arch PyTorch release parity remains deferred.

---

## Detailed Review

### 1. Manifest Scripts

**APPROVED: fail-fast source selection**

- `generate_pytorch_manifest_upfront.py` now errors when a stable PyTorch
  release needs a related-commit pin that is missing or when a repo has no
  explicit stable release pin policy.
- `prepare_pytorch_manifests.py` supports three useful modes without another
  wrapper: pass through a single manifest URL, generate/upload manifests, or
  consume an existing S3/local manifest directory to emit the explicit matrix.
- `checkout_from_manifest.py` now accepts semicolon- or whitespace-separated
  project filters, matching the workflow inputs.

### 2. Workflows

**IMPORTANT: copied inline shell remains in the reusable build workflow**

- `.github/workflows/multi_arch_build_portable_linux_pytorch_wheels.yml`
  still has non-trivial shell for cache flag selection, cache stats, Python PATH
  validation, and wheel splitting.
- Much of this is copied from the existing multi-arch release body, so it is
  defensible if the workflow PR states that the first split preserves the known
  build body and leaves shell extraction as a follow-up.

**Recommendation:** for the workflow PR, either extract the split-wheel block
into a Python script with a focused test, or explicitly call out that the
reusable workflow PR is a mechanical reshaping plus manifest/test plumbing and
track shell extraction separately.

### 3. Tests

**APPROVED: coverage is broad enough for the current split**

- The new tests exercise behavior rather than argparse mechanics in most cases.
- The manifest-directory consume test uses real local files through the storage
  abstraction, avoiding a network dependency while covering the S3 URL shape.
- The quick-test matrix suite covers `auto`, empty-as-auto, `none`, known
  runner mapping, unknown family errors, and missing index URL errors.

### 4. Documentation

**APPROVED: developer workflow docs are present**

- `docs/development/github_actions_debugging.md` now documents narrow
  multi-arch PyTorch dev runs, semicolon-separated inputs, direct child workflow
  use, manifest summary expectations, and how build outputs flow into quick
  tests.
- `external-builds/pytorch/README.md` gives a two-command local manifest
  generation + checkout path, which is the right paper trail for debugging
  a single release ref.

### 5. Deferred Scope

**FUTURE WORK: Windows parity**

- Windows multi-arch release workflow changes should stay out of the first
  Linux review sequence. The Triton policy is correctly explicit for now, with
  a TODO path for future known release-version opt-in.

**FUTURE WORK: test checkout speed**

- Test-only manifest checkouts should eventually be able to skip submodule
  updates as well as HIPIFY, but that is not needed for the first Linux build
  and quick-test validation.

---

## PR Split Recommendation

1. **Manifest foundation**
   - Manifest generator/preparer, checkout-from-manifest, manifest version
     writer, GitHub API helpers, manifest utils, workflow output helper, unit
     tests, and PyTorch README docs.
   - Include `prepare_pytorch_manifests.py --manifest-dir-url` in this PR so
     the frozen-commit design is visible before workflow reviewers look at the
     release jobs.

2. **Standalone Linux multi-arch build/test workflow**
   - New reusable build workflow, quick-test matrix script, test workflow
     manifest summary changes, publish package-index outputs, and related
     tests.
   - This PR should be directly dispatchable for one Python version, one
     PyTorch ref, and a narrow AMDGPU family list.

3. **Linux multi-arch release orchestrator**
   - Release workflow generates/upload manifests once, emits the explicit
     matrix, and calls the reusable build/test workflow.
   - Include release-orchestrator docs and workflow-dispatch evidence here.

4. **Follow-up platform/test expansion**
   - Windows reusable workflow/orchestrator parity, full-test dispatch, CI
     plumbing, and shell extraction if not completed in PR 2.

---

## Conclusion

**Approval Status: APPROVED FOR SPLITTING**

The branch is ready to turn into smaller review branches. The main caution is
to keep PR 1 script-only enough that reviewers can approve the manifest model
without also reviewing the large Linux workflow reshaping.
