# Review: ROCm/rocm-libraries#10993

* **PR:** [ROCm/rocm-libraries#10993](https://github.com/ROCm/rocm-libraries/pull/10993)
* **Title:** `ci(therock): validate the merge-base TheRock ref against a real build`
* **Head:** `d7133a9bd75799991aed2eaab762932b6a78312c`
* **Base:** `develop`
* **Reviewed:** 2026-08-19
* **Scope:** Comprehensive review, with emphasis on dependency-baseline and CI architecture
* **State:** Draft discussion PR

---

## Summary

This is a useful interim-hardening direction, but the current implementation
does not yet establish the property it calls "build-validated." It selects the
newest TheRock workflow run whose overall conclusion is `success`; TheRock's
multi-arch workflow can conclude successfully while both platform build jobs
are skipped. That happened in this PR's own resolver run.

The durable solution remains frequently updated immutable pins produced from
repository synchronization history. This PR can still contribute worthwhile
interim improvements—particularly aligning the `configure` checkout with the
selected source ref, release-branch awareness, and explicit fallback status—if
the health signal is corrected and the dynamic mechanism is not presented as a
replacement for bump-derived pins.

**Net changes:** 421 additions and 71 deletions across three files.

---

## Overall Assessment

**CHANGES REQUESTED**

One blocking correctness issue must be fixed before this is used as a merge
candidate: a no-op workflow success is currently reported as proof that the
selected stack built and passed.

The long-term architecture should prioritize reliable, frequent pin updates.
After the blocker is fixed, this resolver can be a reasonable interim safety
layer or diagnostic fallback, but it still uses wall-clock selection and does
not prove the caller-gitlink relationship discussed in reviews of #9602 and
TheRock #7197.

---

## Findings

### BLOCKING: A successful workflow conclusion does not prove that the selected stack built

[`list_successful_workflow_runs()`](https://github.com/ROCm/rocm-libraries/blob/d7133a9bd75799991aed2eaab762932b6a78312c/.github/scripts/resolve_therock_ref.py#L208-L253)
filters `multi_arch_ci.yml` runs by `status=success` and returns their head
commits. [`resolve_ref()`](https://github.com/ROCm/rocm-libraries/blob/d7133a9bd75799991aed2eaab762932b6a78312c/.github/scripts/resolve_therock_ref.py#L298-L353)
accepts the first result without fetching its jobs or artifacts, and the
summary then states that TheRock's multi-arch CI
[`"ran and passed against this exact commit"`](https://github.com/ROCm/rocm-libraries/blob/d7133a9bd75799991aed2eaab762932b6a78312c/.github/scripts/resolve_therock_ref.py#L461-L470).

The PR's own run disproves that implication:

| Evidence | Value |
|---|---|
| rocm-libraries merge base | `a79ccdca` at 2026-08-19 00:32:54 UTC |
| Resolver-selected TheRock commit | `39bfc3f5` |
| Selected TheRock workflow run | [32181626394](https://github.com/ROCm/TheRock/actions/runs/32181626394), conclusion `success` |
| Jobs that ran | setup, manifest diff, CI summary |
| Platform build jobs | `Linux::skip`, `Windows::skip` |
| Result reported by resolver | `build-validated` |

The selected commit was a CODEOWNERS-only change, so the workflow's change
selection intentionally skipped the builds. The workflow-level green result is
real, but it is not evidence that the source stack at that SHA was built.

The distinction matters in this exact selection. The merge base records
TheRock `48ec94d7`, while the dynamic resolver advanced 21 TheRock commits to
`39bfc3f5`:

```text
                         recorded pin 48ec94d7    selected 39bfc3f5
rocm-libraries gitlink      962d0059                  962d0059
rocm-systems gitlink        af82d0ab                  ef3b1473
amd-llvm gitlink            ba9267ae                  0bace190
```

The resolver therefore changed the rocm-systems and LLVM baseline based on a
workflow run in which neither platform was built. This is the failure mode the
new validation is supposed to prevent.

The docstring also says this reuses the same signal as TheRock's
[`baseline_runs.py`](https://github.com/ROCm/TheRock/blob/691329a44615664d59a599093014c84074e1477c/build_tools/github_actions/baseline_runs.py#L682-L826),
but that implementation goes further: it queries jobs, requires named build
jobs to have completed successfully, and verifies required artifacts. The new
resolver currently reuses only the run-list query.

**Required action:** Make the validation predicate explicit and inspect it.
At minimum:

1. Retain the workflow run ID/URL with each candidate.
2. Query its jobs and require the intended Linux/Windows build gates to be
   present and successful; reject skipped or missing build gates.
3. If a no-op commit is allowed to inherit validation, prove that its complete
   relevant stack identity matches an earlier run with healthy required jobs
   and artifacts.
4. Add regression tests where an overall-success run with skipped build jobs is
   rejected and a run with the required successful jobs is accepted.
5. Do not label a fallback or no-op run `validated`.

Reusing a shared TheRock helper would be preferable to creating another subtly
different definition of workflow health.

### IMPORTANT: Release source selection remains paired with live `main` workflow definitions

The PR maps a `release/therock-*` rocm-libraries base branch to the matching
TheRock source branch, but the caller still loads setup, Linux, and Windows
reusable workflows from literal
[`@main` refs](https://github.com/ROCm/rocm-libraries/blob/d7133a9bd75799991aed2eaab762932b6a78312c/.github/workflows/therock-multi-arch-ci.yml#L184-L246).

That means a release PR would deliberately combine:

```text
workflow definitions W = TheRock main
source and build_tools T = TheRock release/therock-X.Y
```

The PR documents the limitation, but documentation does not make that
cross-release interface safe. In the current develop-branch run, GitHub loaded
reusable workflows at `691329a4` while the resolver selected source
`39bfc3f5`, 14 TheRock commits earlier. Workflow files changed between those
two commits. A release/main split can be substantially wider.

**Recommendation:** Do not enable release-branch source mapping independently
of the workflow-definition policy. Each rocm-libraries release branch can carry
immutable literal `uses: ...@<SHA>` refs updated by bump automation. If that is
not ready, remove the release mapping from this interim PR rather than claiming
release coherence while retaining workflows from `main`.

### IMPORTANT: The new decision is still not auditable from live logs

The [resolver job in run 32292598626](https://github.com/ROCm/rocm-libraries/actions/runs/32292598626/job/96197006537)
logged its base/head/branch inputs and only this decision output:

```text
{'therock_ref': '39bfc3f5705eee7c0cce7d05cb39e087e7d6a068'}
```

It did not log the discovered merge base, timestamp cutoff, workflow runs
considered, selected run ID, job-health evidence, rejected candidates, fallback
reason, or workflow-definition SHA. The step summary cannot replace live
logging when API lookup or summary generation fails, and the current `Commit`
model discards the run ID needed to audit the claimed validation.

**Recommendation:** Emit structured INFO logs as each decision is made. Include
`M`, target branch, every candidate run ID/SHA/time, required-job results,
selection or rejection reason, final `T`, and whether a fallback was used. Also
record the resolved workflow-definition SHA from run provenance when reviewing
the result. Never log the token.

### FUTURE WORK: Make bump-derived immutable pins the primary mechanism

The dynamic health check improves on accepting an arbitrary nearby commit only
after its predicate is corrected. It still does not answer the central graph
question: which TheRock stack was recorded and validated through repository
synchronization for this rocm-libraries history?

At this PR's merge base, `.github/actions/ci-env/action.yml` already records
TheRock `48ec94d7` and baseline run `32050763862`. That is durable state in git
history. The automation should be strengthened so narrow back-reference PRs:

- arrive promptly after a TheRock submodule bump is accepted;
- record an exact TheRock commit and matching validation run/gates;
- atomically update literal reusable-workflow refs and source/script refs;
- verify the TheRock `rocm-libraries` gitlink is equal to or an ancestor of the
  destination history;
- auto-approve and auto-merge when the diff and evidence match policy; and
- alert the developer rotation when freshness exceeds an SLA.

That removes wall-clock inference, keeps unchanged PRs stable, and uses the git
history that actually represents synchronization. The dynamic resolver can
then serve as a diagnostic or explicitly labeled fallback rather than the
source of truth.

---

## What This PR Improves

Subject to the blocking health-predicate correction, these changes are useful:

- The `configure` job now checks out its script from the same selected source
  SHA instead of independently resolving `main`.
- `actions: read` is correctly scoped to the resolver job.
- The summary distinguishes validated and unvalidated modes instead of silently
  claiming the fallback is equivalent.
- The release-branch mapping logic is small and well tested, though it should
  ship only with a compatible workflow-definition policy.
- API query volume is modest for the current implementation.
- No secrets are exposed, and the added permissions are read-only.

---

## Tests and CI Evidence

- The PR reports 21 local resolver tests passing. The new unit tests cover the
  branch mapper and success/fallback control flow, but their `healthy_commits`
  fake assumes that a successful run is healthy; it cannot catch the skipped
  build-job bug above.
- `pre-commit`, `therock-pr-bot`, the resolver job, configure job, and setup job
  passed at review time.
- The full multi-arch run was still active, with Linux and Windows prebuilt-stage
  copy jobs queued. Its workflow definitions resolved to TheRock `691329a4`
  while its source ref resolved to `39bfc3f5`.
- Live API queries verified that `status=success` filters workflow conclusions
  correctly; the defect is the meaning of a successful top-level conclusion,
  not the REST filter syntax.
- Tests were not rerun locally from the PR checkout during this review.

---

## Alternatives Considered

### 1. Frequently bumped immutable pins — recommended primary design

This preserves the causal synchronization edge in repository history and can
pin both workflow/control-plane code and the source stack. Its current weakness
is operational lag, which should be addressed through scoped auto-merge and an
owner/SLA rather than by discarding the mapping.

### 2. Dynamic successful-run selection — acceptable interim defense after correction

This can avoid obviously broken commits and improve current active CI without
waiting for the automation redesign. It must validate required jobs/artifacts,
log its evidence, and remain explicitly secondary because time and workflow
success do not prove the caller-gitlink relationship.

### 3. Fail closed when no validated candidate exists

This provides the strongest semantics but can stop all PR CI during TheRock
outages. A temporary fail-open mode can be reasonable operationally if it emits
a visible annotation/metric, never calls the result validated, and has an
expiration/owner. A step-summary warning alone is too easy to miss.

### 4. Inline or duplicate TheRock workflows in every caller

This could avoid GitHub's literal reusable-workflow ref constraint, but it
would create substantial duplication and drift. Immutable literal refs updated
by automation are simpler and preserve TheRock as the workflow owner.

---

## Conclusion

The high-level split is sound: invest in reliable, frequently updated pins as
the real solution, and accept narrowly scoped robustness improvements while the
current resolver remains active. This PR is not ready to be that interim
improvement until it stops equating a no-op green workflow with a built and
tested stack. Fix that predicate, make the evidence auditable, and avoid
introducing release/main workflow-source skew; the remaining timestamp and
fallback limitations can then be tracked as migration debt toward pinned
baselines.

---

*Review generated with OpenAI Codex.*
