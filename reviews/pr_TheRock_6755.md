# PR Re-review: ROCm/TheRock #6755

* **PR:** [ROCm/TheRock#6755](https://github.com/ROCm/TheRock/pull/6755)
* **Title:** `ci(bump-submodules): Post bump breadcrumbs to upstream superrepo PRs`
* **Author:** `amd-hsivasun`
* **Head:** `users/hsivasun/breadcrumbs-bump-prs` at `135d8d12e6f8f00d71bafe8a14ded1e5776c32d5`
* **Base:** `main` at `ea8aec5ebb3b614bfb901f8439c64257733a1250`
* **Reviewed:** 2026-08-25
* **Commits:** 7
* **Focus:** PR targeting and timing, test evidence, and generated-comment clarity

---

## Summary

The current revision fixes the four functional blockers from the 2026-07-27
review. It now resolves the TheRock PR from the TheRock push SHA, routes range
queries through the explicit App-token client, gives reruns a stable event
identity, and isolates the feature in `post_bump_breadcrumbs.py`. The author
also supplied strong live evidence: real GitHub data for large land/revert
ranges, real Actions runs, a real cross-repository comment, an idempotent
rerun, a revert update, and an unmapped-commit summary.

One correctness issue remains. The visible event date and the promised
newest-first ordering are derived from processing time and insertion order,
not from the bump event. A delayed retry can therefore give an old bump the
retry date and place it above a newer bump.

**Net changes:** +820 / -5 lines across 4 files.

---

## Overall Assessment

**CHANGES REQUESTED** - Normal first-attempt land and revert processing now
targets the right PRs with the right action, but delayed recovery can produce
an incorrect timeline.

### Strengths

- TheRock and submodule SHA namespaces are now explicit and correctly routed.
- The same App-token-bound client is passed through PR resolution, revert
  detection, range fetching, comment lookup, and comment update calls.
- Land, revert, fanout, unmapped-commit, and same-event rerun behavior have
  direct tests and live GitHub evidence.
- The generated upstream comment is short, readable, and links directly to the
  TheRock bump PR.
- The implementation is now in a focused script instead of extending the
  existing bump-automation command with a non-event phase.

### Blocking issue

1. Delayed or out-of-order retries misdate and misorder timeline entries.

---

## Detailed Finding

### BLOCKING: Use the bump event time and sort history by that time

[`process_bump()`](https://github.com/ROCm/TheRock/blob/135d8d12e6f8f00d71bafe8a14ded1e5776c32d5/build_tools/github_actions/post_bump_breadcrumbs.py#L263-L304)
sets `event_date` from `datetime.now(timezone.utc)` when the job attempt runs.
[`build_breadcrumb_body()`](https://github.com/ROCm/TheRock/blob/135d8d12e6f8f00d71bafe8a14ded1e5776c32d5/build_tools/github_actions/post_bump_breadcrumbs.py#L180-L194)
then unconditionally prepends that entry while labeling the list “Newest
first.” Neither value is tied to the `therock_after_sha` that identifies the
actual bump event.

This fails in the recovery path the stable event key is intended to support:

1. Bump A lands on August 18, but its breadcrumb step fails before posting.
2. Bump B lands on August 19 and posts successfully.
3. Bump A's workflow is rerun on August 20.
4. The comment records A as August 20 and prepends it above B, even though A
   landed first.

I also reproduced the ordering directly against the current head: inserting
an August 18 event after an existing August 19 event emitted August 18 first.

The problem can also occur across midnight on an initial queued run. The
current same-day live rerun proves duplicate suppression, but it cannot expose
the wrong-date or out-of-order behavior. The unit test at
[`test_new_entry_is_prepended_above_prior_history`](https://github.com/ROCm/TheRock/blob/135d8d12e6f8f00d71bafe8a14ded1e5776c32d5/build_tools/github_actions/tests/post_bump_breadcrumbs_test.py#L82-L110)
only supplies chronologically increasing dates, so it encodes insertion order
as chronology.

**Required action:** Derive a stable event timestamp from the TheRock push
commit (or pass the push event timestamp), retain a sortable timestamp in each
history entry, and order entries by event time rather than attempt time. Add
tests for a next-day retry and for processing an older failed event after a
newer successful event.

---

## Behavior Review

### Does it comment on the correct PR?

**Yes for the tested normal and revert paths.** The workflow passes
`github.event.before` and `github.sha` to the dedicated script. The script uses
the TheRock `after` SHA only to resolve the TheRock bump PR, and separately
derives old/new submodule SHAs for upstream range traversal. Each upstream
commit is resolved in its own repository and the resulting PR numbers are
deduplicated before posting.

Evidence checked:

- A real 145-commit `rocm-systems` land range mapped all 145 commits to 97
  unique upstream PRs and linked TheRock #7408.
- A real 169-commit revert range mapped all 169 commits to 142 unique upstream
  PRs, swapped the traversal direction, and linked TheRock #4222.
- The live write run posted to the disposable upstream PR
  [rocm-systems#10296](https://github.com/ROCm/rocm-systems/pull/10296#issuecomment-5324051112)
  and linked TheRock #6755.
- An unmapped commit produced a summary on
  [TheRock#6755](https://github.com/ROCm/TheRock/pull/6755#issuecomment-5324136431),
  not on an unrelated upstream PR.

### Does it post at the correct time?

**Yes on the ordinary path, but not reliably on delayed recovery.** The
production step is gated to a `push` to `main` that changes one of the watched
gitlinks, so the first attempt runs after the bump reaches TheRock. The
remaining blocker is that a later retry presents its execution time as the
bump time and always inserts at the top.

The step is still `continue-on-error: true`, so a transient failure does not
block the bump workflow. The script now raises after attempting every changed
submodule, making the failed step visible even though the job is allowed to
continue.

---

## Test Review

The feature has been tested much more thoroughly than in the earlier revision.

### Verified evidence

- I independently ran the current head's targeted suite with TheRock's venv:

  ```text
  D:/projects/TheRock/.venv/Scripts/python.exe -m pytest
    --override-ini=cache_dir=D:/scratch/codex/pytest-cache/TheRock-pr-6755
    github_actions/tests/post_bump_breadcrumbs_test.py
    github_actions/tests/bump_automation_test.py -q

  49 passed
  ```

- Current-head Unit Tests passed on both Ubuntu 24.04 and Windows 2022. The
  Ubuntu job reported 64.12% statement coverage for the new script; the full
  build-tools suite reported 1,837 passed, 50 skipped, and 122 subtests passed
  in 70.33 seconds.
- [Land/write run 32103278996](https://github.com/ROCm/TheRock/actions/runs/32103278996)
  posted the real upstream comment.
- [Rerun 32103534414](https://github.com/ROCm/TheRock/actions/runs/32103534414)
  detected the same event key and left the comment unchanged.
- [Revert/write run 32103812222](https://github.com/ROCm/TheRock/actions/runs/32103812222)
  prepended a revert entry to the same comment.
- [Unmapped run 32104050776](https://github.com/ROCm/TheRock/actions/runs/32104050776)
  posted the summary to the TheRock PR.
- Dry runs covered large real ranges plus `rocm-libraries` and `rocgdb` API
  routing.

### Remaining coverage limitation

The live writes ran against an earlier test commit before the final comment
heading and multi-submodule error/summary changes. Current-head unit CI covers
those changes, but the live sequence was chronological and same-day. There is
no test for a delayed first success or out-of-order recovery, which is why the
remaining finding escaped both the mocks and the live exercise.

The current Multi-Arch CI aggregate is red, but the failures inspected are in
unrelated GPU/package tests: a rocprofiler-sdk timeout, missing hipBLASLt files
in a Windows devel-wheel assertion, and a rocFFT test failure. The focused
Ubuntu/Windows unit checks, pre-commit, CodeQL, and policy checks passed.

---

## Generated Comment Review

The current code generates an upstream comment with this visible Markdown
(the HTML event IDs are hidden by GitHub):

```markdown
### TheRock Submodule Bump Activity
_Newest first_

- **2026-08-20** — Reverted out of TheRock via [ROCm/TheRock#4222](https://github.com/ROCm/TheRock/pull/4222).
- **2026-08-18** — Included in TheRock via [ROCm/TheRock#7408](https://github.com/ROCm/TheRock/pull/7408).
```

This is understandable enough. It answers the useful questions quickly: what
happened, when, and which TheRock PR caused it. Keeping one sticky comment also
prevents repeated comments from cluttering the PR timeline, though each update
can still generate notifications.

The actual live comment linked above has the earlier heading “TheRock
submodule-bump history (newest first)”; the final revision changed only the
heading. The final heading has unit coverage and is clearer, but has not itself
been shown in a real posted comment.

The unmapped summary is also understandable, but `1 commit(s)` is mechanical.
Handling singular/plural would be a small optional polish.

---

## Required Before Approval

1. Make event dates stable and tied to the TheRock bump, not the workflow
   attempt.
2. Sort history by event time and test delayed/out-of-order retries.

---

## Conclusion

**Approval Status: CHANGES REQUESTED**

The PR now demonstrates correct repository/PR routing and useful, readable
comment output on the normal path. Fixing event-time ordering should be small,
but it is necessary for the sticky timeline to remain truthful when the
best-effort workflow is retried after a failure.

*Review generated with Codex (OpenAI).*
