# Branch Review: users/scotttodd/torch-manifest-foundation

* **Branch:** `users/scotttodd/torch-manifest-foundation`
* **Base:** `upstream/main`
* **Reviewed:** 2026-05-26
* **Commits:** 2 commits

## Summary

This branch adds the PyTorch manifest script foundation:

* `generate_pytorch_manifest_upfront.py` resolves PyTorch ecosystem source
  commits and expected package versions before build jobs run.
* `prepare_pytorch_manifests.py` is the workflow-facing entry point for
  manifest pass-through, generation/upload, uploaded-directory consumption, and
  release matrix output.
* `checkout_from_manifest.py` gives developers and CI one command to check out
  the repositories pinned by a manifest.
* `write_torch_versions.py` can now compare built wheel versions against a
  manifest.
* `WorkflowOutputRoot`, manifest utils, versioning docs, and the PyTorch README
  are updated to describe the new manifest path.

Evidence checked:

* `D:/projects/TheRock/.venv/Scripts/python.exe -m pytest github_actions/tests/generate_pytorch_manifest_upfront_test.py github_actions/tests/prepare_pytorch_manifests_test.py github_actions/tests/checkout_from_manifest_test.py github_actions/tests/write_torch_versions_test.py`
  passed: 31 tests in 0.21s. Pytest warned that the local `.pytest_cache`
  directory is not writable.
* `pre-commit run --files ...` across the changed Python, tests, docs, and
  README files passed.

## Overall Assessment

**CHANGES REQUESTED BEFORE PR** - The core script design is sound and the
coverage is broad enough, but I found a few issues worth cleaning up before
opening this branch for review. The highest-value fixes are to correct the
Windows Triton docs/current behavior, document or implement the intended
non-release/fork workflow, and decide whether GitHub API retries belong in this
foundation PR.

## Findings

### IMPORTANT: README advertises unsupported Windows Triton opt-in

`external-builds/pytorch/README.md` documents a Windows Triton opt-in command
with `--projects "pytorch pytorch_audio pytorch_vision triton"` around line
529. The implementation still raises `NotImplementedError` for any Windows
Triton manifest generation in
`build_tools/github_actions/generate_pytorch_manifest_upfront.py` around line
185.

Impact: a developer following the documented command will get a deliberate
failure. This also does not yet meet the desired path for nightly Windows
PyTorch builds against a pinned `triton-windows` repository.

Recommendation: either remove that command and leave the TODO prose, or add an
explicit opt-in path such as `--windows-triton-ref` / `--windows-triton-repo`
for nightly and branch-development testing while keeping release defaults
disabled until the pin policy is settled.

### IMPORTANT: non-release and fork behavior is not explicit enough

`generate_pytorch_manifest_upfront.py` selects the torch repository from only
two cases: literal `nightly` uses `pytorch/pytorch`, and all other refs use
`ROCm/pytorch` around line 270. For non-nightly refs, default Linux projects
then require `related_commits` pins for audio, vision, and apex around lines
288-322.

Impact: a branch on `ROCm/pytorch` that is missing `related_commits` fails
loudly, which is good for release branches. A branch or commit on a fork, or an
upstream `pytorch/pytorch` branch that is not exactly `nightly`, is not
addressable today except by first pushing it to the expected repository or by
building only torch with `--projects pytorch`.

Recommendation: document this contract in the README/script help. If fork and
pre-merge branch testing is in scope for this PR, add explicit torch repo inputs
instead of overloading `--pytorch-git-refs`.

### IMPORTANT: GitHub API calls fail fast but do not retry transients

Manifest generation uses `gha_resolve_git_ref()` and
`gha_fetch_file_contents()` in `generate_pytorch_manifest_upfront.py` around
lines 132-140. The underlying `GitHubAPI.send_request()` reports HTTP, network,
timeout, and JSON errors, but does not retry transient 5xx, connection reset,
or timeout failures.

Impact: the release-orchestrator path will make many GitHub API requests in one
job. A single transient GitHub/API/network failure can fail the whole manifest
freeze job even though rerunning may succeed.

Recommendation: add bounded retry with exponential backoff in the GitHub API
helper, or deliberately defer it with a TODO and keep the current fail-fast
behavior for the first PR.

### SUGGESTION: add a Windows release matrix preset or clarify Linux-only preset

`prepare_pytorch_manifests.py` has `--matrix-preset linux-release` only around
line 391, with default release refs/excludes around lines 44-45. The script can
generate Windows manifests by passing `--platform windows`, but callers must
spell out Windows refs and Python versions manually.

Recommendation: either add `windows-release` before wiring Windows workflows,
or keep this as a follow-up and make the help/docs clear that the only preset
is currently Linux.

### SUGGESTION: trim assertions that mainly preserve a previous summary shape

`prepare_pytorch_manifests_test.py` asserts `self.assertNotIn("### Inputs",
summary)` around lines 308 and 387. These assertions read like guardrails
against an earlier development version rather than behavior a user depends on.

Recommendation: remove those checks or replace them with positive assertions
for the summary content users actually need.

## Notes On The User Questions

* Tests are fast and cover the important script units: manifest resolution,
  missing/malformed pins, matrix generation, uploaded-directory consumption,
  checkout command construction, and version verification. The generator tests
  are still verbose, but mostly because the fake GitHub fixtures are explicit.
* The scripts are reasonably composable: `generate` writes manifests,
  `prepare` uploads/emits CI outputs, and `checkout` consumes manifests. The
  boundary between `generate` and `prepare` is understandable.
* Documentation is good for the local generate + checkout path. It is thinner
  for `prepare_pytorch_manifests.py` developer usage and currently wrong for
  Windows Triton opt-in.
* Improperly configured release branches now fail loudly for missing or
  conflicting `related_commits`, which matches the desired behavior.
* Non-release branches work best when they are on the expected repository and
  either provide the same pins as a release branch or build only `pytorch`.
* Windows Triton is excluded by default. Explicit opt-in is documented but not
  implemented yet.

## Conclusion

The branch is close, but I would fix the Windows Triton documentation/behavior
and clarify the non-release/fork contract before sending it. Retry/backoff is
the one reliability question to decide before review: it is not required for
correctness, but it is likely to matter once manifest generation becomes a
single release-freeze gate.
