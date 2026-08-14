# PR Re-review: ROCm/TheRock #7373

* **PR:** https://github.com/ROCm/TheRock/pull/7373
* **Title:** `ci: authenticate git clones via GITHUB_TOKEN and enforce step timeouts`
* **Head:** `e8ae1e63e4643ce994141b293c6de527d41223d3`
* **Base:** `main`
* **Reviewed:** 2026-08-14
* **Review type:** Comprehensive re-review, with emphasis on Git authentication

## Overall Assessment

**CHANGES REQUESTED** - The updated credential-helper approach fixes the
credential-bearing remote URL problem, and the timeout test now rejects
ordinary new violations. However, `gh` is not installed in the portable Linux
build container, so the affected compiler-runtime workflow now fails before
fetching any sources. The allowlist also retains exemptions after violations
are fixed and can mask new same-named steps.

## Findings

### BLOCKING: Portable Linux requires an executable that its container does not provide

[`Fetch sources` now invokes `gh auth setup-git`](https://github.com/ROCm/TheRock/blob/e8ae1e63e4643ce994141b293c6de527d41223d3/.github/workflows/multi_arch_build_portable_linux_artifacts.yml#L157-L164),
but the portable Linux container image does not include GitHub CLI. The updated
[Linux compiler-runtime job](https://github.com/ROCm/TheRock/actions/runs/31850715001/job/94926102947)
failed immediately in that step with:

```text
/__w/_temp/...sh: line 1: gh: command not found
```

This is the workflow's first use of `gh`, and there is no preceding install
step. Consumer graph drift passes because GitHub-hosted Ubuntu includes GitHub
CLI; that does not validate the custom build container.

**Required action:** Use an authentication mechanism available on every target
runner/container, or explicitly add and maintain the missing dependency. A
small and dependency-free option is to pass the existing `url.insteadOf` rule
through step-scoped Git runtime configuration:

```yaml
env:
  GIT_CONFIG_COUNT: 1
  GIT_CONFIG_KEY_0: url.https://x-access-token:${{ github.token }}@github.com/.insteadOf
  GIT_CONFIG_VALUE_0: https://github.com/
```

Git documents `GIT_CONFIG_COUNT`, `GIT_CONFIG_KEY_<n>`, and
`GIT_CONFIG_VALUE_<n>` specifically for spawning multiple Git commands with
common runtime-only configuration. Because these variables are scoped to the
`Fetch sources` step, the rewrite is gone before LLVM queries the remote URL,
and no token-bearing setting is written to global or repository config.

An HTTP authorization header scoped to the same step would avoid URL rewriting
entirely, but its Basic value must be constructed and masked safely. If that
requires non-trivial inline shell, put the setup in a tested helper script.

After changing the mechanism, rerun the portable Linux and Windows
compiler-runtime jobs. Also exercise the WSL workflow or otherwise verify its
pre-WSL Windows-host fetch path.

### BLOCKING: Resolved allowlist entries remain permanent exemptions

The updated timeout test now fails violations whose generated string is not in
`_KNOWN_VIOLATIONS`, which resolves the original unconditional-warning bug.
However, the generated identity is only
[`workflow / job / step name`](https://github.com/ROCm/TheRock/blob/e8ae1e63e4643ce994141b293c6de527d41223d3/build_tools/github_actions/tests/workflow_step_timeouts_test.py#L105-L126),
and the test only checks whether that string is a member of the allowlist.

There are two resulting bypasses:

* When issue #7388 adds a timeout to a known step, its unused allowlist entry
  does not fail. A later regression that removes the timeout from the same step
  is therefore still classified as pre-existing debt.
* A second missing-timeout step added to the same job with the same display
  name produces the same string and is also classified as known. The
  `frozenset` cannot represent the allowed occurrence count.

This means the test still cannot enforce the stated "any new step" invariant
over time.

**Required action:** Make each violation identity unique (for example, include
the step index) or compare occurrence counts, and fail when an allowlist entry
is no longer present so resolved exemptions must be removed. Add focused tests
for a stale allowlist entry and for a second same-named violating step.

### IMPORTANT: Update the PR description to match the new implementation and evidence

The PR body still says the workflows inject `GITHUB_TOKEN` using
`url.insteadOf`; the current head uses GitHub CLI as a credential helper. It
also continues to describe PR #7354 as validation that authentication reduces
throttling. That experiment showed compatibility, but its single authenticated
fetch took 5m42s versus 2m56s for the unauthenticated control, so it does not
establish a reliability improvement for an intermittent stall.

**Recommendation:** Describe the credential-helper implementation actually
shipped, cite GitHub administrator guidance as the operational basis for
authenticated clones, and characterize #7354 as a compatibility check rather
than evidence that throttling is fixed.

## Resolved From the Previous Review

* The token is no longer persisted in a global `url.insteadOf` entry.
* LLVM will no longer observe a credential-bearing remote URL from the current
  credential-helper design.
* Ordinary new timeout violations now call `self.fail()` rather than being
  downgraded to warnings.
* Checkout and fetch steps in the four changed workflows retain explicit
  timeouts.

## CI Evidence

* Unit tests passed on Ubuntu and Windows. The timeout test reported the 54
  current legacy violations and found no unallowlisted violation.
* Consumer graph drift passed; GitHub CLI is available on its GitHub-hosted
  Ubuntu runner.
* Portable Linux compiler-runtime failed in `Fetch sources` because `gh` is
  absent from the custom container.
* At the time of review, the Windows compiler-runtime job was still running;
  its result cannot repair the portable Linux dependency failure.
* Pre-commit, action analysis, Python analysis, CodeQL, and gitleaks passed.

## Conclusion

**Approval Status: CHANGES REQUESTED**

Remove or supply the undeclared GitHub CLI dependency, verify all affected
runner paths, close the allowlist's stale/same-name bypasses, and update the PR
description.

---

Reviewed with OpenAI Codex.
