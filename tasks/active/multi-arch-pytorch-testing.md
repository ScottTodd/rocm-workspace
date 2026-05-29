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
- [x] Unit tests for generate_pytorch_source_manifest.py
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
- Issue: https://github.com/ROCm/TheRock/issues/5496 (running PyTorch tests)
- PR #4996: `multi_arch` input for test workflows (merged)
- PR #5107: drop whl-staging, publish directly to whl-multi-arch (merged)
- PR #5406: GitHub Actions API ref/file helpers
  (`users/scotttodd/torch-github-actions-api`, merged)
- PR #5407: export PyTorch version suffix from `determine_version.py`
  (`users/scotttodd/torch-version-suffix`, merged)
- PR #5452: split reusable multi-arch PyTorch build workflows
  (`users/scotttodd/torch-reusable-pytorch-build-workflows`, merged)
- PR #5503: PyTorch source manifest generation and checkout foundation
  (`users/scotttodd/torch-manifest-generate-checkout`, draft)

### Key files

```
# New manifest scripts
build_tools/github_actions/generate_pytorch_source_manifest.py
build_tools/github_actions/prepare_pytorch_manifests.py
build_tools/github_actions/configure_pytorch_test_matrix.py
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
- `generate_pytorch_source_manifest.py`: resolves refs -> commits via
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
          +-> generate_quick_test_matrix (auto: built families; overrideable)
          +-> test (matrix: family/runner, calls test_pytorch_wheels.yml)
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

Do not add a separate `pytorch_manifest_manager.py` wrapper unless it actually
retires or renames an existing entry point. A single coherent script with
well-factored functions is preferable to a thin +300 LOC CLI layer over two
large scripts.

For future JAX and other framework releases, avoid forcing a generic PyTorch-
shaped manager abstraction too early. The likely reusable layer is a small set
of shared helpers for listing manifests from local/S3 locations, reading JSON
manifests, uploading manifest directories, and emitting GitHub Actions outputs.
Each framework can keep its own release-ref and version logic.

For the longer-term "freeze commits before release" flow,
`prepare_pytorch_manifests.py` should also be able to consume an existing
manifest directory URL and emit the explicit build matrix from the manifests in
that directory. Prefer listing the S3 prefix directly when credentials are
available instead of relying on deterministic filenames, an uploaded JSON map,
or server-side `index.html` generation.

### Alternatives considered

#### Freeze only framework root commits

For PyTorch, the minimum commit freeze is probably just TheRock plus the root
`torch` commit. A pinned `torch` commit should, when the `related_commits` and
`ci_commit_pins` files are complete, determine the other source repository
commits during checkout. The same higher-level idea could support future JAX
releases: one scheduler job freezes root refs for TheRock, PyTorch, JAX, and
other frameworks, then dispatches framework-specific release jobs with those
frozen roots.

This is a useful future direction, but it is weaker as the direct build/test
contract. Reruns would still depend on later checkout-time interpretation of
framework-specific pin files and repository layout. Keep that as a scheduler
layer, not as the only data passed into build and test jobs.

#### Expanded manifests as the build/test contract

The current PyTorch approach expands the root torch ref into a full manifest
before build jobs run. That is more verbose, but it gives build, test, rerun,
and local repro paths one concrete object to consume. It also keeps the
manifest-driven checkout script useful for developers: generate a manifest,
then check out exactly the sources from that manifest, without manually
matching several repo commands from docs.

For JAX and other frameworks, avoid forcing a PyTorch-shaped manifest manager
too early. A future scheduler can freeze root commits first, then call
framework-specific expanders to produce the expanded manifests consumed by
release workflows. Smaller frameworks may produce smaller manifests while still
using the same manifest-directory, upload, checkout, and summary patterns.

### Test matrix and developer overrides

Script controls which `(pytorch_ref, python_version)` combos to build and which
GPU families to quick-test after an individual build. Override inputs:
`python_versions`, `pytorch_git_refs`, and quick-test GPU families. Quick tests
default to `auto`, meaning "test the families covered by the build"; `none`
skips quick tests explicitly.

Keep full PyTorch test dispatch separate from quick tests: model that path after
PR #4499 with an explicit `run_full_pytorch_tests` input plus release/cadence
rules, and pass the build cell's `manifest_url`, `torch_version`, and
`package_index_url` outputs to `test_pytorch_wheels_full.yml`.

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
   `generate_pytorch_source_manifest.py`, `checkout_from_manifest.py`,
   `prepare_pytorch_manifests.py`, `WorkflowOutputRoot.pytorch_manifest_dir()`,
   and the GitHub API helpers.
3. [x] Add unit tests for `generate_pytorch_source_manifest.py`.
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
7. [x] Consolidate manifest workflow plumbing into user-facing scripts.
   Move manifest generation/upload/matrix output into
   `prepare_pytorch_manifests.py`; extend `checkout_from_manifest.py` to accept
   `--manifest-url` and validate the expected PyTorch ref. Keep unit tests on
   the functions inside these scripts for generation, upload path computation,
   matrix generation, manifest download, validation, and checkout command
   construction.
8. [x] Restructure `multi_arch_build_portable_linux_pytorch_wheels.yml` around
   a `prepare_manifest` job. If `manifest_url` is provided, pass it through; if
   not, generate/upload one manifest for the requested Python/PyTorch cell.
   Make the build and test jobs consume that output instead of duplicating
   manifest logic.
9. [x] Add per-cell quick test orchestration inside the reusable build workflow.
   Add a `test_amdgpu_families` input, generate a small quick-test matrix with
   `configure_pytorch_test_matrix.py`, then call `test_pytorch_wheels.yml` with
   `multi_arch=true`, the package index URL output by the publish step, and
   manifest-driven test-source checkout. The default `auto` mode tests all
   built families that have configured runners; use `none` to skip tests or a
   narrower semicolon-separated family list to test a subset. Initial
   validation target is direct-dispatch build/test for one Python version, one
   PyTorch ref, and `gfx950`.
10. [x] Fix review-blocking manifest pin behavior before opening script PRs.
   `generate_pytorch_source_manifest.py` should fail fast if a stable
   PyTorch ref is missing a required `related_commits` pin for audio, vision,
   or apex. Do not fall back to a branch like `nightly`, `master`, or `main`.
   Add a regression test for the missing-pin case. Consider making malformed
   `related_commits` lines fatal as part of the same cleanup.
11. [ ] Improve GitHub Actions job summaries for multi-arch PyTorch runs.
   The manifest preparation summary should keep the manifest index link, add
   links to individual manifest files, and show the generated build matrix
   (`pytorch_git_ref` x `python_version`) with explicit manifest URLs. The
   quick-test configuration job should not post a separate noisy summary when
   the per-test jobs immediately below it already summarize what is being
   tested. The PyTorch test report should include the build manifest link when
   `manifest_url` is provided.
12. [ ] Add developer debugging docs for the new multi-arch PyTorch workflows.
   Extend `docs/development/github_actions_debugging.md` near "Testing PyTorch
   release workflows" with narrow dev-dispatch examples for
   `multi_arch_release_linux_pytorch_wheels.yml`, direct child workflow usage
   once available on the default branch, semicolon-separated list inputs,
   manifest locations, and how build outputs feed quick tests.
13. [ ] Decide how much inline shell cleanup is required before the workflow
   PR. The new Linux reusable workflow still has copied cache-flag and wheel
   split shell logic. Either extract the largest new blocks into scripts before
   review or explicitly scope that as a follow-up in the workflow PR.
14. [ ] Run a focused Linux workflow-dispatch validation on a small matrix
   (one Python version, one PyTorch ref, one or two families). Verify the
   manifest is generated upfront, the build checks out from it, wheels upload to
   `whl-multi-arch`, and the manifest index is linked from the run summary.
15. [ ] After Linux build/test plumbing is stable, decide whether the parent
   release workflow should always use the full release matrix or expose an
   explicit developer-oriented matrix profile. The child workflow remains the
   preferred path for a single Python/PyTorch combination.
16. [ ] Add full-test dispatch after quick Linux validation. Follow the shape
   from PR #4499, but dispatch from each successful reusable build cell using
   that cell's manifest URL, torch version output, and package index URL output
   instead of re-resolving package versions from the index. Keep this separate
   from inline quick tests via a `run_full_pytorch_tests` boolean and cadence
   rules for daily release branches vs Sunday-only PyTorch nightly.
17. [ ] Repeat the reusable-build/orchestrator split for Windows after the Linux
   path is passing and reviewed.
18. [ ] Optimize manifest-based test source checkout. For test-only repro and
   workflow paths, add a way for `checkout_from_manifest.py` or the underlying
   PyTorch repo fetch scripts to skip `git submodule update`, similar to how
   they can already skip hipify with `--no-hipify`.
19. [ ] Add manifest-directory consume mode to `prepare_pytorch_manifests.py`.
   Given a local manifest directory or S3-backed manifest directory URL, list
   the manifest JSON files, read their PyTorch refs and Python versions, and
   emit the same explicit build matrix used after freshly generated manifests.
   This should support future scheduler workflows that freeze commits in one
   job and later dispatch release workflows from the frozen manifest directory.

## PR sequence

1. GitHub Actions API helpers:
   PR #5406, `users/scotttodd/torch-github-actions-api`. Adds ref resolution
   and file-content fetch helpers used by manifest generation.
2. Version suffix export:
   PR #5407, `users/scotttodd/torch-version-suffix`. Makes
   `determine_version.py` export the PyTorch version suffix for later manifest
   generation/build consistency.
3. Reusable workflow split:
   PR #5452, `users/scotttodd/torch-reusable-pytorch-build-workflows`.
   Splits the multi-arch PyTorch release workflows into reusable build
   workflows without depending on the new manifest code.
4. Manifest generation and checkout foundation:
   PR #5503, `users/scotttodd/torch-manifest-generate-checkout` (merged).
   `generate_pytorch_source_manifest.py`, `checkout_from_manifest.py`,
   manifest utilities, repo checkout support, focused unit tests, and manifest
   checkout/versioning docs.
5. Manifest upload and Linux build workflow plumbing:
   `prepare_pytorch_manifests.py`, `WorkflowOutputRoot.pytorch_manifest_dir()`,
   and `.github/workflows/multi_arch_build_portable_linux_pytorch_wheels.yml`
   plumbing for direct child workflow runs. The child workflow can pass through
   an explicit `manifest_url` or generate/upload one manifest, then the build
   job checks out source from that manifest. Keep release-orchestrator matrix
   generation, `write_torch_versions.py --expected-manifest`, package-index
   outputs, and test wiring out of this PR. Current branch:
   `users/scotttodd/torch-manifest-build-workflow`.
6. PyTorch test workflow wiring:
   add `configure_pytorch_test_matrix.py`, connect successful build jobs to
   quick tests via `test_pytorch_wheels.yml`, and plumb manifest/package index
   outputs into test summaries. Track broader/full-test dispatch under #5496.
7. Linux multi-arch release orchestrator integration:
   `.github/workflows/multi_arch_release_linux_pytorch_wheels.yml` generates
   all release manifests once, emits the explicit matrix, and calls the
   standalone build/test workflow for each cell. Include manifest summary
   improvements here: index link, individual manifest links, and generated
   matrix display. Add `docs/development/github_actions_debugging.md` coverage
   for direct build workflow runs and release-orchestrator runs. Planned after
   the standalone workflow PR.
8. Follow-up platform/test expansion:
   Windows reusable build/orchestrator parity, full-test dispatch, and CI
   plumbing.

## Branch inventory

Current review stack:

- `users/scotttodd/torch-manifest-build-workflow`: active branch on `main`.
  Adds the minimal manifest prepare/upload helper and wires
  `multi_arch_build_portable_linux_pytorch_wheels.yml` to generate or consume a
  manifest URL before building. No release-orchestrator or test-workflow wiring.
- `users/scotttodd/torch-manifest-prepare-workflow`: stacked branch on
  `torch-manifest-generate-checkout` (`ba353030c`). Contains the deferred
  manifest prepare/upload/output layer plus a rough workflow/test-plumbing draft
  carried forward from the older build-test branch. Clean this branch before
  review; likely split or trim test wiring.
- `users/scotttodd/torch-manifest-build-test`: older follow-up branch used as a
  source for selected workflow draft files. It is no longer the active stacked
  review branch.
- `users/scotttodd/torch-manifest-release-linux`: older release orchestrator
  integration branch. Rebase or reconstruct after the standalone build and
  test wiring PRs are settled.

Backup and historical branches:

- `torch-manifest-foundation-backup-20260528`: backup of the pre-rebase
  foundation branch (`c9ba22322`).
- `users/scotttodd/torch-manifest-split-backup`: backup of the combined
  foundation branch before the generate-checkout / prepare-workflow split
  (`c0e9cfaca`).
- `torch-manifest-foundation-pre-5406-5407-rebase`: backup before PR #5406 and
  PR #5407 landed (`035b073d2`).
- `torch-manifest-foundation-pre-split`: earlier pre-split backup
  (`d323becff`).
- `torch-manifest-build-test-pre-5406-5407-rebase`: older build/test backup
  (`3858b3a6d`).
- `torch-manifest-release-linux-pre-5406-5407-rebase`: older release Linux
  backup (`0cc9f1a0a`).
- `torch-manifest-2-backup`: broad backup of the previous combined branch
  (`4e6ef20e9`).
- `users/scotttodd/torch-manifest-1`, `users/scotttodd/torch-manifest-2`, and
  `multi-arch-torch-manifest`: earlier development snapshots retained for
  reference.

## Current manifest foundation cleanup

PR #5503 merged from `users/scotttodd/torch-manifest-generate-checkout`.

Cleanup priorities for PR #5503 review:

- Simplify tests so they cover manifest contents, matrix outputs, checkout
  command interfaces, version checks, and GitHub/API boundaries instead of
  asserting incidental markdown summary formatting.
- Keep non-release and fork behavior easy to extend later. Do not solve it in
  this PR, but document the current contract: `nightly` resolves against
  upstream `pytorch/pytorch`, other refs resolve against `ROCm/pytorch`, full
  ecosystem manifests require release-style pin files, and `--projects pytorch`
  is the narrow branch-development escape hatch.
- Keep Windows Triton behavior explicit. The current default excludes Triton on
  Windows. Before review, remove any docs that imply unsupported Windows Triton
  opt-in works, or add an explicit escape hatch for early bring-up. The natural
  future default should follow upstream PyTorch pins once the same pin format is
  available.
- Treat GitHub API retry/backoff as separate unless it becomes necessary for
  this PR. The foundation currently fails fast with clear API errors.

Progress on 2026-05-28:

- Rebased/squashed foundation branch onto `main`.
- Focused manifest tests pass locally: 31 tests across manifest generation,
  manifest preparation, checkout-from-manifest, and wheel version verification.
- Dropped `release/2.8` from the new manifest default release refs to match
  recent release matrix cleanup on `main`.
- Split the combined branch into
  `users/scotttodd/torch-manifest-generate-checkout` and
  `users/scotttodd/torch-manifest-prepare-workflow`.
- Cleaned up `generate_pytorch_source_manifest.py` before drafting PR #5503:
  default `--platform` now follows the local system like other TheRock scripts,
  tests use explicit project lists instead of helper logic in setup, and
  comments document `related_commits` and Triton pin source file formats.
- Windows Triton handling is now intentionally narrow. The default project set
  still excludes Triton on Windows; explicit Windows nightly Triton opt-in reads
  `external-builds/pytorch/ci_commit_pins/triton-windows.txt`; explicit
  Windows release Triton fails with a clear nightly-only error. A skipped test
  marks the future one-line default flip once nightly Triton is ready.
- Drafted PR #5503 with motivation, current-vs-new manifest flow diagram,
  technical details, and manual/GitHub Actions test evidence.

Progress on 2026-05-29:

- PR #5503 merged to `main`.
- Created `users/scotttodd/torch-manifest-build-workflow` from `main` for the
  next PR. Scope is intentionally limited to the reusable Linux build workflow:
  pass through or generate/upload one manifest URL, then checkout PyTorch source
  repos from that manifest before building. Release-orchestrator matrix
  generation and PyTorch test wiring remain deferred.
- Paused work on the build-workflow branch after finding a direct-dispatch
  ergonomics issue: GitHub applies the `pytorch_git_ref` default even when a
  user provides an explicit `manifest_url`, which caused a downloaded
  `release/2.9` manifest to be validated against the workflow default
  `release/2.12`.
- Direction for next week: avoid a hidden fallback/default PyTorch ref in this
  path. The active release default changes over time, so it should not be
  duplicated across workflow names, job names, and helper-script outputs.
  Prefer explicit behavior:
  - `manifest_url` provided and `pytorch_git_ref` empty: trust the manifest and
    do not run expected-ref validation.
  - `manifest_url` provided and `pytorch_git_ref` set: validate that the
    manifest's PyTorch branch/ref matches the explicit input.
  - `manifest_url` empty: require an explicit `pytorch_git_ref` before
    generating/uploading a one-off manifest.
- Do not carry forward the larger "compute a default and emit normalized ref
  outputs" experiment unless there is a stronger reason than the default-value
  issue. Keep this branch biased toward simplifying the workflow and script
  interface.
- Current local TheRock worktree has partial experimental edits in
  `multi_arch_build_portable_linux_pytorch_wheels.yml`,
  `multi_arch_build_windows_pytorch_wheels.yml`,
  `prepare_pytorch_manifests.py`, and
  `prepare_pytorch_manifests_test.py`. Reconcile those edits before the next
  push or workflow-dispatch test run.

## Deferred CI notes

Leave CI plumbing out of the immediate release workflow work. Before wiring
multi-arch PyTorch into CI, add or expose a project filter for
`generate_pytorch_source_manifest.py` so CI can build a smaller repository
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
