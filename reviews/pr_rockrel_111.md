# Review: ROCm/rockrel pull request 111

- Reviewed: 2026-09-15
- Head: `decc3272dd2062a3c3f8fd52933b1c98b83f931c`
- Base: `main`
- Scope: correctness, architecture, style, tests, documentation, security, performance.
- Overall assessment: **CHANGES REQUESTED**

## Findings

### 1. BLOCKING: The read-only checker and default dry run perform destructive local operations

[check_release_branch_state.py:87](https://github.com/ROCm/rockrel/blob/decc3272dd2062a3c3f8fd52933b1c98b83f931c/scripts/check_release_branch_state.py#L87) calls `build_plan`, which checks out the requested commit and runs `git reset --hard` unconditionally at [repo_plan.py:144](https://github.com/ROCm/rockrel/blob/decc3272dd2062a3c3f8fd52933b1c98b83f931c/scripts/repo_plan.py#L144). A reused cache containing uncommitted tracked changes loses them, even when checking the same commit. Planning also clones/fetches and updates submodules; `--force-clone` can delete an invalid cache directory. This contradicts the checker's explicit read-only contract.

The creation command calls the same planner regardless of dry-run mode. Its [create_release_branches.py:66](https://github.com/ROCm/rockrel/blob/decc3272dd2062a3c3f8fd52933b1c98b83f931c/scripts/create_release_branches.py#L66) then runs `git checkout -B` before checking `dry_run`, resetting an existing local branch and changing the working tree. Remote configuration is also changed before that guard. Only pushing is suppressed.

**Required action:** Make checks inspect an explicitly prepared local checkout without modifying it. Move clone/fetch/reset preparation into an explicit operation. Guard every mutation in the creation command, and avoid forcibly resetting existing branches by default. Add a real local-repository regression test asserting unchanged refs, files, index, and remote configuration.

**Validated:** The scratch reproduction below discarded uncommitted work through the real planner reset, then moved an existing branch and changed files through `execute_plan(..., dry_run=True)`, returning zero.

### 2. BLOCKING: Creation bypasses preflight and continues mutating later repositories after failures

[create_release_branches.py:114](https://github.com/ROCm/rockrel/blob/decc3272dd2062a3c3f8fd52933b1c98b83f931c/scripts/create_release_branches.py#L114) goes directly from `build_plan` to `execute_plan`; it never invokes `check_release_branch_state` or its checks. The module docstring says it runs preflight first. Within [create_release_branches.py:39](https://github.com/ROCm/rockrel/blob/decc3272dd2062a3c3f8fd52933b1c98b83f931c/scripts/create_release_branches.py#L39), missing paths and failed remote setup, branch creation, or pushes are accumulated while subsequent repositories are still processed. With actual pushes enabled, a known failure in one repository does not prevent publishing branches in others.

**Required action:** Establish all checkable preconditions before mutation and fail immediately when a mutation fails. Invoke the standalone checker, or explicitly document and enforce the prepared-state contract for a small creation script. Cross-repository pushes cannot be atomic, but continuing after a known failure needlessly increases partial release state. Correct the docstring.

This addresses the substance of the [original review](https://github.com/ROCm/rockrel/pull/90#pullrequestreview-5035135052): focused checks followed by readily auditable mutations. Splitting the original code into files does not establish that boundary.

### 3. BLOCKING: Discovery errors silently remove repositories from the release plan

[repo_plan.py:29](https://github.com/ROCm/rockrel/blob/decc3272dd2062a3c3f8fd52933b1c98b83f931c/scripts/repo_plan.py#L29) catches every exception while reading submodule paths and returns an empty map. [repo_plan.py:45](https://github.com/ROCm/rockrel/blob/decc3272dd2062a3c3f8fd52933b1c98b83f931c/scripts/repo_plan.py#L45) likewise treats every URL lookup failure as a missing URL; [repo_plan.py:114](https://github.com/ROCm/rockrel/blob/decc3272dd2062a3c3f8fd52933b1c98b83f931c/scripts/repo_plan.py#L114) skips those repositories. A malformed configuration or failed Git command can therefore yield a partial plan which creation reports as successful.

**Required action:** Propagate unexpected Git/configuration errors and reject missing required URL entries. Handle only an explicitly expected no-match condition. Never interpret failure to discover release inputs as an empty successful result.

**Validated:** A real malformed `.gitmodules` file returned `{}` rather than an error.

### 4. BLOCKING: Tests miss the safety contract and duplicate implementation logic

At [tests/test_create_release_branch.py:124](https://github.com/ROCm/rockrel/blob/decc3272dd2062a3c3f8fd52933b1c98b83f931c/scripts/tests/test_create_release_branch.py#L124), the dry-run test mocks remote setup and command execution and only checks that no command contains `push`. It passes with the destructive checkout above. At [tests/test_create_release_branch.py:80](https://github.com/ROCm/rockrel/blob/decc3272dd2062a3c3f8fd52933b1c98b83f931c/scripts/tests/test_create_release_branch.py#L80), the org-filter test reimplements the predicate inside the test instead of calling production code; it cannot detect a regression in repository discovery.

**Required action:** Replace the copied-predicate test with behavior exercised through real discovery inputs. Cover read-only checks and dry runs using disposable local Git repositories, mocking external network boundaries only. Include malformed inputs and stop-on-failure behavior. Keep these tests focused rather than adding wrapper-call assertions.

CI does run the tests: 54 passed on both platforms. The coverage report shows the entire `build_plan` body and repository collection path unexecuted; neither new check module appears in that report.

### 5. IMPORTANT: Resolve commit references with Git instead of requiring lowercase full SHA-1 text

[check_release_branch_state.py:132](https://github.com/ROCm/rockrel/blob/decc3272dd2062a3c3f8fd52933b1c98b83f931c/scripts/check_release_branch_state.py#L132), [create_release_branches.py:104](https://github.com/ROCm/rockrel/blob/decc3272dd2062a3c3f8fd52933b1c98b83f931c/scripts/create_release_branches.py#L104), and [check_github_permissions.py:200](https://github.com/ROCm/rockrel/blob/decc3272dd2062a3c3f8fd52933b1c98b83f931c/scripts/check_github_permissions.py#L200) duplicate the same 40-character regex. Valid short object names, tags, branches, and revision expressions are rejected before Git can resolve them. The regex does not establish that a 40-character value exists or names a commit.

**Recommendation:** For commands operating on the prepared checkout, resolve once using `git rev-parse --verify --end-of-options <ref>^{commit}`, then pass the resulting full object ID onward. Define the standalone API-only permission check's ref contract explicitly rather than copying a SHA regex. Test valid refs and missing/non-commit objects.

### 6. IMPORTANT: Replace the subprocess framework with standard functionality

[release_utils.py:18](https://github.com/ROCm/rockrel/blob/decc3272dd2062a3c3f8fd52933b1c98b83f931c/scripts/release_utils.py#L18) adds two execution paths, manual byte decoding, output forwarding, timeout cleanup, and custom command-error reconstruction. In the streaming path, iteration over stdout happens *before* `wait(timeout=...)`; a child that keeps stdout open can block the iterator indefinitely, so that timeout does not bound command execution.

**Recommendation:** Use `subprocess.run(..., check=True)` with inherited output for commands and `subprocess.check_output(..., text=True)` when output is needed. These standard interfaces already provide errors and output handling ([Python documentation](https://docs.python.org/3/library/subprocess.html)). Remove the generic streaming option and unnecessary timeout policy instead of extending the wrapper.

Other concrete [Python style guide](https://github.com/ROCm/TheRock/blob/main/docs/development/style_guides/python_style_guide.md) issues:

- Broad exception catches and silent omission in discovery violate fail-fast and distinct-error guidance (finding 3).
- Continuing mutation after failure violates fail-fast guidance (finding 2). Aggregating diagnostics in a read-only checker is a different, reasonable use case.
- [check_github_permissions.py:46](https://github.com/ROCm/rockrel/blob/decc3272dd2062a3c3f8fd52933b1c98b83f931c/scripts/check_github_permissions.py#L46) raises `SystemExit` inside reusable helpers; propagate appropriate exceptions and handle presentation at the CLI boundary.
- Bare `list` in the wrappers and bare `dict` in `check_repo` obscure data types. Use specific types or a small named record where useful.
- Repository discovery/filtering is implemented twice, using Git config in `repo_plan.py` and a handwritten `.gitmodules` parser in `check_github_permissions.py`. Prefer one source of repository information.
- The `--action` option only changes printed wording; remove it unless an actual behavioral distinction is needed.

The safe-default/read-only requirement comes directly from the user's requested contract; it is not presented as a verbatim rule from that style guide.

### 7. IMPORTANT: The SSH check overrides host verification policy

[check_release_branch_state.py:29](https://github.com/ROCm/rockrel/blob/decc3272dd2062a3c3f8fd52933b1c98b83f931c/scripts/check_release_branch_state.py#L29) passes `StrictHostKeyChecking=no`, weakening the caller's configured host identity checks. On first contact it can also write to known_hosts, another side effect in a purportedly read-only check.

**Recommendation:** Honor configured host-key verification. Report missing trust configuration as a precondition failure and let the user configure it separately; use noninteractive authentication checks where appropriate.

## Comparison with the local release-branching approach

Read `release-branching:scripts/create_release_branch.sh` from the local rockrel repository without switching branches. It is 29 lines and exposes the repository list, branch command, and push directly. The proposed replacement has 711 lines across its five new non-test modules, with 127 in the creation entry point; following its side effects still requires reading the planner and utility modules.

The local script is a useful structural target: operate on a prepared checkout and show a short list of Git operations. It is not itself a safe-default template: it force-moves branches and pushes immediately without a dry-run guard.

Defining `check_ssh_auth` inside a standalone check script is not inherently a violation of the original request. That review asked for a check script which includes authentication/configuration checks, not necessarily one executable per helper. The material failure is that checking mutates the checkout and the creation command neither runs those checks nor clearly trusts a prepared-state contract.

**Suggested direction:** Separate preparation, read-only checks, and explicit creation. Keep the mutation script close to the local shell example in size and visibility; use direct Git commands or straightforward subprocess calls. Treat the LOC target as a constraint encouraging simplicity, not a substitute for checking safety.

## Validation and limits

All PR checks passed: Linux unit tests, Windows unit tests, unit-test summary, and pre-commit. Inspected authenticated job logs:

- [Linux unit tests](https://github.com/ROCm/rockrel/actions/runs/34008707968/job/101420552323): 54 passed in 0.42 seconds.
- [Windows unit tests](https://github.com/ROCm/rockrel/actions/runs/34008707968/job/101420552425): 54 passed in 0.97 seconds.

Logs saved to `D:/scratch/codex/rockrel-pr111/ci-linux.log` and `ci-windows.log`. CI timing was available directly, so no author clarification was needed.

Ran a targeted reproduction against downloaded files at the reviewed SHA, using real disposable Git repositories. Only clone/fetch, submodule population, remote setup, and network branch-existence checking were mocked. No GitHub pushes or user-checkout mutations were performed. The first sandbox attempt failed during Git submodule inspection; the approved rerun outside the sandbox completed successfully.

Full command:

```powershell
$env:PYTHONDONTWRITEBYTECODE = '1'; D:/projects/TheRock/.venv/Scripts/python.exe D:/scratch/codex/rockrel-pr111/reproduce.py 2>&1 | Tee-Object D:/scratch/codex/rockrel-pr111/reproduce.log
```

Output:

```text
build_plan discarded uncommitted work: True
dry-run return code: 0
dry-run moved existing branch: True
dry-run changed checked-out files: True
malformed .gitmodules result: {}
```

Reproduction source: [reproduce.py](D:/scratch/codex/rockrel-pr111/reproduce.py). This validates local mutation and error swallowing, not an end-to-end authenticated release. Existing CI provides the full-suite evidence; the suite was not rerun locally.

Generated with Codex

