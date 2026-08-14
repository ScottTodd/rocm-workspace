# PR Review: ROCm/TheRock #7373

* **PR:** https://github.com/ROCm/TheRock/pull/7373
* **Title:** `ci: authenticate git clones via GITHUB_TOKEN and enforce step timeouts`
* **Head:** `d30950b52722f92186417437013c030911159298`
* **Base:** `main`
* **Reviewed:** 2026-08-14
* **Review type:** Comprehensive, with emphasis on Git authentication

## Overall Assessment

**CHANGES REQUESTED** - The checkout/fetch timeouts are useful, and the
job-scoped `GITHUB_TOKEN` with `contents: read` is the right credential to try.
However, putting that token in a global `url.insteadOf` rewrite breaks the
compiler-runtime build on both Linux and Windows. The new timeout test also
does not enforce its stated invariant.

## Findings

### BLOCKING: The token-bearing URL rewrite breaks LLVM's build

The new configuration in
[`multi_arch_build_portable_linux_artifacts.yml`](https://github.com/ROCm/TheRock/blob/d30950b52722f92186417437013c030911159298/.github/workflows/multi_arch_build_portable_linux_artifacts.yml#L132-L136)
(and the equivalent Windows/WSL/consumer-graph changes) rewrites every
`https://github.com/...` URL to a URL with the token in its userinfo. This is
not transparent to repository inspection: `git remote get-url` expands
`url.insteadOf`, so downstream tools observe a remote containing an embedded
password.

The PR's own Multi-Arch CI confirms the regression:

* [Linux compiler-runtime job 94920071532](https://github.com/ROCm/TheRock/actions/runs/31848599692/job/94920071532)
  fetched sources successfully in 1m40s, then failed while generating
  `VCSRevision.h`: `The git remote repository URL has an embedded password.`
* [Windows compiler-runtime job 94920071516](https://github.com/ROCm/TheRock/actions/runs/31848599692/job/94920071516)
  fetched sources successfully in 3m58s and failed at the same LLVM check with
  the same message.

The global setting also writes a live token into the runner user's Git config
without a matching cleanup step. `actions/checkout@v7` deliberately stores its
credential separately under `RUNNER_TEMP` and removes it during post-job
cleanup; this workflow-owned global entry is outside that lifecycle.

**Required action:** Authenticate without changing the effective repository
URL and scope the credential to the fetch operation. Suitable approaches are a
Git credential helper (for example, GitHub CLI's `gh auth setup-git` with
step-scoped `GH_TOKEN`) or a step-scoped `http.https://github.com/.extraheader`.
Then rerun at least the Linux and Windows compiler-runtime jobs and verify that
`git remote get-url origin` remains credential-free.

`x-access-token` itself is not the defect. `GITHUB_TOKEN` is a GitHub App
installation token, and GitHub documents `x-access-token` as the username when
an installation token is supplied as an HTTPS password. That form is needed
only for URL/Basic-auth injection; a credential helper or authorization header
does not require changing repository URLs.

### BLOCKING: The timeout test warns about every violation and fails on none

[`test_checkout_and_fetch_sources_have_timeouts()`](https://github.com/ROCm/TheRock/blob/d30950b52722f92186417437013c030911159298/build_tools/github_actions/tests/workflow_step_timeouts_test.py#L67-L89)
collects all missing timeouts, but when the list is non-empty it only calls
`warnings.warn()`. Consequently, the test passes not only for the 54 known
violations, but also for any new checkout or `fetch_sources.py` step added
without a timeout. It therefore cannot provide the PR description's claimed
"failing the PR if any new step is added without one" behavior.

**Required action:** Represent the existing debt as an explicit allowlist (or
equivalent baseline), warn only for those known entries, and fail for every
unrecognized violation. Add focused unit coverage proving that a newly added
violating step fails while an allowlisted legacy violation does not.

### IMPORTANT: PR #7354 proves token acceptance, not reduced throttling

The paired jobs in [PR #7354](https://github.com/ROCm/TheRock/pull/7354)
both succeeded. In that one run, the authenticated `Fetch sources` step took
5m42s while the unauthenticated control took 2m56s. The PyTorch job also shows
that this repository-scoped token can authenticate a public cross-repository
clone. That is useful compatibility evidence, but one successful run per arm
does not validate a reliability improvement for an intermittent 30-minute
stall.

**Recommendation:** Describe #7354 as an authentication compatibility test,
not validation that throttling is fixed. Collect repeated runs or GitHub-side
evidence before claiming the mitigation reduces stalls. This does not need to
block the mechanism change if the GitHub administrator recommendation is the
operational basis, but the claim should be calibrated.

## GitHub Authentication Guidance

GitHub creates `GITHUB_TOKEN` for the job, but raw `git` does not automatically
read that Actions context. `actions/checkout` consumes `${{ github.token }}` by
default and persists credentials for Git operations associated with its
checkout. `fetch_sources.py`, however, launches additional submodule updates
and independent clones, so it needs an authentication mechanism those child
Git processes can use.

The most GitHub-native option, if `gh` is installed on every custom runner, is
to configure GitHub CLI as Git's credential helper and expose the token only to
the fetch step:

```yaml
- name: Fetch sources
  timeout-minutes: 30
  env:
    GH_TOKEN: ${{ github.token }}
  run: |
    gh auth setup-git --hostname github.com
    python build_tools/fetch_sources.py --stage ${STAGE_NAME} --jobs 12 --depth 1
```

For the existing Bash-based Windows jobs, substitute the existing command and
arguments unchanged. If `gh` is not guaranteed on the custom runner images,
use a Git credential helper or HTTP authorization header implemented without a
token-bearing remote URL, and ensure any global configuration is cleaned up in
an `always()` step.

## CI Evidence

* Unit tests passed on Ubuntu and Windows, but the new timeout test passes by
  construction because it emits warnings rather than assertions.
* Consumer graph drift passed; its authenticated fetch took 7m37s.
* Linux and Windows compiler-runtime fetches passed, proving the token was
  accepted, but both jobs then failed due to the rewritten credential-bearing
  remote URL.
* Pre-commit, action analysis, Python analysis, CodeQL, and gitleaks passed.

## Conclusion

**Approval Status: CHANGES REQUESTED**

Replace the URL rewrite with credential-free-URL authentication, verify both
compiler-runtime platforms, and make the timeout test fail for new violations.

---

Reviewed with OpenAI Codex.
