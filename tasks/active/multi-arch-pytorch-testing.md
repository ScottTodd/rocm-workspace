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
- [ ] Unit tests for generate_pytorch_manifest_upfront.py
- [ ] Unit tests for checkout_from_manifest.py
- [ ] Restructure multi-arch release workflow (orchestrator + per-cell)
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

Currently generated inline in the build job. Future: separate
generate_manifest job that runs first and uploads to S3, with the build
job downloading it. This enables an orchestrator to freeze commits once
for the entire build matrix (#1236).

### Repo URL consistency

All repo URLs in manifests use `https://github.com/{owner}/{repo}` without
`.git` suffix. URLs from `related_commits` (upstream data) already omit it;
we now match that for URLs we construct.

### Workflow architecture (target state)

```
orchestrator
  +-> generate_manifest (one job, uploads to S3)
  +-> build_and_test (matrix: pytorch_ref x python_version)
        calls: reusable per-cell workflow
          +-> build (downloads manifest, checks out, builds, uploads wheels)
          +-> generate_test_matrix (which families, runner labels)
          +-> test (matrix: family, calls test_pytorch_wheels.yml)
```

### Test matrix and developer overrides

Script controls which (pytorch_ref, python_version, family) combos to test.
Override inputs: `python_versions`, `pytorch_git_refs`, `test_families_override`.
Future: `test_level` (none/smoke/full) per entry.

## Next steps

1. [ ] Test the manifest-driven checkouts end-to-end on a real workflow run
   (trigger build_portable_linux_pytorch_wheels.yml manually)
2. [ ] Add unit tests for new scripts
3. [ ] Restructure multi-arch release workflow into orchestrator + per-cell
4. [ ] Write configure_pytorch_test_matrix.py
5. [ ] Add test jobs to multi-arch release workflows
6. [ ] Wire into CI workflows for pre-submit testing (#3291)

## Windows test signal (as of 2026-05-01)

| Target | Runners? | torch 2.9 | torch 2.10 | torch 2.11+ |
|--------|----------|-----------|------------|-------------|
| gfx110X-all | Yes | Segfault | 15,539 passed (0501) | Cancelled |
| gfx1151 | Yes | 1,924 failed + 36,950 errors | py3.11 passed, rest segfault | Failed |
| gfx120X-all | Yes | Failed | Blocked by #4889 (smoke test bug) | Cancelled |
| Others (8 families) | No runners | Skipped | Skipped | Skipped |

**Only clean signal:** gfx110X-all + torch 2.10 on 20260501.
