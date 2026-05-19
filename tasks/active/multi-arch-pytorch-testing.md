---
repositories:
  - therock
---

# Multi-Arch PyTorch Testing

- **Status:** In progress
- **Priority:** P1 (High)
- **Started:** 2026-05-01

## Overview

Enable running PyTorch tests on multi-arch packages (kpack-split wheels with
device extras like `torch[device-gfx942]`) as part of both release and CI
workflows. Related to issue #3332 and the multi-arch-releases task.

## Goals

- [x] Test workflows support `multi_arch=true` install path
- [x] Drop whl-staging-multi-arch, publish directly to whl-multi-arch
- [x] Upfront manifest generation script
- [x] Checkout-from-manifest script
- [x] determine_version.py exports version_suffix to GITHUB_ENV
- [x] Wire manifest into per-family build workflows (Linux + Windows)
- [x] Rename upload_pytorch_manifest -> upload_pytorch_manifests (directory)
- [x] Add pytorch_manifest_dir() to WorkflowOutputRoot
- [x] Clean up manifest format (consistent URLs, rocm_version under therock)
- [ ] Test end-to-end on a real workflow run
- [x] Unit tests for generate_pytorch_manifest_upfront.py
- [x] Unit tests for checkout_from_manifest.py
- [x] Restructure multi-arch release workflow (orchestrator + per-cell)
- [ ] Test matrix script (configure_pytorch_test_matrix.py)
- [ ] Add test jobs to multi-arch release workflows
- [ ] Multi-arch CI workflows optionally call test workflows

## Context

### Issue and PR references

- Issue: https://github.com/ROCm/TheRock/issues/3332
- Issue: https://github.com/ROCm/TheRock/issues/5110 (manifest + workflow architecture)
- Issue: https://github.com/ROCm/TheRock/issues/1236 (commit manifests)
- PR #4996: `multi_arch` input for test workflows (merged)
- PR #5107: drop whl-staging, publish directly to whl-multi-arch (merged)

### Key files

```
# New manifest scripts
build_tools/github_actions/generate_pytorch_manifest_upfront.py
build_tools/github_actions/upload_pytorch_manifests.py
build_tools/github_actions/manifest_utils.py
build_tools/github_actions/github_actions_api.py  # gha_resolve_git_ref, gha_fetch_file_contents
external-builds/pytorch/checkout_from_manifest.py

# Workflows updated with manifest-driven checkouts
.github/workflows/build_portable_linux_pytorch_wheels.yml
.github/workflows/build_windows_pytorch_wheels.yml

# Workflows to restructure next
.github/workflows/multi_arch_release_linux_pytorch_wheels.yml
.github/workflows/multi_arch_release_windows_pytorch_wheels.yml

# Test workflows (already support multi_arch=true)
.github/workflows/test_pytorch_wheels.yml
.github/workflows/test_pytorch_wheels_full.yml
```

## Completed work

### PR #4996 -- multi_arch input for test workflows

Added `multi_arch` boolean input to both test workflows. When true:
- `expand_amdgpu_families.py --output-mode=device-extras` expands family to
  device extras and writes to GITHUB_OUTPUT
- `setup_venv.py` installs `torch[device-gfx942]==$VERSION --index-url=$URL`
- `rocm[devel,device-gfx942]` installed from same index (full test only)

### PR #5107 -- drop whl-staging, publish directly to whl-multi-arch

- Renamed `publish_pytorch_to_staging.py` -> `publish_pytorch_to_release_bucket.py`
- `v4/whl-staging` -> `v4/whl` (per-family v3 staging unchanged)
- RELEASES.md: removed staging, added install examples
- external-builds/pytorch/README.md: rewrote gating section

### Manifest generation (branch: multi-arch-torch-manifest)

Scripts:
- `generate_pytorch_manifest_upfront.py`: resolves refs -> commits via
  GitHub API, fetches version.txt, computes versions. Supports `--platform`,
  `--projects`, `--pytorch-git-refs` for flexibility.
- `checkout_from_manifest.py`: reads manifest, delegates to existing
  `pytorch_*_repo.py checkout` scripts with explicit commit SHAs.
- `gha_resolve_git_ref()` and `gha_fetch_file_contents()` added to
  `github_actions_api.py`.
- `detect_therock_source_info()` added to `manifest_utils.py`.
- `determine_version.py`: simplified, exports `version_suffix` to GITHUB_ENV.

Workflow changes:
- `build_portable_linux_pytorch_wheels.yml` and
  `build_windows_pytorch_wheels.yml`: replaced nightly/stable checkout
  blocks with manifest generation + checkout_from_manifest.py. Made
  `rocm_version` required.
- Renamed `upload_pytorch_manifest.py` -> `upload_pytorch_manifests.py`,
  changed from single-file to directory upload.
- Added `pytorch_manifest_dir()` to `WorkflowOutputRoot`.
- Removed old `generate_pytorch_manifest.py` post-build step.

Manifest format:
```json
{
  "pytorch": {
    "commit": "1a2700743c...",
    "repo": "https://github.com/ROCm/pytorch",
    "branch": "release/2.10",
    "version": "2.10.0+rocm7.13.0a20260501"
  },
  "pytorch_audio": { "commit": "...", "repo": "...", "version": "..." },
  "pytorch_vision": { "commit": "...", "repo": "...", "version": "..." },
  "triton": { "commit": "...", "repo": "...", "version": "..." },
  "apex": { "commit": "...", "repo": "...", "version": "..." },
  "therock": {
    "commit": "...",
    "repo": "https://github.com/ROCm/TheRock",
    "branch": "main",
    "rocm_version": "7.13.0a20260501"
  }
}
```

## Design decisions

### Package promotion for multi-arch

**Decision:** Drop the staging-to-promoted index split for multi-arch.
Publish directly to `whl-multi-arch`. Tests run post-publish as signal
(HUD), not as a gate. See #3332 discussion.

### Manifest-driven checkouts

**Decision:** Generate manifests upfront (before build), pin exact commits
and compute versions via GitHub API. Both build and test jobs read from
the manifest. Replaces the old nightly/stable checkout conditionals and
post-build manifest generation.

Manifests are uploaded to S3 at
`{run_id}-{platform}/manifests/pytorch/{amdgpu_family}/`.

For the new multi-arch Linux build workflow, manifests are not scoped by GPU
family and are uploaded under `{run_id}-linux/manifests/pytorch/`.

The multi-arch Linux release workflow now generates all PyTorch manifests once
before expanding the build matrix. It uploads those manifests, generates a
matrix with an explicit `manifest_url` for each `(pytorch_git_ref,
python_version)` cell, and the reusable build workflow downloads its assigned
manifest. Direct dispatch of the reusable build workflow still generates and
uploads a one-off manifest when `manifest_url` is not provided.

### Repo URL consistency

All repo URLs in manifests use `https://github.com/{owner}/{repo}` without
`.git` suffix. URLs from `related_commits` (upstream data) already omit it;
we now match that for URLs we construct.

### Workflow architecture (target state)

```
orchestrator
  +-> prepare_manifests (one job, uploads to S3, emits matrix with manifest_url)
  +-> build_and_test (matrix: pytorch_ref x python_version)
        calls: reusable per-cell workflow
          +-> prepare_manifest (passes through manifest_url, or generates one)
          +-> build (downloads manifest, checks out, builds, uploads wheels)
          +-> generate_test_matrix (reads manifest/package versions)
          +-> test (matrix: family/test_level, calls test_pytorch_wheels.yml)
```

The per-cell reusable workflow should run tests for a successful build without
waiting for unrelated matrix cells. For example, a successful `release/2.10`
build should be able to test even if a separate `nightly` build fails. Keep the
parent matrix `fail-fast: false` and make test jobs depend only on the build
inside the same reusable workflow invocation.

### User-facing script entry points

Prefer a small number of user-facing scripts over many low-level CLI wrappers:

- `prepare_pytorch_manifests.py`: generate one or more manifests, upload them
  when requested, and emit either a single `manifest_url` or a build matrix with
  explicit `manifest_url` entries. Owns Python/PyTorch release defaults and
  exclusions so workflows do not need inline lists like `PYTHON_VERSIONS`,
  `PYTORCH_GIT_REFS`, or `release/2.8|3.14`.
- `checkout_from_manifest.py`: accept either `--manifest` or `--manifest-url`,
  validate the expected PyTorch ref when supplied, download if needed, and
  check out the requested source projects.

Keep testable units as importable functions inside those scripts. Do not add
extra CLI entry points solely to make individual operations testable.

### Test matrix and developer overrides

Script controls which (pytorch_ref, python_version, family) combos to test.
Override inputs: `python_versions`, `pytorch_git_refs`, `test_families_override`.
Future: `test_level` (none/smoke/full) per entry.

### Scope reset: focus on multi-arch workflows

The branch currently has a useful proof of concept in the non-multi-arch
`build_portable_linux_pytorch_wheels.yml` and
`build_windows_pytorch_wheels.yml` workflows. Since we plan to delete the
non-multi-arch release workflows, do not carry that workflow churn forward as
the main integration path.

Instead:

- Restore the non-multi-arch release workflows and their legacy upload scripts
  so they remain stable until deletion.
- Keep the new manifest-generation and checkout-from-manifest scripts as the
  reusable foundation.
- Add a new reusable multi-arch build workflow,
  `.github/workflows/multi_arch_build_portable_linux_pytorch_wheels.yml`.
- Update `.github/workflows/multi_arch_release_linux_pytorch_wheels.yml` to
  call that reusable build workflow, mirroring how
  `.github/workflows/release_portable_linux_pytorch_wheels.yml` calls
  `.github/workflows/build_portable_linux_pytorch_wheels.yml`.
- Defer Windows multi-arch release integration until the Linux path is reviewed
  and passing.

## Next steps

1. [x] Revert the non-multi-arch workflow experiment on this branch.
   Restore `.github/workflows/build_portable_linux_pytorch_wheels.yml`,
   `.github/workflows/build_windows_pytorch_wheels.yml`,
   `build_tools/github_actions/upload_pytorch_manifest.py`, and
   `build_tools/github_actions/tests/upload_pytorch_manifest_test.py` to the
   pre-experiment behavior.
2. [x] Keep and test the reusable manifest pieces:
   `generate_pytorch_manifest_upfront.py`, `checkout_from_manifest.py`,
   `upload_pytorch_manifests.py`, `WorkflowOutputRoot.pytorch_manifest_dir()`,
   and the GitHub API helpers.
3. [x] Add unit tests for `generate_pytorch_manifest_upfront.py`.
   Cover stable vs nightly resolution, Linux vs Windows project defaults,
   `release/2.12` matrix coverage, manifest version fields, and the
   `--output` single-manifest mode.
4. [x] Add unit tests for `checkout_from_manifest.py`.
   Mock subprocess calls and verify project ordering, checkout directories,
   `--no-hipify`, missing project errors, and repo/commit argument plumbing.
5. [x] Create `.github/workflows/multi_arch_build_portable_linux_pytorch_wheels.yml`
   as the reusable per-cell Linux multi-arch build workflow. It should accept
   `python_version`, `pytorch_git_ref`, `amdgpu_families`, `rocm_version`,
   `rocm_package_find_links_url`, `release_type`, `repository`, `ref`, and
   `cache_type`; generate or consume a manifest; checkout from the manifest;
   build fat wheels; split torch/torchvision; upload wheels to the multi-arch
   Python release bucket; upload the manifest to artifacts; and expose package
   versions from the manifest.
6. [x] Update `.github/workflows/multi_arch_release_linux_pytorch_wheels.yml`
   into the orchestrator. Its matrix should call
   `multi_arch_build_portable_linux_pytorch_wheels.yml` for each
   `(python_version, pytorch_git_ref)` cell, preserving the existing release
   matrix shape while moving the build body into the reusable workflow.
7. [ ] Consolidate manifest workflow plumbing into user-facing scripts.
   Move manifest generation/upload/matrix output into
   `prepare_pytorch_manifests.py`; extend `checkout_from_manifest.py` to accept
   `--manifest-url` and validate the expected PyTorch ref. Keep unit tests on
   the functions inside these scripts for generation, upload path computation,
   matrix generation, manifest download, validation, and checkout command
   construction.
8. [ ] Restructure `multi_arch_build_portable_linux_pytorch_wheels.yml` around
   a `prepare_manifest` job. If `manifest_url` is provided, pass it through; if
   not, generate/upload one manifest for the requested Python/PyTorch cell.
   Make the build and test jobs consume that output instead of duplicating
   manifest logic.
9. [ ] Add per-cell quick test orchestration inside the reusable build workflow.
   Generate a small test matrix from the manifest and package versions for the
   just-built cell, then call `test_pytorch_wheels.yml` with `multi_arch=true`
   and manifest-driven test-source checkout. Start with a conservative test
   subset and add `test_level` controls before broadening.
10. [ ] Run a focused Linux workflow-dispatch validation on a small matrix
   (one Python version, one PyTorch ref, one or two families). Verify the
   manifest is generated upfront, the build checks out from it, wheels upload to
   `whl-multi-arch`, and the manifest index is linked from the run summary.
11. [ ] After Linux build/test plumbing is stable, decide whether the parent
   release workflow should always use the full release matrix or expose an
   explicit developer-oriented matrix profile. The child workflow remains the
   preferred path for a single Python/PyTorch combination.
12. [ ] Repeat the reusable-build/orchestrator split for Windows after the Linux
   path is passing and reviewed.

## Deferred CI notes

Leave CI plumbing out of the immediate release workflow work. Before wiring
multi-arch PyTorch into CI, add or expose a project filter for
`generate_pytorch_manifest_upfront.py` so CI can build a smaller repository
set, likely `pytorch` plus possibly `triton`, while skipping audio, vision, and
apex. The manifest-driven checkout should then replace the previous explicit
per-repository checkout workflow branches without adding many new workflow
conditionals.

## Windows test signal (as of 2026-05-01)

| Target | Runners? | torch 2.9 | torch 2.10 | torch 2.11+ |
|--------|----------|-----------|------------|-------------|
| gfx110X-all | Yes | Segfault | 15,539 passed (0501) | Cancelled |
| gfx1151 | Yes | 1,924 failed + 36,950 errors | py3.11 passed, rest segfault | Failed |
| gfx120X-all | Yes | Failed | Blocked by #4889 (smoke test bug) | Cancelled |
| Others (8 families) | No runners | Skipped | Skipped | Skipped |

**Only clean signal:** gfx110X-all + torch 2.10 on 20260501.
