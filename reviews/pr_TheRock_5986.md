# PR Review: ROCm/TheRock#5986

* **PR:** https://github.com/ROCm/TheRock/pull/5986
* **Title:** `feat(Quartz): notify_quartz reusable workflow + dispatcher`
* **Author:** `HereThereBeDragons`
* **Branch:** `users/lpromber/notify_quartz`
* **Base:** `main`
* **Reviewed:** 2026-07-14
* **Head SHA:** `a766b8db3b878c64b351a9d737467b3b85f9c532`
* **Net changes:** +947 / -0 across 3 files

---

## Summary

This PR adds a reusable workflow and Python dispatcher for reporting TheRock
workflow status to Quartz. The dispatcher reads the current Actions run, adds
caller-supplied inputs and outputs, and dispatches a started or completed
payload to a configurable workflow in `ROCm/Quartz`.

The implementation is not active in existing workflows yet, but several
problems in the interface would produce over-privileged dispatch credentials or
incorrect data once the follow-up caller changes land.

## Overall Assessment

**CHANGES REQUESTED** - The payload builder attributes the full top-level run's
job list to each nested reusable workflow, silently publishes an empty job list
when the Actions API fails, and does not validate the environment-backed
lifecycle values used by the reusable workflow. The required PR policy check is
also failing on the title.

## Findings

### IMPORTANT: Constrain the production dispatch target and token permissions

[`notify_quartz.yml`](https://github.com/ROCm/TheRock/blob/a766b8db3b878c64b351a9d737467b3b85f9c532/.github/workflows/notify_quartz.yml#L53-L82)
accepts `quartz_repo`, `quartz_workflow_file`, and `quartz_workflow_ref` from
the caller, then creates a GitHub App token with `owner: ROCm` but no
`repositories` or `permission-*` restrictions. The pinned action documents
that `owner` without `repositories` scopes the token to every repository in the
owner's App installation, while omitted permission inputs inherit all
installation permissions ([action documentation](https://github.com/actions/create-github-app-token/blob/bcd2ba49218906704ab6c1aa796996da409d3eb1/README.md#repositories)).
The script then uses the caller's three values directly in the dispatch
endpoint ([`notify_quartz.py`](https://github.com/ROCm/TheRock/blob/a766b8db3b878c64b351a9d737467b3b85f9c532/build_tools/github_actions/notify_quartz.py#L519-L524)).

The Hauly installation is already restricted to a narrow repository set, so an
additional `repositories:` input is not necessary if that set is exactly the
intended source and target repositories. The remaining concern is defense
against accidental misuse: the production reusable workflow can dispatch any
workflow/ref reachable within that installation, and the token inherits every
permission granted to the installation rather than requesting only the
permission this job uses.

**Recommendation:** Document the installation's repository and permission
scope. Hardcode or allowlist the production target (`ROCm/Quartz`,
`receive_therock_data.yml`, `main`) unless caller overrides are an intentional
supported contract. Request only the required token permissions where the App
grants more than `actions`, and keep broader development overrides in a
separate controlled path.

### BLOCKING: Every leaf report is populated with the entire top-level run's jobs

[`_build_payload()`](https://github.com/ROCm/TheRock/blob/a766b8db3b878c64b351a9d737467b3b85f9c532/build_tools/github_actions/notify_quartz.py#L379-L460)
correctly notes that nested reusable workflows share the top-level
`GITHUB_RUN_ID`. It nevertheless calls `_fetch_jobs()` with that shared ID,
which returns every job in the top-level release run, and then only overrides
`workflow_run.path` to make the payload look like it belongs to the reporting
leaf. No job is filtered or otherwise associated with that leaf.

Once the planned callers notify at the beginning and end of each reusable
workflow, each leaf will therefore send the same run-wide job set under a
different path. Completed leaf notifications can also include still-running
sibling jobs. If the payload exceeds the dispatch limit, Quartz is instructed
to re-fetch by the same shared run ID, reproducing the same ambiguity. This
duplicates data and assigns jobs to workflows that did not run them; retaining
the same run ID while changing the path may also collide if the receiver keys a
workflow-run row by run ID, as the RFC describes.

**Required action:** Define and test a stable data model before adding callers.
Either send the run-wide job array exactly once from the top-level workflow, or
introduce a reliable leaf identity and filter/associate jobs before labeling a
payload with a leaf path. Verify the receiver's uniqueness key for multiple
records that share a GitHub run ID. Add an integration fixture with at least
two nested reusable workflows and prove that each stored job is attributed
once to the intended workflow.

### BLOCKING: An Actions API failure is stored as a successful empty job list

[`_fetch_jobs()`](https://github.com/ROCm/TheRock/blob/a766b8db3b878c64b351a9d737467b3b85f9c532/build_tools/github_actions/notify_quartz.py#L220-L242)
catches API, JSON, and shape failures, logs a warning, and returns `[]`.
`dispatch_to_quartz()` only sets `fetch_jobs=true` when payload size forces it
to remove jobs, so this error path sends `jobs: []` with `fetch_jobs=false`.
Quartz cannot distinguish "the run had no jobs" from "TheRock failed to read
the jobs," and it will persist incomplete data instead of retrying.

The outer reusable job already has `continue-on-error: true`, so failing the
reporting attempt will not fail the caller. Swallowing this exception only
turns an observable telemetry failure into silent data corruption.

**Required action:** Propagate the failure as `_DispatchConfigError`, or return
an explicit fetch-failed state that removes `jobs` and sets `fetch_jobs=true`.
Add a test that injects an `HTTPError` and verifies that an empty authoritative
job list is never dispatched.

### BLOCKING: Lifecycle values passed through environment defaults bypass validation

The reusable workflow supplies `RUN_PHASE` and `RUN_CONCLUSION` as environment
variables ([workflow lines 84-94](https://github.com/ROCm/TheRock/blob/a766b8db3b878c64b351a9d737467b3b85f9c532/.github/workflows/notify_quartz.yml#L83-L94)).
The parser puts those values in `default=` while declaring `choices` only for
`--run-phase`
([parser lines 580-597](https://github.com/ROCm/TheRock/blob/a766b8db3b878c64b351a9d737467b3b85f9c532/build_tools/github_actions/notify_quartz.py#L580-L597)).
Argparse does not validate an environment-derived default against `choices`.
Locally, `RUN_PHASE=bogus` and `RUN_CONCLUSION=banana` parsed unchanged; because
`_build_payload()` treats every phase other than `started` as completed, that
typo would publish a completed row with conclusion `banana`.

The derived path has a related hole:
[`_derive_run_conclusion_from_captured_outputs()`](https://github.com/ROCm/TheRock/blob/a766b8db3b878c64b351a9d737467b3b85f9c532/build_tools/github_actions/notify_quartz.py#L614-L664)
returns `success` for `success + timed_out` and `skipped` for `timed_out` alone,
despite the CLI help promising that unknown results fail closed.

**Required action:** Validate normalized phase and conclusion values explicitly
after parsing, fail closed on unknown `needs.*.result` values, and add table
tests for every accepted value plus unknown, null, mixed, and malformed input.

### BLOCKING: The required PR policy check rejects the title

The `therock-pr-bot` check failed because the uppercase scope in
`feat(Quartz): ...` does not satisfy the repository's Conventional Commits
policy. The bot has marked the PR not ready for review.

**Required action:** Rename the PR using an accepted scope, for example
`feat(quartz): add reusable notification workflow and dispatcher`, and rerun
the policy check.

### IMPORTANT: The dispatcher logs the complete caller-supplied payload

[`main()`](https://github.com/ROCm/TheRock/blob/a766b8db3b878c64b351a9d737467b3b85f9c532/build_tools/github_actions/notify_quartz.py#L739-L740)
logs the full pretty-printed payload, including `workflow_inputs` and every
captured job output. The workflow documentation warns callers not to pass
secrets, but logging all values creates another exposure surface for signed
URLs, credentials derived from secrets, or other sensitive outputs that are
not covered by GitHub's exact-value masking.

**Recommendation:** Log identifiers, field names, counts, and serialized sizes,
not the payload values. If full payload logging is needed for development,
gate it behind an explicit debug option that is disabled in the reusable
production workflow.

## Test Coverage

The six added tests pass, but
[`notify_quartz_test.py`](https://github.com/ROCm/TheRock/blob/a766b8db3b878c64b351a9d737467b3b85f9c532/build_tools/github_actions/tests/notify_quartz_test.py#L18-L88)
only covers reporting-path normalization and override. It does not exercise
pagination, API failures, payload-size fallback, dispatch construction,
lifecycle validation/derivation, actor/job normalization, or `main()` error
paths. For a new 761-line dispatcher that handles credentials and cross-repo
data ingestion, these are critical behavioral paths rather than optional
coverage.

In addition to the focused tests required by the findings, provide an
end-to-end test-run link showing both started and completed dispatches from a
nested reusable workflow to the intended test receiver. The PR body currently
states that the files are standalone but does not provide runtime evidence for
the new `workflow_call` path.

## CI Evidence

* `Unit Tests :: ubuntu-24.04`, `Unit Tests :: windows-2022`, pre-commit,
  action/python analysis, CodeQL, and gitleaks passed on head `a766b8d`.
* `therock-pr-bot` failed on the title policy described above.
* The Linux gfx942 math-libs build and Windows `libhipcxx_hipcc` test failed.
  The changed files are not active in this CI run, so these failures do not
  originate from this PR. The Windows log shows `offload-arch.exe` returned no
  architecture and CMake was invoked with `--offload-arch=None`.
* The overall `CI Summary` failed because of the failing build/test jobs.

## Local Verification

Ran the added tests from a scratch copy of the PR head with TheRock's venv
Python:

```powershell
D:\projects\TheRock\.venv\Scripts\python.exe -m unittest discover `
  -s D:\scratch\codex\pr5986\tests -p "*_test.py" -v
```

Result: `6 tests passed` in `0.001s`.

Also exercised the parser and conclusion helper directly. Environment defaults
`RUN_PHASE=bogus` and `RUN_CONCLUSION=banana` were accepted unchanged;
`success + timed_out` derived `success`, and `timed_out` alone derived
`skipped`.

## Conclusion

**Approval Status: CHANGES REQUESTED**

Resolve the job-attribution model before this becomes a shared workflow
contract. Then make the reporting paths fail fast, validate lifecycle values,
cover the core behavior with tests, and fix the required title check. Constrain
and document the production dispatch target as appropriate for the Hauly
installation's existing scope.

Generated by Codex.
