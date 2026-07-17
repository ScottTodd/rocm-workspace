# Branch Review: users/scotttodd/pytorch-shared-matrix

**Branch:** `users/scotttodd/pytorch-shared-matrix`  
**Base reviewed against:** authored branch commits plus current worktree state; aggregate `main..HEAD` is polluted by an upstream merge commit  
**Reviewed:** 2026-06-25  
**Review type:** Comprehensive, focused on scope, GitHub Actions data flow, tests, and maintainability

## Summary

This branch is still scoped tightly enough for a reviewable PR. It is not tiny, but the changes are cohesive: move PyTorch build matrix policy into `configure_pytorch_release_matrix.py`, thread the resulting matrix into `configure_multi_arch_ci.py` build configs, show it in the CI summary, and update CI/release workflows to consume the same policy.

The branch avoided pulling in the separate function-signature refactor and avoided manifest generation/test orchestration work. That keeps this PR about shared matrix policy rather than becoming another broad workflow rewrite.

## Overall Assessment

**Status:** APPROVED with suggestions

No blocking or important correctness issues found in this review pass.

## Findings

### No Blocking Issues

None found.

### No Important Issues

None found.

### Suggestions

1. Commit or squash the current worktree-only reorder in `.github/workflows/setup_multi_arch.yml` before posting or updating the PR. It is a small local-style cleanup, but the branch currently has an unstaged modification.

2. In the PR description, call out one subtle design detail: setup now computes and summarizes the PyTorch matrix in `build_config`, while the dispatched release PyTorch workflows still regenerate their matrix from scalar inputs using the same script. That is reasonable for the current workflow-dispatch boundary, but reviewers may otherwise expect `pytorch_build_matrix` JSON to be passed directly through release orchestration.

## Scope Assessment

The branch has three related pieces:

- Matrix policy: `build_tools/github_actions/configure_pytorch_release_matrix.py` defines release-vs-CI defaults, platform-specific refs, and unsupported family filtering.
- Setup/config propagation: `build_tools/github_actions/configure_multi_arch_ci.py` adds `build_pytorch`, optional `python_version`, and `pytorch_build_matrix` into per-platform build config.
- Workflow consumption: CI workflows consume `build_config.pytorch_build_matrix`; release workflows pass the same scalar inputs into the PyTorch release child workflows, which use the same matrix script.

Those pieces are coupled enough that splitting them further would make individual PRs harder to validate. The branch does not include the later manifest re-land or PyTorch test-trigger changes, which is the right boundary.

## Review Notes

- `setup_multi_arch.yml` caller inventory is complete for local callers: `multi_arch_ci.yml`, `multi_arch_ci_asan.yml`, `multi_arch_release.yml`, and `multi_arch_release_asan.yml` are all updated.
- The YAML changes do not add complex inline shell logic. Matrix decisions live in Python, matching the workflow style guide direction.
- `configure_pytorch_release_matrix.py` is small and direct after the simplification pass. The release/CI defaults and unsupported-family map are easy to scan.
- Tests cover the important behavior: CI-reduced matrices, explicit Python/ref narrowing, family filtering, build config integration, and `build_pytorch` opt-out.
- Current known limitation is acceptable for this PR: `python_version` is a single scalar through setup. That matches the current release UI intent, while the matrix script itself still supports lists where the child release workflows need them.

## Verification

Ran from `D:/projects/TheRock/build_tools`:

```powershell
D:/projects/TheRock/.venv/Scripts/python.exe -m pytest github_actions/tests/configure_pytorch_release_matrix_test.py github_actions/tests/configure_multi_arch_ci_test.py
```

Result: `86 passed, 1 skipped`.

Ran from `D:/projects/TheRock`:

```powershell
pre-commit run --files .github/workflows/multi_arch_ci.yml .github/workflows/multi_arch_ci_asan.yml .github/workflows/multi_arch_release.yml .github/workflows/multi_arch_release_asan.yml .github/workflows/setup_multi_arch.yml .github/workflows/multi_arch_ci_linux.yml .github/workflows/multi_arch_ci_windows.yml .github/workflows/multi_arch_release_linux.yml .github/workflows/multi_arch_release_windows.yml .github/workflows/multi_arch_release_linux_pytorch_wheels.yml .github/workflows/multi_arch_release_windows_pytorch_wheels.yml build_tools/github_actions/configure_multi_arch_ci.py build_tools/github_actions/configure_multi_arch_ci_summary.py build_tools/github_actions/configure_pytorch_release_matrix.py build_tools/github_actions/tests/configure_multi_arch_ci_test.py build_tools/github_actions/tests/configure_pytorch_release_matrix_test.py
```

Result: passed.

## Conclusion

The scope is focused enough. I would keep this as one PR, with the current setup input ordering cleanup committed or squashed in, and leave the function-signature cleanup, manifest re-land, and richer release orchestration changes as separate follow-ups.

Assisted-by: Codex
