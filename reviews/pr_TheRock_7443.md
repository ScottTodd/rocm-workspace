# PR Re-review: ROCm/TheRock #7443

* **PR:** [ROCm/TheRock#7443](https://github.com/ROCm/TheRock/pull/7443)
* **Title:** `[ci] Add quartz_tracking_id to all release-related workflows`
* **Head:** `c931fa9cb1ca9ccc67846ea18dc3625c2098a72a`
* **Base:** `main`
* **Reviewed:** 2026-08-18
* **Review type:** Comprehensive, with emphasis on workflow architecture

## Overall Assessment

**APPROVED** - No code changes are required. The companion
[`ROCm/rockrel#98`](https://github.com/ROCm/rockrel/pull/98) covers all six
rockrel asynchronous targets, removing the cross-repository compatibility
blocker. Explicitly carrying the same field through every reachable workflow is
more verbose, but it gives each Quartz notification a self-contained lineage
value and avoids implicit receiver-side run mapping, event-order handling, and
special cases for workflows that later cross another asynchronous boundary.

Merge rockrel#98 first, then resolve TheRock#7443's current branch conflict and
merge it. A coordinated Quartz-enabled run is still recommended before relying
on the new classification in production.

## Architecture Assessment

The uniform propagation model is reasonable here:

```text
root owner -> workflow_call -> workflow_call -> workflow_dispatch -> workflow_call
                 |                  |                  |                  |
                 +------- the same quartz_tracking_id is explicit -------+
```

Although synchronous `workflow_call` jobs share a `GITHUB_RUN_ID`, using that
fact to reduce YAML would move complexity into Quartz. The receiver would need
to associate all records for a run, tolerate child reports arriving before the
report carrying the explicit owner, backfill those records later, and preserve
the owner through the PyTorch build workflow before its second asynchronous
dispatch. That is not a clear simplification over declarative passthrough.

The PR's approach has useful properties:

* Every `notify_quartz` invocation continues to send `toJSON(inputs)`, and that
  payload contains its own authoritative lineage value.
* Workflow processing remains independent and order-insensitive in Quartz.
* Authors follow one propagation rule instead of deciding whether a particular
  edge creates a new Actions run.
* Missing edges can be detected statically from the workflow graph.

The 284 added lines across 25 files are almost entirely schema declarations and
one-line passthroughs. In this case the repetition represents an explicit
cross-workflow contract rather than duplicated decision logic.

## Companion PR and Merge Ordering

rockrel#98 adds the input to the six wrappers targeted by TheRock's seven
`benc-uk/workflow-dispatch` edges and forwards it to TheRock:

* `test_artifacts.yml`
* `test_native_linux_packages_install.yml`
* `test_pytorch_wheels_full.yml`
* `multi_arch_release_linux_pytorch_wheels.yml`
* `multi_arch_release_linux_jax_wheels.yml`
* `multi_arch_release_windows_pytorch_wheels.yml`

Its pre-commit/actionlint check passes, and all six declarations default to an
empty string, so landing rockrel#98 before TheRock#7443 is backward-compatible.

The merge order is not actually interchangeable despite rockrel#98's current PR
description. TheRock#7443 always includes the JSON key at asynchronous dispatch
sites, even when tracking is disabled and the value is `""`. If TheRock lands
first, existing rockrel wrappers still reject that unexpected key with HTTP
422. The safe order is:

1. Merge rockrel#98 so every target accepts the optional input.
2. Rebase/resolve TheRock#7443's current conflict with `main` and rerun checks.
3. Merge TheRock#7443.
4. Deploy the Quartz classifier change and enable/verify tracking.

This sequencing requires no code change to TheRock#7443. The rockrel#98
description should be corrected from "Safe in either order" to "Merge this PR
first."

## Suggestion: Turn the static propagation audit into a test

The uniform contract is strongest when completeness is machine-checked. The PR
body reports a static audit of 25 declarations, 20 reusable edges, and seven
asynchronous edges, but the audit is not committed as a test. Because the input
defaults to `""`, a future missing passthrough can silently lose lineage while
actionlint and ordinary workflow execution remain green.

Consider extending the existing
`build_tools/github_actions/tests/workflow_dispatch_inputs_test.py` machinery or
adding a focused graph test that starts at `multi_arch_release.yml` and asserts:

* every reachable non-root workflow declares `quartz_tracking_id`;
* every local reusable-workflow edge forwards it; and
* every `benc-uk/workflow-dispatch` payload includes it and its target accepts
  it.

This is a non-blocking follow-up. The existing dispatch-input test already
guards against TheRock dispatches sending undefined keys, and the completed
manual audit plus end-to-end transport run provide adequate evidence for this
change.

## CI Evidence

* Required TheRock checks pass: pre-commit/actionlint and the unit-test summary
  are green.
* The standalone release run
  [`32134565582`](https://github.com/ROCm/TheRock/actions/runs/32134565582)
  completed successfully. Its reusable jobs received `32134565582;dev`, and
  all seven asynchronous trigger jobs accepted and forwarded the value to
  TheRock targets.
* rockrel#98's pre-commit/actionlint check passes and the PR is mergeable.
* The general TheRock Multi-Arch CI failures are in unrelated existing test
  paths: rocFFT timed out after 600 seconds, and a Windows wheel packaging test
  reported missing libraries. Recent `main` runs also contain Multi-Arch CI
  failures.
* Quartz notification jobs were skipped in the standalone TheRock run, so a
  rockrel-triggered, Quartz-enabled run remains the final integration check.
* TheRock#7443 currently conflicts with the updated `main`; checks should rerun
  after conflict resolution.

## Conclusion

**Approval Status: APPROVED**

The explicit end-to-end field is a defensible tradeoff: more declarative YAML,
but simpler and more robust event semantics. Merge rockrel#98 first, resolve the
current TheRock branch conflict, and validate the coordinated path with Quartz
enabled. Automating the graph-completeness audit would be a worthwhile
follow-up.

---

Reviewed with OpenAI Codex.
