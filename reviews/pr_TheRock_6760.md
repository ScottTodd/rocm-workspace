# PR Review: ROCm/TheRock #6760

* **PR:** [#6760 — feat: Add stage reuse planning and CI impact reporting](https://github.com/ROCm/TheRock/pull/6760)
* **Head reviewed:** `1a7d740bbaa2126e70ca948865fdf375eb93d211`
* **Base:** `main` at `4cc263bfa7b91e33fce1423104a7c586512a5a4e`
* **Reviewed:** 2026-07-29
* **Change size:** +3,665 / -473 across 20 files and 19 commits

## Summary

This PR expands the stage-reuse prototype with exact diff-base provenance,
platform-aware artifact validation, report-only test impact, external-repository
source reporting, and per-job timing artifacts. The conservative exact-SHA
baseline rule is sound, and the changed focused Python suites pass locally.
The change is nevertheless not ready to merge because the merge-affecting
workflow paths have not been exercised end-to-end and the latest current-head
Multi-Arch run is still in progress.

## Readiness level

**Substantial CI architecture change with incomplete integration validation.**
This is beyond style cleanup: it modifies automatic stage reuse and two reusable
workflows, and adds new reporting/telemetry systems. The unit-level design is
well covered, but the evidence needed to validate artifact copying, reusable
workflow triggers, permissions, and external-repository behavior is not yet
present.

## Priority / urgency

**Medium priority optimization; not a release blocker.** It advances #3399 and
#6752 and may shorten routine bump CI once proven, but defaults remain
conservative (`dry-run`) and test impact is report-only. Nothing in the PR
identifies a release bug that requires taking this large change urgently.
Correctness and measured reuse rates should take precedence over landing it
quickly.

## Overall assessment

**CHANGES REQUESTED**

## Findings

### ❌ BLOCKING: The workflow paths that can change build behavior have not been validated end-to-end

[`multi_arch_ci.yml`](https://github.com/ROCm/TheRock/blob/1a7d740bbaa2126e70ca948865fdf375eb93d211/.github/workflows/multi_arch_ci.yml#L20)
exposes `workflow_dispatch` inputs including `reuse-stage`, while
[`setup_multi_arch.yml`](https://github.com/ROCm/TheRock/blob/1a7d740bbaa2126e70ca948865fdf375eb93d211/.github/workflows/setup_multi_arch.yml#L18)
is a reusable `workflow_call` used by normal and external-repository CI. The
actual `reuse-stage` path changes `prebuilt_stages` and `baseline_run_id`, which
causes downstream jobs to skip builds and copy artifacts.

The PR description lists pytest and actionlint commands but says only that
"Full CI validation is in progress." It provides no successful linked run for:

* `workflow_dispatch` with `reuse-stage`, including proof that the exact
  diff-base baseline was selected and every skipped stage was copied;
* a reusable external-repository call that exercises the source/ref summary and
  cross-repository guardrails;
* failure/fallback cases with unavailable artifacts;
* the final timing upload on a completed workflow.

The latest current-head
[Multi-Arch CI run 30468666174](https://github.com/ROCm/TheRock/actions/runs/30468666174)
was still in progress when reviewed, and its pull-request/default
`dry-run` path cannot validate actual stage reuse. Per the workspace workflow
review policy, each modified trigger/behavioral path needs CI evidence.

**Required action:** provide successful end-to-end runs for the dispatch,
reusable-workflow/external-repo, dry-run, and `reuse-stage` paths. Verify the
selected exact baseline SHA, copied artifact inventory, rebuilt stages,
fallback behavior, impact summary, timing JSON/Markdown, and final workflow
status.

### ⚠️ IMPORTANT: Mandatory timing collection couples optional telemetry to CI success

[`workflow_summary.py`](https://github.com/ROCm/TheRock/blob/1a7d740bbaa2126e70ca948865fdf375eb93d211/build_tools/github_actions/workflow_summary.py#L260)
performs live Actions API collection before reporting required job results, and
any HTTP, parsing, or formatting error propagates out of the summary step.
[`multi_arch_ci.yml`](https://github.com/ROCm/TheRock/blob/1a7d740bbaa2126e70ca948865fdf375eb93d211/.github/workflows/multi_arch_ci.yml#L175)
enables this unconditionally, making a data-collection prototype a new
dependency of every CI run. Review discussion also raised the alternative of
polling this data externally.

This broadens the failure surface for a feature that does not build or test the
change. It also contributes several hundred lines and a dependency from
`workflow_timing.py` into the stage-reuse/baseline module solely to share a
duration helper.

**Recommendation:** split raw timing collection into a separate workflow or
external collector, or make its failure semantics explicitly opt-in while the
prototype is evaluated. Keep the existing summary's build/test verdict
independent from telemetry availability.

### ⚠️ IMPORTANT: Invalid timestamps are converted into plausible zero-duration data

[`seconds_between()`](https://github.com/ROCm/TheRock/blob/1a7d740bbaa2126e70ca948865fdf375eb93d211/build_tools/github_actions/baseline_runs.py#L546)
now clamps negative durations to `0.0`. The new timing collector reuses this
helper. An out-of-order API timestamp is invalid/unknown data, not evidence that
queue or execution time was zero; the resulting JSON can therefore bias the
savings analysis the PR is intended to enable.

**Recommendation:** preserve `None` (or an explicit invalid-data status) for
negative/out-of-order timestamps and report that state distinctly in Markdown
and JSON.

### ⚠️ IMPORTANT: The PR is too broad to validate and roll out safely as one change

The 4,138-line diff spans automatic reuse semantics, baseline selection,
test-impact modeling, workflow summaries, external-repo auditing, and timing
collection. These features have different rollout and failure characteristics:
exact-SHA reuse is correctness-critical; test impact is report-only; source
reporting is diagnostic; timing can be collected independently.

The scope also makes CI evidence ambiguous—one run cannot isolate whether a
failure comes from artifact reuse, impact reporting, the external signal, or
telemetry.

**Recommendation:** at minimum separate timing collection and external source
reporting from the exact-baseline/stage-reuse correctness change. Land the
report-only test-impact work independently if it is not required by reuse. See
the concrete split proposal below.

### 💡 SUGGESTION: Do not silently discard the impact report job

[`setup_multi_arch.yml`](https://github.com/ROCm/TheRock/blob/1a7d740bbaa2126e70ca948865fdf375eb93d211/.github/workflows/setup_multi_arch.yml#L228)
runs the CI impact report as a separate job with `continue-on-error: true`.
If report rendering or output propagation breaks, the workflow remains green
and the feature can disappear unnoticed.

Consider appending the already-computed report in the setup job, or add a small
validation check for the report output while this feature is under evaluation.

## Suggested PR split

The primary recommendation is a three-PR split. This is a reasonable compromise
between reviewability and the overhead of managing a long stack: it keeps code
that changes build behavior separate from report-only diagnostics and from
Actions API telemetry.

### Recommended: three PRs

#### PR 1: Automatic stage reuse safety and execution

This PR should contain the complete behavior-changing stage-reuse feature:

* exact diff-base SHA validation and baseline health checks;
* platform/family artifact applicability and availability checks;
* the pure stage-reuse planner and its conservative fallbacks;
* manual-versus-automatic reuse precedence;
* `dry-run` and `reuse-stage` configuration;
* the `configure_multi_arch_ci.py`, `multi_arch_ci.yml`, and
  `setup_multi_arch.yml` hunks required to apply the decision.

Likely files include:

* `build_tools/github_actions/baseline_runs.py`
* `build_tools/github_actions/stage_reuse_decision.py`
* `build_tools/_therock_utils/build_topology.py`
* the stage-reuse portions of
  `build_tools/github_actions/configure_multi_arch_ci.py`
* the stage-reuse inputs and propagation in
  `.github/workflows/multi_arch_ci.yml` and
  `.github/workflows/setup_multi_arch.yml`
* the corresponding focused tests

It should not contain test-impact reporting, super-repo source reporting, or
workflow timing collection.

Required evidence:

1. A normal PR/default `dry-run` that rebuilds all stages.
2. A `workflow_dispatch` run using `reuse-stage` that selects an exact
   diff-base baseline, copies the expected artifacts, and skips only the
   verified reusable stages.
3. Missing-artifact, unhealthy-job, stale-baseline, and cross-platform
   disagreement cases that rebuild conservatively.
4. An external-repository invocation showing that the cross-repository
   guardrails and manual configuration precedence still work.

This is the largest of the three PRs, but it has one coherent review question:
can CI safely replace selected builds with exact-baseline artifacts?

#### PR 2: Report-only CI impact and source-provenance reporting

This PR should combine the non-behavior-changing setup reports:

* stage-to-test impact recommendations;
* platform-specific test inventory lookup;
* rendering and publishing the CI impact summary;
* external super-repo and TheRock source/ref audit information.

Likely files include:

* `build_tools/github_actions/stage_to_test_impact.py`
* `build_tools/github_actions/fetch_test_configurations.py`
* `build_tools/github_actions/super_repo_signal.py`
* the report-only portions of
  `build_tools/github_actions/configure_multi_arch_ci.py`
* the relevant setup-summary workflow hunks
* the corresponding focused tests

This PR may depend on PR 1's pure stage-impact/planning result, but it must not
modify `prebuilt_stages`, test labels, or generated test matrices. Combining
the super-repo signal here is acceptable because both features are human-facing
setup diagnostics with the same rollback behavior and workflow integration
point.

Required evidence:

1. Reports from normal TheRock and external `rocm-systems` or
   `rocm-libraries` calls.
2. Unmapped, forced, unavailable, and platform-inapplicable test components are
   represented conservatively.
3. Report generation does not change build or test selection.
4. Broken or missing report output has an explicit, tested failure policy.

#### PR 3: Workflow timing telemetry

This PR should contain only the Actions API timing collector and its artifacts:

* job/run pagination and timing-record collection;
* runner pool/instance and workflow-phase classification;
* Markdown and JSON rendering;
* the workflow job or step that uploads those artifacts.

Likely files include:

* `build_tools/github_actions/workflow_timing.py`
* `build_tools/github_actions/workflow_timing_json.py`
* `build_tools/github_actions/tests/workflow_timing_test.py`
* only the timing-specific `workflow_summary.py` and workflow hunks, if timing
  remains integrated there

Prefer a separate collector job or workflow over making the required build/test
summary depend on telemetry. The timing module should not import a duration
helper from `baseline_runs.py`; keep that calculation local or move it to a
genuinely generic utility. Invalid or out-of-order timestamps should remain
unknown (`None` or an explicit invalid state), not be converted to zero-second
durations.

Required evidence:

1. A completed multi-arch run that uploads valid Markdown and JSON artifacts.
2. Multi-page job results and retry attempts are handled.
3. Missing and invalid timestamps remain distinguishable from real zeroes.
4. Actions API or formatting failures follow the documented failure policy
   without obscuring the build/test verdict.

PR 3 is technically independent, but it should land last because it has the
lowest bearing on stage-reuse correctness and introduces a new live API
dependency.

The three-PR dependency order is:

```text
1. Stage reuse safety and execution
                 |
                 v
2. Report-only impact and source provenance

3. Workflow timing telemetry (independent; land last)
```

### Finer-grained alternative: six PRs

If individual review and rollback boundaries are more important than stack
overhead, split the same work into six PRs:

1. **Exact-baseline provenance guardrail** -- `baseline_runs.py` and the
   minimal caller/test changes needed to require
   `candidate.head_sha == diff_base_commit`.
2. **Pure stage-reuse planner** -- platform/family applicability, artifact
   availability, conservative planning, and unit tests, without workflow
   behavior changes.
3. **Stage-reuse workflow integration** -- `dry-run`/`reuse-stage` inputs,
   output propagation, and end-to-end artifact-copy behavior.
4. **Report-only test-impact analysis** -- test inventory, impact
   recommendations, summaries, and tests, without matrix changes.
5. **External super-repo source signal** -- the source/ref audit module, tests,
   and its minimal setup-workflow step.
6. **Workflow timing telemetry** -- the Actions API collector, JSON/Markdown
   output, tests, and isolated workflow integration.

Their dependency structure would be:

```text
1. Exact baseline safety
          |
          v
2. Pure reuse planner
       /       \
      v         v
3. Apply reuse  4. Report test impact

5. Source/ref signal      independent
6. Timing telemetry       independent; land last
```

The six-PR structure is cleaner technically, but the three-PR structure above
is likely the better practical balance for this change.

## Strengths

* Exact `candidate.head_sha == diff_base_commit` validation correctly avoids
  reusing artifacts from an older ancestor whose unanalysed changes could make
  them stale.
* Platform/family-specific artifact validation is conservative, and automatic
  reuse remains disabled for cross-repository cases without explicit inputs.
* Unknown test mappings remain enabled, and test-impact recommendations do not
  yet alter the generated matrix.
* Security and pre-commit checks pass on the current head; CodeQL reports no new
  alerts.

## Testing performed

From the reviewed source's `build_tools` directory:

```text
D:/projects/TheRock/.venv/Scripts/python.exe -m pytest \
  github_actions/tests/baseline_runs_test.py \
  github_actions/tests/configure_multi_arch_ci_test.py \
  github_actions/tests/fetch_test_configurations_test.py \
  github_actions/tests/stage_reuse_decision_test.py \
  github_actions/tests/stage_to_test_impact_test.py \
  github_actions/tests/super_repo_signal_test.py \
  github_actions/tests/workflow_summary_test.py \
  github_actions/tests/workflow_timing_test.py \
  -q --basetemp D:/scratch/codex/prreviews/pytest6760a

262 passed, 1 skipped in 0.48s
```

The skipped test is an existing TODO for rejecting a
workflow-dispatch family unavailable on the requested platform.

## Conclusion

**Approval status: CHANGES REQUESTED**

The conservative exact-baseline design is a good foundation, but unit tests are
not sufficient evidence for a workflow that can skip build stages and copy
artifacts. Complete the trigger-path validation first, then reduce the rollout
surface by separating the telemetry and diagnostic additions.

_Review generated by OpenAI Codex._
