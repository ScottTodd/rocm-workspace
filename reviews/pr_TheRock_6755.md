# PR Review: ROCm/TheRock #6755

* **PR:** [ROCm/TheRock#6755](https://github.com/ROCm/TheRock/pull/6755)
* **Title:** `ci(bump-submodules): Post bump breadcrumbs to upstream superrepo PRs`
* **Author:** `amd-hsivasun`
* **Head:** `users/hsivasun/breadcrumbs-bump-prs` at `c6b72ef60f656e590829b1352ef738ed3db8eea9`
* **Base:** `main` at `05e2e8b8943cb12c95594015c08846017b8bd54b`
* **Reviewed:** 2026-07-27
* **Commits:** 1

---

## Summary

The breadcrumb feature is useful, and the single-comment/newest-first-history
design avoids GitHub's fixed comment ordering. The implementation should not
merge yet: it queries TheRock with a submodule commit SHA, so the first real
API lookup fails before any breadcrumb is posted. The mock-heavy tests encode
that defect instead of detecting it, and the PR has no push-path or sandbox
repository validation.

**Net changes:** +1015 / -3 lines across 3 files.

---

## Overall Assessment

**CHANGES REQUESTED** - The live workflow path is broken, retries can corrupt
the history, and critical API/token behavior is absent from the tests.

### Strengths

- The motivation and intended user-visible behavior are clear.
- A single sticky comment with explicit newest-first history is a reasonable
  model for land/revert/re-land sequences.
- The pure comment-body tests exercise meaningful output behavior.
- Linux and Windows unit-test jobs, pre-commit, CodeQL, and the secret scan
  passed.

### Blocking issues

1. TheRock PR resolution uses the submodule gitlink SHA instead of the TheRock
   push SHA, causing the real API request to fail.
2. The orchestration tests mock the implementation and assert the incorrect
   SHA; no test or recorded experiment exercises the actual push/API path.
3. Re-running a workflow unconditionally appends the same event again, so the
   advertised history is not idempotent.
4. Revert/range API calls bypass the explicit GitHub App client and rely on the
   unauthenticated module singleton.

### Important issue

5. `post_breadcrumbs` is a push phase, not a GitHub event type, and its largely
   independent implementation adds 292 lines to an existing 472-line script.

---

## Detailed Review

### 1. BLOCKING: Resolve the bump PR from the TheRock push SHA

[`detect_changed_submodule()`](https://github.com/ROCm/TheRock/blob/c6b72ef60f656e590829b1352ef738ed3db8eea9/build_tools/github_actions/bump_automation.py#L127-L140)
returns `new_sha` as the new submodule gitlink target.
[`process_bump()`](https://github.com/ROCm/TheRock/blob/c6b72ef60f656e590829b1352ef738ed3db8eea9/build_tools/github_actions/bump_automation.py#L279-L307)
then passes that SHA to `resolve_therock_pr_number()`, which queries
`ROCm/TheRock/commits/{sha}/pulls`. A submodule commit is not a commit in
TheRock's object database.

I verified this against a recent real bump:

```text
TheRock push SHA:
  ROCm/TheRock/commits/82ca30cad815586a3338c54eac08e17378df3942/pulls
  -> ROCm/TheRock#6871

Submodule target SHA used by this PR:
  ROCm/TheRock/commits/44be71b52284948e58c93f65f46910399773fdcd/pulls
  -> HTTP 422: No commit found for SHA

The same submodule SHA in its actual repository:
  ROCm/rocm-systems/commits/44be71b52284948e58c93f65f46910399773fdcd/pulls
  -> ROCm/rocm-systems#8666
```

`handle_post_breadcrumbs()` receives the correct TheRock `after` SHA but
discards it when calling `process_bump()`. The resulting exception is hidden
at job level by `continue-on-error: true`, so this can leave the workflow green
without posting anything.

**Required action:** Carry both namespaces explicitly. Pass the TheRock
`after` SHA to `resolve_therock_pr_number()` and retain the old/new gitlink
SHAs only for submodule range analysis. Add a test that fails if these SHAs are
interchanged.

### 2. BLOCKING: Replace call-sequence tests with production-boundary tests

The purported end-to-end
[`ProcessBumpTest`](https://github.com/ROCm/TheRock/blob/c6b72ef60f656e590829b1352ef738ed3db8eea9/build_tools/github_actions/tests/bump_automation_test.py#L847-L939)
patches `GitHubAPI`, URL discovery, PR resolution, revert detection, commit
fetching, per-commit resolution, comment lookup, and comment update. It
therefore tests a handwritten call sequence, not the observable behavior of
the feature. Most importantly, line 898 explicitly requires
`resolve_therock_pr_number(changed["new_sha"], ...)`, locking in finding 1.

The dispatch tests have the same issue:
[`MainDispatchTest`](https://github.com/ROCm/TheRock/blob/c6b72ef60f656e590829b1352ef738ed3db8eea9/build_tools/github_actions/tests/bump_automation_test.py#L1137-L1170)
mocks the handler and includes a test that only verifies `argparse` rejects
missing required arguments. The small pure-output tests for timeline/comment
formatting are useful and should remain; the problem is concentrated in the
orchestration and CLI coverage.

All discovered PR workflow runs use `pull_request` or
`pull_request_target`. The new workflow step is gated to `push`, so none of
those runs execute it. The description records only unit-test commands and no
duration or sandbox/fork run. Passing unit tests therefore do not demonstrate
token scope, commit-to-PR resolution, comment creation/update, or rerun
behavior.

**Required action:** Mock only the HTTP boundary (and external clock), while
running real detection, SHA routing, range selection, comment construction,
and request planning together. Use a temporary git repository with real
gitlink changes or a small checked-in fixture. Remove tests of `argparse`
itself and redundant call-sequence cases. Before merge, record a successful
land/revert/re-land and rerun experiment against disposable repositories or a
fork/test organization, including links or captured request/result evidence.

### 3. BLOCKING: Make history updates idempotent

[`build_breadcrumb_body()`](https://github.com/ROCm/TheRock/blob/c6b72ef60f656e590829b1352ef738ed3db8eea9/build_tools/github_actions/bump_automation.py#L235-L258)
always prepends a new entry to the existing body. GitHub Actions jobs can be
re-run for the same push, so the same TheRock PR/action is then recorded twice.
A later rerun date can make one inclusion look like two distinct lifecycle
events. This contradicts the PR's goal of preserving an accurate ordered
history.

**Required action:** Give each event a stable identity (for example TheRock
push SHA plus action/submodule), store it in the comment, and replace or skip
an existing matching entry. Test first run, same-day rerun, later-day rerun,
and the intended land/revert/re-land sequence.

### 4. BLOCKING: Route every API call through the App-token client

`process_bump()` constructs an explicit `GitHubAPI(github_token=app_token)`,
but the imported
[`is_revert()` and `fetch_commits_in_range()` helpers](https://github.com/ROCm/TheRock/blob/c6b72ef60f656e590829b1352ef738ed3db8eea9/build_tools/generate_manifest_diff_report.py#L335-L400)
call the module-level `gha_send_request()` singleton. The
[`Post bump breadcrumbs`](https://github.com/ROCm/TheRock/blob/c6b72ef60f656e590829b1352ef738ed3db8eea9/.github/workflows/bump_submodules.yml#L90-L101)
step passes App tokens only as command arguments; it does not export
`GITHUB_TOKEN`. These range/revert reads therefore fall back to unauthenticated
requests in Actions and are subject to the low anonymous rate limit.

This directly contradicts the description's claim that one App-token client
is reused for every call. Because the step is `continue-on-error`, rate-limit
or API failures can again suppress the feature without failing the job.

**Required action:** Extend the shared helpers to accept a `GitHubAPI` client
and pass the same explicit App-token instance through every request. Add a
boundary test that rejects any request made through the default singleton.

### 5. IMPORTANT: Give breadcrumbs their own module and command

[`--event_type`](https://github.com/ROCm/TheRock/blob/c6b72ef60f656e590829b1352ef738ed3db8eea9/build_tools/github_actions/bump_automation.py#L724-L757)
previously selected actual workflow triggers, `schedule` and `push`.
`post_breadcrumbs` is not a third trigger; it is a second phase of `push`.
Modeling phases and triggers in the same enum obscures the command contract
and makes unrelated token/argument requirements global.

The change adds 292 source lines to a 472-line script and 708 test lines to its
test file. Most breadcrumb logic has a separate lifecycle and only needs a
small set of shared git/config helpers.

**Recommendation:** Move the feature to a focused module and preferably a
separate command such as `post_bump_breadcrumbs.py`. Extract the genuinely
shared submodule detection/config helpers to a small common module if needed.
The workflow can then invoke the breadcrumb command directly without diluting
`--event_type` or running unrelated global git configuration.

---

## PR Description and Test Evidence

The description is much longer than needed and narrates individual helper
calls and test implementation details already visible in the diff. Length
alone is not the main problem: two prominent claims are inaccurate—the
TheRock lookup does not receive `after_sha`, and not every request uses the
explicit client.

Condense it to the motivation, the single-comment history design, operational
failure policy, and concrete validation. Move the longer design history to the
linked issue. Add test duration and an actual sandbox/fork workflow result.

---

## CI Evidence

At head `c6b72ef...`:

- Ubuntu and Windows unit-test jobs passed.
- Pre-commit, CodeQL, Gitleaks, and the PR bot passed.
- Multi-Arch CI failed in the Windows gfx110X `Driver / GPU sanity check`
  before its test step. That appears unrelated to these Python/workflow files,
  but the aggregate CI result is still failed.
- No discovered run exercised the new `push`-gated breadcrumb step.

The passing unit tests do not offset finding 1 because the relevant test mocks
the API lookup and asserts the wrong SHA.

---

## Required Before Re-review

1. Preserve and use the TheRock push SHA for TheRock PR resolution.
2. Replace orchestration call-sequence tests with boundary-level behavior
   tests and record a real sandbox/fork run.
3. Make history updates idempotent across workflow reruns.
4. Pass the explicit App-token client through revert and commit-range helpers.
5. Extract the feature from `bump_automation.py` or provide a compelling
   module-boundary alternative.
6. Correct and shorten the PR description, including test duration and live
   validation evidence.

---

## Conclusion

**Approval Status: CHANGES REQUESTED**

The comment-history design is salvageable, but the current workflow cannot
reach it with real GitHub data. The fatal SHA mix-up is exactly the kind of
defect the current mock-heavy suite cannot detect.

*Review generated with Codex (OpenAI).*
