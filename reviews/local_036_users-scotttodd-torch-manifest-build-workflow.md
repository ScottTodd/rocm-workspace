# Branch Review: users/scotttodd/torch-manifest-build-workflow

**Branch:** `users/scotttodd/torch-manifest-build-workflow`
**Base:** `main`
**Reviewed:** 2026-05-29
**Commit count:** 3
**Status:** APPROVED

## Summary

This branch wires the existing PyTorch source manifest generator into the
multi-arch PyTorch build workflows. It adds upload/output support to
`generate_pytorch_source_manifest.py`, a thin pass-through/generate wrapper for
the reusable workflows, and replaces explicit per-repo checkout logic in the
multi-arch Linux/Windows build workflows with manifest-driven checkout.

The overall direction simplifies the workflow surface: repository selection,
pin resolution, upload location construction, and manifest URL output are now
handled by scripts rather than duplicated inline workflow logic. The wrapper
script is intentionally small, and the workflow comments explain the two paths
without adding unnecessary branching.

## Findings

### 💡 SUGGESTION: Add one CLI test for the workflow-facing `--manifest-dir --upload` path

- The workflow calls `prepare_pytorch_manifests.py`, which forwards
  `--manifest-dir "${{ github.workspace }}/output/manifests"` and `--upload` to
  `generate_pytorch_source_manifest.py`
  (`.github/workflows/multi_arch_build_portable_linux_pytorch_wheels.yml:170`).
- The current upload integration test uses `--output` with `--upload`
  (`build_tools/github_actions/tests/generate_pytorch_source_manifest_test.py:537`),
  so it covers upload/output emission but not the exact generated-filename path
  that the workflow uses.
- This is not blocking because the lower-level behavior is simple and the
  workflow syntax/lint checks pass, but one concise test using `--manifest-dir`,
  a single ref, and `--upload` would better protect the real CI entry point.

## Complexity Assessment

- `prepare_pytorch_manifests.py` is appropriately small. It has one real
  responsibility: either pass through an already-uploaded manifest URL or invoke
  the generator with `--upload`. The tests map directly to those two modes.
- Upload support in `generate_pytorch_source_manifest.py` is cohesive. The new
  helpers split bucket/root selection, single-file upload, and summary output
  cleanly without introducing a larger orchestration abstraction.
- The workflow changes reduce source checkout complexity by removing the
  nightly/stable repo checkout branches from both multi-arch build workflows.
  The remaining inline shell is mostly preexisting build/split logic; this
  branch does not add another large inline decision tree.

## Test Review

- `prepare_pytorch_manifests_test.py` is simple but useful: it verifies
  pass-through mode does not run the generator and generation mode forwards the
  expected command.
- The generator tests focus on business logic: related commit parsing,
  fail-fast missing pins, PyTorch-only filtering, Linux/Windows Triton behavior,
  upload output emission, and argparse validation.
- The tests avoid network access by mocking the GitHub API boundaries.
- One skipped Windows Triton default-project test is acceptable because the
  code path is intentionally gated until Windows Triton is enabled by default.

## Workflow Review

- Reusable workflow callers are still wired: the release workflows call the
  multi-arch build workflows and can rely on `manifest_url`'s default empty
  value.
- The prepare job correctly emits a single `manifest_url` output consumed by the
  build job.
- The pass-through path avoids configuring artifact credentials when
  `inputs.manifest_url` is provided.
- The generation path uses a Linux runner for Windows manifest preparation,
  which keeps expensive Windows runners focused on actual builds.

## Verification

Commands run:

```text
D:/projects/TheRock/.venv/Scripts/python.exe -m pytest github_actions/tests/prepare_pytorch_manifests_test.py github_actions/tests/generate_pytorch_source_manifest_test.py tests/workflow_outputs_test.py
```

Result: 52 passed, 1 skipped. Pytest emitted a cache warning because the
workspace `.pytest_cache` directory is not writable.

```text
pre-commit run --files .github/workflows/multi_arch_build_portable_linux_pytorch_wheels.yml .github/workflows/multi_arch_build_windows_pytorch_wheels.yml build_tools/_therock_utils/workflow_outputs.py build_tools/github_actions/generate_pytorch_source_manifest.py build_tools/github_actions/prepare_pytorch_manifests.py build_tools/github_actions/tests/generate_pytorch_source_manifest_test.py build_tools/github_actions/tests/prepare_pytorch_manifests_test.py build_tools/tests/workflow_outputs_test.py
```

Result: passed.

```text
git -C D:/projects/TheRock diff --check main..HEAD
```

Result: passed.

## Conclusion

Approved for push/test runs. The branch is reviewable as-is and appears to move
workflow complexity into testable script interfaces. The only suggested
improvement before formal PR review is one extra workflow-shaped generator CLI
test for `--manifest-dir --upload`.

Assisted-by: Codex
