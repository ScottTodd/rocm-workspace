# Review: TheRock PR 8365

Reviewed 2026-09-29 at `42dd7d35ff75bea8497fd6e2edd3d607f5eec7d3`.

**Overall assessment: CHANGES REQUESTED.** The first-parent walk correctly establishes ancestry for synthetic PR merges, but ancestry alone does not establish that a baseline's artifacts remain valid.

## Findings

### BLOCKING — P1: Older ancestors can supply artifacts invalidated by intervening commits

Location: [stage_reuse_decision.py:775–779](https://github.com/ROCm/TheRock/blob/42dd7d35ff75bea8497fd6e2edd3d607f5eec7d3/build_tools/github_actions/stage_reuse_decision.py#L775-L779).

The new history allows a synthetic merge `M` to accept baseline `A` through first-parent history `M -> B -> A`. However, [PR impact analysis](https://github.com/ROCm/TheRock/blob/42dd7d35ff75bea8497fd6e2edd3d607f5eec7d3/build_tools/github_actions/configure_multi_arch_ci.py#L330) still computes only `B..M`, and [reuse planning](https://github.com/ROCm/TheRock/blob/42dd7d35ff75bea8497fd6e2edd3d607f5eec7d3/build_tools/github_actions/stage_reuse_decision.py#L462-L468) occurs before baseline selection. No later check accounts for `A..B`.

Concrete case: A has healthy artifacts; B changes CMake build configuration; the PR only bumps rocm-libraries. The event diff says compiler-runtime is unaffected, so this PR now allows copying compiler/runtime artifacts built before the CMake change. Job health, artifact existence, and recency do not detect this. In `reuse-stage` mode this builds/tests the wrong combination of sources and artifacts; default dry-run only reports the unsafe decision.

Reproduced with a real local Git merge graph and the PR's actual topology, history reader, baseline selector, artifact validator, and reuse decision. Only remote workflow/job/artifact listings were supplied as fixtures. Baseline A was selected and ten stages were marked for reuse; computing impact from A instead correctly required a full rebuild.

**Required action:** evaluate impact against each candidate's actual built commit, including all intervening changes, before applying reuse. Alternatively, conservatively restrict reuse to a baseline matching the event's diff base until baseline-relative impact is implemented. Add a regression with an intervening build configuration or compiler/runtime source change.

Scope: this missing baseline-relative check already affects push-event reuse. The change newly exposes it for normal synthetic-merge PRs, whose candidates were previously rejected as unknown; it is not a defect in `git rev-list` itself.

#### External-repository callers: two source identities and two reuse paths

The same safety gap applies to repositories using TheRock's reusable workflows, but the identities differ. Let T be the pinned TheRock commit and L the external repository revision under test. The build uses T's build rules, compiler configuration, and remaining submodule pins, with L substituted for one source repository. `STAGE_REUSE_CURRENT_SHA` identifies T, not the external PR's synthetic merge commit. The automatic selector searches TheRock workflow runs and compares their SHAs against T's history.

For external runs, [configure_multi_arch_ci.py](https://github.com/ROCm/TheRock/blob/42dd7d35ff75bea8497fd6e2edd3d607f5eec7d3/build_tools/github_actions/configure_multi_arch_ci.py#L1772-L1788) constructs a coarse changed-file context such as `["rocm-libraries"]`. It does not analyze the difference between an older candidate A and T. Consequently, A can pass ancestry while containing outdated compiler/runtime sources, other submodules, or build settings. This behavior predates this PR; a mainline T could already be found in the old API-provided history. The PR's merge-commit fix is not generally needed to recognize a normal pinned T.

Inspected rocm-libraries `develop` at `843f2dbf5d80676800d6f5f3ba97bf545b787bf7`, which pins TheRock `7440cb8578f4daae0d85a428fadd6645dc5464a0`. Its [multi-arch workflow](https://github.com/ROCm/rocm-libraries/blob/843f2dbf5d80676800d6f5f3ba97bf545b787bf7/.github/workflows/therock-multi-arch-ci.yml#L170-L208) combines:

- **Explicit reuse:** a manually supplied or [bot-maintained baseline ID](https://github.com/ROCm/rocm-libraries/blob/843f2dbf5d80676800d6f5f3ba97bf545b787bf7/.github/actions/ci-env/action.yml), plus a list of prebuilt stages. This generally includes runtime tests, communications, storage, debugging, profiling, media, and other stages. Math/ML stages are not explicitly prebuilt; cv-libs is rebuilt for RPP changes. Compiler-runtime is deliberately excluded from the explicit list because of an existing CMake-path concern.
- **Automatic reuse:** `reuse-stage` is enabled when an explicit baseline ID exists. Without an ID, the caller selects `off` and rebuilds. Changed projects are passed to downstream testing, but this caller does not pass them to setup's `changed_projects` input; automatic stage impact uses the whole external-repository context above.

There are two additional pre-existing interactions that prevent treating the automatic ancestry gate as a complete safety check:

1. **Explicit prebuilt stages bypass automatic compatibility selection.** They are marked PREBUILT directly. Tightening `_default_baseline_selector` does not establish that the supplied baseline matches T or its build configuration. Compatibility must be established by the caller's coordinated pin/baseline policy or a separate validation step. This review has not established the actual built-tree/configuration equivalence of the bot-maintained baseline; workflow-run `head_sha` alone would not establish that for a PR-produced baseline.
2. **Automatic selection can replace the explicit baseline.** [configure_multi_arch_ci.py:1131–1172](https://github.com/ROCm/TheRock/blob/7440cb8578f4daae0d85a428fadd6645dc5464a0/build_tools/github_actions/configure_multi_arch_ci.py#L1131-L1172) retains explicit PREBUILT stage decisions but replaces the shared `baseline_run_id` whenever automatic reuse applies. Thus explicitly requested stages can be copied from an automatically selected run instead. `explicit_prebuilt_stages` suppresses automatic report entries, not baseline selection or this replacement. In particular, excluding compiler-runtime from the explicit list does not prevent automatic reuse from selecting it.

Source equality also does not establish **configuration equality**. The [existing TODO](https://github.com/ROCm/TheRock/blob/42dd7d35ff75bea8497fd6e2edd3d607f5eec7d3/build_tools/github_actions/stage_reuse_decision.py#L377-L380) acknowledges that reuse is not keyed on build flags. External callers can provide extra CMake options; rocm-libraries currently enables a HIP kernel provider flag. A constant flag across that caller's runs does not by itself prove compatibility with artifacts produced by a differently configured TheRock run. Whether a particular option affects a particular copied artifact requires input/dependency analysis.

These are code-path findings, not a claim that a specific external CI run consumed invalid artifacts. They broaden the existing risk assessment but should not be attributed as new regressions introduced by this PR.

#### Conservative scope for this fix

An interim restriction should express the intended source identity explicitly:

| Build context | Conservative automatic baseline identity |
| --- | --- |
| TheRock synthetic PR merge M | B, M's first parent, matching the existing impact diff base |
| TheRock push | The event's `before` SHA used by impact analysis, not necessarily HEAD's immediate parent |
| External repository using TheRock T | T itself, not T's parent |

If no suitable baseline exists, rebuild. For PRs, fixed checkout depth two is sufficient to resolve B and diff B..M. Fetch depth must not serve as the eligibility policy: explicitly check the baseline identity. Remove the history-window input if ancestor searching no longer has a consumer; push diff-base fetching remains a separate concern. Explicit baseline selection and configuration compatibility still need their own contract. Automatic selection should not silently replace a caller-selected baseline.

Older commits are not inherently unsafe, and not every Python build-tool edit changes every artifact. The problem is that the current checks do not establish which changes are irrelevant to the outputs being reused. Broad path filters can conservatively over-invalidate, while ancestry can under-invalidate; neither is an artifact identity.

#### FUTURE WORK: fingerprint-based artifact cache

The separate [artifact-cache design discussion](https://gist.github.com/ScottTodd/0b62d8207986175bad1c86ee21ce081e) proposes replacing historical workflow searches with direct artifact-key lookups. That is the appropriate place to generalize reuse across older commits and repository boundaries: compute an input key for each required artifact, including relevant source, dependency/toolchain identities, build recipes/options, variant, and output identity, then reuse only a matching published entry. Irrelevant edits can retain the same key without relying on how far back a candidate lies in Git history.

This is a design direction, not evidence that today's fingerprints already form sound cache keys. Their sensitivity to meaningful changes, stability across checkout locations, and publication metadata need validation, as the linked discussion notes. The cache redesign is separate scope; this PR should retain conservative eligibility rather than require implementing that redesign or extend ancestry heuristics to stand in for it.

### BLOCKING — P2: A history window of one removes the parent needed for PR setup

Location: [setup_multi_arch.yml:210–212](https://github.com/ROCm/TheRock/blob/42dd7d35ff75bea8497fd6e2edd3d607f5eec7d3/.github/workflows/setup_multi_arch.yml#L210-L212).

`stage_reuse_commit_history` previously only limited baseline search, and the selector explicitly accepts one (`max(1, ...)`). It now also sets checkout depth. With `"1"`, a shallow checkout treats the synthetic merge as a root and cannot resolve `HEAD^`. [GitContext.from_repo](https://github.com/ROCm/TheRock/blob/42dd7d35ff75bea8497fd6e2edd3d607f5eec7d3/build_tools/github_actions/configure_multi_arch_ci.py#L445-L451) calls `get_git_commit_hash('HEAD^')` before reuse selection; this raises and fails setup, including when stage reuse is off. The missing-SHA fetch helper does not fetch symbolic parent expressions.

Reproduced with a depth-one clone: `get_git_commit_hash('HEAD^')` exits 128. Previously the fixed depth of two retained that parent.

**Required action:** preserve a minimum checkout depth of two independently of the reuse search window, or explicitly fetch the diff base before resolving it. Add a shallow-checkout regression at history count one.

### IMPORTANT — P2: The graph test inherits commit signing from the user's Git configuration

Location: [configure_ci_path_filters_test.py:233–242](https://github.com/ROCm/TheRock/blob/42dd7d35ff75bea8497fd6e2edd3d607f5eec7d3/build_tools/github_actions/tests/configure_ci_path_filters_test.py#L233-L242).

The temporary repository configures author identity but invokes real `git commit` operations without disabling signing. A developer with `commit.gpgsign=true` therefore receives hardware-signing prompts during pytest, or sees failures/timeouts when signing is unavailable. This happened during this review; the user confirmed the signing prompt. CI's unsigned default configuration hides the problem.

**Recommendation:** set `git config --local commit.gpgsign false` in the temporary fixture before creating commits, and disable `merge.gpgsign` there as well so the synthetic merge is independent of user signing settings. Leave the user's global and source-repository settings unchanged.

## Graph and integration assessment

- For a synthetic merge with parents `(B, H)`, walking first parents correctly yields M, B, and older first-parent ancestors. H-only commits and newer main commits are excluded.
- Normal linear pushes and first-parent mainline merge history work with the same traversal. True ancestors reachable only through second parents are conservatively rejected; shallow boundaries also cause conservative misses rather than false ancestry.
- Push impact uses the event's `before` SHA, including multi-commit pushes; new-ref pushes lack a diff and fall back to a rebuild. Manual runs without changed-file context also rebuild. External-repository runs traverse the checked-out TheRock commit in the workspace, not the separate CI-config checkout.
- Missing/unreadable history now fails closed for both same-repository and external callers, which is appropriate.
- Internal workflow callers retain the default history depth unless explicitly forwarding the existing input. No added dependencies or shell interpolation vulnerabilities were found.

## CI evidence

- [PR setup job](https://github.com/ROCm/TheRock/actions/runs/36447776970/job/109014437422) succeeds with depth 50 and synthetic merge `9418202d...`. Its five build-tool/workflow changes force a full rebuild, so it never exercises successful baseline reuse. Unit tests on Linux and Windows and pre-commit pass.
- [Stacked validation setup](https://github.com/ROCm/TheRock/actions/runs/36455796857/job/109041691761) confirms M-to-base traversal and a one-file rocm-libraries diff. It uses history 160 and age 500 hours. Candidate `0a5e4387...` reaches health/artifact checks but is rejected for missing six artifact pairs. This validates ancestry acceptance, not safe successful reuse.
- Inspected all failing checks: JAX reports a clang frontend failure; miopenprovider times out in GPU sanity checking; rocprofiler-systems fails `amd-smi static`; Windows libhipcxx times out after repeated test failures; Windows rocfft fails its test. CI Summary and the PR bot reflect those failures. Since this run selected no reused stages, these failures do not demonstrate a traversal/reuse regression.
- Latest completed main run available during review, [34785131834](https://github.com/ROCm/TheRock/actions/runs/34785131834), has successful setup with the old depth two. It is substantially older than the PR run, so it is not a controlled timing comparison.

## Local evidence

Source was downloaded as an archive at the reviewed SHA to `D:/scratch/codex/pr8365/ROCm-TheRock-42dd7d3`; user checkouts were not modified.

Reproducer: [reproduce.py](D:/scratch/codex/pr8365/reproduce.py). Full output: [reproduce.log](D:/scratch/codex/pr8365/reproduce.log).

```powershell
D:/projects/TheRock/.venv/Scripts/python.exe D:/scratch/codex/pr8365/reproduce.py
```

```text
PR event paths: ['rocm-libraries']
Baseline-to-build paths: ['CMakeLists.txt', 'rocm-libraries']
Candidate A relationship: ancestor
Selected baseline: 123
Applied reuse stages: ('comm-libs', 'compiler-runtime', 'dctools-core', 'debug-tools', 'emulation', 'media-libs', 'profiler-apps', 'runtime-tests', 'storage-libs', 'wsl-rocdxg')
Correct baseline-relative plan full rebuild: True
Depth-one PR base resolution failed: 128
```

Downloaded job logs are retained in `D:/scratch/codex/pr8365/`.

Local pytest was attempted with:

```powershell
cd D:/scratch/codex/pr8365/ROCm-TheRock-42dd7d3/build_tools
D:/projects/TheRock/.venv/Scripts/python.exe -m pytest --override-ini=cache_dir=D:/scratch/codex/pytest-cache/pr8365 github_actions/tests/configure_ci_path_filters_test.py github_actions/tests/stage_reuse_decision_test.py github_actions/tests/baseline_runs_test.py -q
```

That run encountered the signing problem above and was interrupted after failing to finish. After the user authorized disabling signing for test fixtures, reruns used process-local `GIT_CONFIG_COUNT=1`, `GIT_CONFIG_KEY_0=commit.gpgsign`, and `GIT_CONFIG_VALUE_0=false`, with TEMP/TMP under scratch. Those attempts also stalled and were interrupted; no completed local pytest result is claimed. Partial logs are retained as `pytest*.log` in scratch. Passing Linux/Windows unit-test results cited above are CI evidence. The standalone graph/selection reproducer completed successfully and independently confirms both correctness findings.

Generated with Codex.
