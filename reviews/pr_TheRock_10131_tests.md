# AMD SMI test-policy evidence audit

Reviewed 2026-11-19 with Codex. Scope: test coverage and failure history relevant to [TheRock PR 10131](https://github.com/ROCm/TheRock/pull/10131), head `b36b231d299061aa6455ab7252333286860778cf`. This is a focused evidence audit, not a comprehensive code review.

## Assessment

The evidence supports removing the broad downstream GPU runtime-test fan-out for ordinary amdsmi changes. It does **not** establish that amdsmi has complete self coverage or that consumer breakages are uniformly low impact. No confirmed recent runtime regression was identified that passed both the applicable standalone workflows and TheRock's amdsmi test, then was caught uniquely by one of the downstream runtime suites being removed. Expired logs and incomplete rerun histories prevent turning that observation into a zero-escape rate.

**Overall assessment: APPROVED for the runtime scheduling direction, with IMPORTANT qualifications below.** No blocking implementation defect is established in the small policy diff. A safer justification is that full downstream GPU suites have little demonstrated incremental signal for these changes, while known consumer failures deserve cheap, targeted checks. The PR's claim that consumers merely link amdsmi should be softened: RCCL, rocSHMEM, profilers, and Python consumers have meaningful API, layout, loading, and CLI dependencies.

### IMPORTANT: existing standalone coverage is not an equivalent merge gate

The [effective rules for develop](https://api.github.com/repos/ROCm/rocm-systems/rules/branches/develop), retrieved during this audit, list `HIP NVIDIA CI Summary`, `Multi-Arch CI Summary`, and `RCCL PR gate` as required status checks. They do not list AMDSMI CI, AMDSMI ASAN, or the new AMDSMI ABI gate. This is the visible ruleset evidence; the separate legacy branch-protection status-check endpoint returned HTTP 403, so additional legacy protection could not be verified.

Both [AMDSMI CI](https://github.com/ROCm/rocm-systems/blob/develop/.github/workflows/amdsmi-build.yml#L56) and the [ASAN GPU job](https://github.com/ROCm/rocm-systems/blob/develop/.github/workflows/amdsmi-asan.yml) skip fork PRs. A successful ASAN workflow can therefore mean only the hardware-free leg ran. [PR 14676](https://github.com/ROCm/rocm-systems/pull/14676) explicitly says adding the ABI workflow did not make it required.

Recommendation: if standalone coverage is the justification for removing a blocking check, make the relevant standalone checks enforceable and provide a trusted GPU path for fork PRs, or put the necessary checks in the retained TheRock self job. This audit does not propose changing repository settings automatically.

### IMPORTANT: self tests and packaged integration tests cover different failure modes

TheRock's retained amdsmi job tests its own installed artifact and compiler/runtime configuration. The standalone workflows build another configuration, largely with distro GCC. Passing one is not a substitute for testing the other artifact. Retain the TheRock self job and its existing CLI startup check. Consider adding bare `amd-smi` and `amd-smi process`, including the relevant sanitizer mode, to that job rather than paying for a consumer's complete GPU test suite to invoke them incidentally.

The existing `Driver / GPU sanity check` already invokes `amd-smi static` with checked exit status before the component test. The proposal therefore retains a useful CLI smoke check; adding another identical static check would be redundant. That probe disables leak detection, so it is not a substitute for the explicit CLI leak check.

Sources: pinned [test_component.yml](https://github.com/ROCm/TheRock/blob/c0d2f4d21e7daffe3896b9be9ce9d1b2e0793827/.github/workflows/test_component.yml#L171), [print_driver_gpu_info.py](https://github.com/ROCm/TheRock/blob/c0d2f4d21e7daffe3896b9be9ce9d1b2e0793827/build_tools/print_driver_gpu_info.py#L145), and [test_amdsmi.py](https://github.com/ROCm/TheRock/blob/c0d2f4d21e7daffe3896b9be9ce9d1b2e0793827/build_tools/github_actions/test_executable_scripts/test_amdsmi.py).

## Activity metrics

Activity uses full UTC days: start inclusive, `2026-11-19T00:00:00Z` exclusive. Commits come from the GitHub commits API for `develop` and `path=projects/amdsmi`. Every one of the 140 recent commits was joined to its associated PRs; all qualifying develop merges were already in the labelled cohort. This avoids assuming that a commit is a distinct PR or counting merges to feature/release branches as develop integrations.

| Window | Path commits reachable from develop | Commits/day | Distinct merged PRs to develop touching the path | PRs/day |
|---|---:|---:|---:|---:|
| Sep 19–Nov 18, 61 days | 140 | 2.30 | 92 | 1.51 |
| Oct 19–Nov 18, 31 days | 86 | 2.77 | 38 | 1.23 |

The 140 commits include one merge commit and multiple commits integrated by a single PR. In particular, November's NIC work contributes many commits, so counting commits alone exaggerates the number of independent changes/merge events.

The broader discovery query found 299 `project: amdsmi` PRs updated since Sep 19: 291 actually touch `projects/amdsmi`, 270 touch no other `projects/<name>` project, and 244 change only paths under `projects/amdsmi/`. There were 104 labelled PR merges in the activity window across all target branches, of which 94 targeted develop; two of those 94 do not touch the amdsmi path. These broader counts are **not** the merge-rate numerator above.

## Coverage overlap

Workflow source was fetched from remote develop, rather than assuming the local checkout was current. The regular external workflow pins TheRock to `c0d2f4d21e7daffe3896b9be9ce9d1b2e0793827` (Nov 11). Historic runs may use earlier pins.

| Coverage | TheRock multi-arch / retained amdsmi job | Standalone amdsmi workflows |
|---|---|---|
| C++ amdsmitst | Yes; quick includes legacy dynamic metrics and `*Unit*`; standard/full includes GPU functional read/write, units, and dynamic metrics, with explicit and ASIC exclusions | `amdsmi-build.yml` runs the binary with ASIC exclusions; ASAN GPU runs the full binary with state-changing tests disabled |
| Privileged writes | Automatically skipped in unprivileged containers; ASIC and manual exclusions also apply | Regular GPU job has a privileged container and covers state-changing paths; ASAN GPU deliberately sets `AMDSMI_NON_PRIVILEGED=1` |
| Python bindings, CLI tests, examples | Self runner does not execute these suites; pre-test probe runs `amd-smi static` | Regular GPU workflow runs integration, Python unit, CLI unit, ABI/loader compatibility tests, and DRM/non-DRM examples; sweeps 13 CLI commands |
| Memory safety | Separate TheRock ASAN workflows/configurations; a green workflow summary alone does not demonstrate an amdsmi GPU test ran | `amdsmi-asan.yml`: hardware-free units plus GPU binary and CLI sweeps; explicit CLI leak mode added Nov 11 |
| Python versions | Not a matrix in self runner | `amdsmi-python-versions.yml`: loader checks across Python 3.6–3.15; these are loader tests, not the entire test suite on every interpreter |
| Packaging and loading | Tests the TheRock artifact/install layout; does not replace all standalone package tests | Main workflow: 10 distro/container legs; manylinux wheels: RPM/DEB builds, wheel/loader/conflict checks; SLES packaging; DEB/RPM upgrade/downgrade/component removal |
| Public ABI against older consumers | Rebuilding a test against the new header does not prove compatibility with an old binary | ABI gate checks sizes, offsets, signatures, constants, and related contracts against base/release headers; not listed as required in the visible ruleset |
| Real consumers | Broad integration/build and runtime suites; sometimes merely running an amdsmi diagnostic is the coupling | DME workflow source exists, but its workflow history's latest run was Sep 3, before the study window; do not count it as recently exercised consumer coverage |
| Hardware/configuration | Configured regular families include gfx94X, gfx950, gfx125X; actual jobs depend on selection/availability. Example run only executes gfx94X tests. amdsmi is Linux-only in TheRock | GPU hardware is selected by repository runner variables; a distro matrix is not evidence of a GPU-architecture matrix; guarded GPU jobs do not run automatically on forks |

The overlap is substantial for C++ unit/read-only GPU behavior. Standalone CI is substantially broader in Python, CLI, packaging, and privilege scenarios. TheRock adds artifact/configuration integration coverage. Neither is a strict superset of the other.

Workflow sources: [regular multi-arch](https://github.com/ROCm/rocm-systems/blob/develop/.github/workflows/therock-multi-arch-ci.yml), [AMDSMI CI](https://github.com/ROCm/rocm-systems/blob/develop/.github/workflows/amdsmi-build.yml), [ASAN](https://github.com/ROCm/rocm-systems/blob/develop/.github/workflows/amdsmi-asan.yml), [Python versions](https://github.com/ROCm/rocm-systems/blob/develop/.github/workflows/amdsmi-python-versions.yml), [manylinux](https://github.com/ROCm/rocm-systems/blob/develop/.github/workflows/amdsmi-manylinux-build.yml), [SLES](https://github.com/ROCm/rocm-systems/blob/develop/.github/workflows/amdsmi-sles-packaging.yml), [upgrade/downgrade](https://github.com/ROCm/rocm-systems/blob/develop/.github/workflows/amdsmi-upgrade-downgrade.yml), [ABI](https://github.com/ROCm/rocm-systems/blob/develop/.github/workflows/amdsmi-abi-gate.yml).

## Recent CI failure evidence

PR CI discovery covers Sep 19 through the Nov 19 collection time. The inventory includes 1,355 regular TheRock multi-arch PR runs and 1,338 TheRock ASAN PR runs associated with the 299 PR head branches. These are branch-associated inventories, not 2,693 independent tests or independent changes. Run metadata, available earlier attempts, and cancelled runs were examined, rather than only the final checks on merged PRs. Shared branch names and PRs changing multiple projects are recorded in the inventory and are not sufficient causal evidence.

The same source SHA was used to join standalone workflow results to downstream failures. A stricter candidate requires TheRock's same-family amdsmi test to have passed at that attempt or an earlier inherited attempt, and the latest discovered run of every applicable standalone amdsmi workflow on that SHA to be successful, including AMDSMI CI. Missing/skipped workflows are not silently treated as passing. Even this condition does not prove every possible check was triggered or a guarded ASAN GPU leg ran.

The regular-run screen requested all jobs/attempts for 901 runs with failures, cancellations, timeouts, or reruns. It obtained 887 complete enumerations and fallback data for 14 runs; 13 of those fallback histories may omit attempts/jobs, and one returned no job data. Successful single-attempt runs were screened by workflow conclusion rather than downloading every job. Earlier complete enumerations from exploratory sampling were retained too. A non-blocking failed job inside an otherwise successful single-attempt workflow could therefore be missed; this is primarily an audit of failures capable of affecting the blocking CI result.

Across the collected job data, 232 failing Linux jobs in the removed consumer set had an effective same-family self-test pass. Of those, **87 job attempts across 60 runs** also met the stricter standalone-green condition. **45 had downloadable logs; 42 did not.** The last-month portion contains **35 such job attempts, all with downloadable logs**. No confirmed amdsmi-caused unique runtime catch was established in those 35. These are selected failure candidates, not 35 independent code changes or the denominator for a statistical escape rate. The machine-readable inventory also records the cases that did not meet the standalone-green condition.

Representative candidates inspected in full logs:

| Run/job | Observed failure | Attribution |
|---|---|---|
| [Oct 16 hipblaslt](https://github.com/ROCm/rocm-systems/actions/runs/38916082631/job/117056895465) | `matmul_size_t_output_overflow...` repeatedly cannot allocate 8–9 GB of host memory, then SIGSEGV | No demonstrated amdsmi causal path; a host-memory/test problem is the visible failure |
| [Oct 23 hipblaslt](https://github.com/ROCm/rocm-systems/actions/runs/39987028252/job/120560637579) | Same large-output matmul case, host allocation failures, SEGFAULT | Same qualification; not counted as an amdsmi regression |
| [Nov 5 hipblaslt](https://github.com/ROCm/rocm-systems/actions/runs/42114042689/job/127587698867) | Artifact setup cannot resolve api.github.com | Infrastructure; tests never reach an amdsmi-dependent behavior |
| [Nov 18 hipblaslt, shard 6](https://github.com/ROCm/rocm-systems/actions/runs/44346347853/job/135008798444), [shard 2](https://github.com/ROCm/rocm-systems/actions/runs/44346347853/job/135008798598) | GPU node-9 hang during matmul; both shards abort | No evidence attributing the GPU hang to amdsmi; same-SHA amdsmi checks passed |
| [Oct 14 hipsparselt](https://github.com/ROCm/rocm-systems/actions/runs/38588395270/job/115973947711) | GPU node-5 hang | No demonstrated amdsmi attribution |
| [Oct 13 RCCL](https://github.com/ROCm/rocm-systems/actions/runs/38481268905/job/115626276285), [Nov 17 RCCL](https://github.com/ROCm/rocm-systems/actions/runs/44128731788/job/134278459657) | Test step reaches its 15-minute timeout | No demonstrated amdsmi attribution; timeout alone is not a regression diagnosis |
| [Oct 22 rocSHMEM run, later rerun](https://github.com/ROCm/rocm-systems/actions/runs/39833181645/job/121704187028) | ghcr.io Docker login fails | Infrastructure |

Other inspected failures include HIP memory-prefetch assertions/segfaults, profiler output/baseline expectations, Windows test failures, and pytest/plugin compatibility. They are not automatically called flakes or proven unrelated; no amdsmi cause was established. Windows failures especially cannot demonstrate a runtime defect in the Linux-only TheRock amdsmi binary. Cases with a failing standalone workflow do not meet the requested all-self-checks-green shape.

### An actual downstream ASAN failure, with an important distinction

[PR 13401](https://github.com/ROCm/rocm-systems/pull/13401), merged Nov 11, documents real LeakSanitizer failures in TheRock's **amdsmi and libhipcxx jobs**: libhipcxx invoked bare `amd-smi`, which leaked the GPU process-list cache and exited nonzero before the consumer tests ran. This is real downstream impact, but it is **not** a unique downstream catch after amdsmi itself passed: the amdsmi job failed too, and that TheRock build predated the fix in [PR 12362](https://github.com/ROCm/rocm-systems/pull/12362), merged Oct 1. The PR reports TheRock's pin included the fix from Oct 5.

The November follow-up added a CLI-specific leak sweep because the existing preloaded CLI sweep disabled leak detection to avoid CPython allocation noise. Its reported A/B replay catches the old leak in both the full binary suite and the new CLI check. This is evidence of a known gap being closed, not a new November regression in current source and not evidence that every consumer runtime suite is necessary.

## Twelve-month history: consumer breakages are real

The `develop` path history from Nov 19, 2025 through Nov 18, 2026 contains 595 commits. A search across complete commit messages for reverts, regressions, named consumers, loader/ABI problems, crashes, and leaks found 157 candidate messages. Relevant PR bodies, discussions, and linked incidents were then checked. Keyword hits are discovery aids, not a defect count. Twelve commit subjects begin with a revert form; one is explicitly the reversal of a CI experiment, and several are parts of the same revert/reland sequence.

| Date | Evidence | What it establishes |
|---|---|---|
| Feb–Mar | [TheRock issue 3487](https://github.com/ROCm/TheRock/issues/3487), [amdsmi PR 3777](https://github.com/ROCm/rocm-systems/pull/3777) | amdsmi/rocm-smi symbol collision caused SIGBUS when importing torch and ray, breaking vLLM startup; internal symbol visibility was tightened |
| Mar 24 / Apr 3 | [Revert 4371](https://github.com/ROCm/rocm-systems/pull/4371), [fix 4660](https://github.com/ROCm/rocm-systems/pull/4660) | Real sanity-test failures and process-exit invalid frees; these demonstrate the value of retained startup/sanity coverage, not necessarily a need for all math-library tests |
| Jun 25 | [Issue 7808](https://github.com/ROCm/rocm-systems/issues/7808), [revert 7810](https://github.com/ROCm/rocm-systems/pull/7810) | A new `rocm_sdk` import in the amdsmi loader broke 21 rocprofiler-compute profile-mode tests under its restricted import guard; confirmed consumer failure and revert |
| Jul 27–28 | [Revert 9339](https://github.com/ROCm/rocm-systems/pull/9339), [reland 9340](https://github.com/ROCm/rocm-systems/pull/9340) | Python packaging rework blocked a TheRock bump; reland fixed CLI interpreter/shebang assumptions in relocatable environments |
| Aug 31 | [PR 9879](https://github.com/ROCm/rocm-systems/pull/9879) | Added a direct amdsmi restrictive-import-guard regression test for the June 21-test consumer failure; concrete transfer of downstream signal into self coverage |
| Sep 4–7 | [Issue 11286](https://github.com/ROCm/rocm-systems/issues/11286), [revert 11281](https://github.com/ROCm/rocm-systems/pull/11281) | Fabric struct grew 320→552 bytes; RCCL's compile-time layout guard broke the comm-libs build. This was a build failure, not an eight-GPU runtime-test catch |
| Oct 14–29 | [Reland 11741](https://github.com/ROCm/rocm-systems/pull/11741), [revert 14511](https://github.com/ROCm/rocm-systems/pull/14511) | Feature was reapplied after RCCL accepted the new layout, then reverted again because it still broke ABI compatibility with released libraries. Current-source rebuilds can pass while old binaries remain unsafe |
| Oct 22 | [Revert 13926](https://github.com/ROCm/rocm-systems/pull/13926) | Driver-info struct grew 768→1792 bytes without a SONAME change; callers using the old allocation could be overrun by 1,024 bytes. High potential impact, not harmless monitoring noise |
| Oct 28 | [PR 13470](https://github.com/ROCm/rocm-systems/pull/13470) | Unconditional mutex unlock made TSAN-instrumented `amd-smi static` exit 86 and interfere with downstream sanity checks; direct regression coverage was added |
| Nov 18 | [PR 14409](https://github.com/ROCm/rocm-systems/pull/14409), [TheRock issue 9226](https://github.com/ROCm/TheRock/issues/9226) | Fixes duplicate-library symbol binding that made PyTorch report zero GPUs, plus invalid BDFs without libdrm. The issue was reported in June, so Nov 18 is the fix date, not proof of a new November introduction. Added/strengthened direct tests and wheel symbol-conflict checks |

This history does not support a confident claim that consumer instability has simply disappeared. Some important issues were fixed very recently; others persisted for months. It **does** show a pattern of moving identified consumer failure classes into direct checks.

### Coverage improvements and their dates

| Merged | Improvement | Consequence for interpreting old green CI |
|---|---|---|
| Aug 31 | Restrictive import regression test, PR 9879 | Old loader/import compatibility escape has a direct reproducer |
| Oct 2 | [ASAN workflow, PR 12363](https://github.com/ROCm/rocm-systems/pull/12363) | Earlier amdsmi workflows did not provide this sanitizer coverage |
| Oct 14 | [Fail GPU CI on command/test failures, PR 12997](https://github.com/ROCm/rocm-systems/pull/12997) | Earlier green runs could hide CLI/example failures; CLI unit tests were not being run, and an early suite failure could hide later suites |
| Oct 30 | [Repair ABI report parsing, PR 14425](https://github.com/ROCm/rocm-systems/pull/14425) | Earlier ABI reports could incorrectly appear clean; repaired reporting was still non-blocking |
| Nov 4 | [Add ABI gate, PR 14676](https://github.com/ROCm/rocm-systems/pull/14676) | PR reports replay detecting 19 historic layout/API breaks; this is author-reported replay evidence, not independently rerun here, and the workflow addition did not itself make the gate required |
| Nov 11 | [CLI leak check, PR 13401](https://github.com/ROCm/rocm-systems/pull/13401) | Covers the consumer-style bare CLI leak mode explicitly; only about a week of current-policy history exists at audit time |
| Nov 18 | Symbol binding / missing-libdrm checks, PR 14409 | Very recent direct coverage for a real PyTorch interaction |

Therefore a two-month aggregate pass rate would mix materially different test policies. It would not be a valid estimate of the current policy's escape rate, even if every log were available. More fixes or test additions also do not by themselves prove worsening or improving product stability.

## Cost in the linked example

For [push run 43939350749](https://github.com/ROCm/rocm-systems/actions/runs/43939350749), commit `08aeffaf88f67ae02e3a6c170cfd9fc179553b41`:

- 32 actual leaf test jobs occupied 268.6 runner-minutes in aggregate, excluding build jobs and queue time. This is elapsed job allocation, including job setup/cleanup, not summed test-binary CPU time or a billing estimate.
- [Test amdsmi](https://github.com/ROCm/rocm-systems/actions/runs/43939350749/job/133621345903) occupied 1.72 minutes; its binary ran 506 tests in 37.36 seconds: 453 passed, 53 skipped. It detected an unprivileged container.
- [RCCL](https://github.com/ROCm/rocm-systems/actions/runs/43939350749/job/133621345917) occupied 15.13 minutes and [rocSHMEM](https://github.com/ROCm/rocm-systems/actions/runs/43939350749/job/133621346183) 2.93 minutes, both on `linux-gfx942-8gpu-ossci-rocm`.
- The 30 component jobs other than amdsmi and sanity account for 265.93 runner-minutes. This is an illustrative opportunity for removing downstream fan-out, not a measured before/after saving across all PRs.
- Weighting allocations by runner GPU count gives about 395.1 GPU-minutes (6.58 GPU-hours) for all 32 jobs. This does not measure actual GPU utilization.
- The sole failed leaf was [rocprofiler-systems](https://github.com/ROCm/rocm-systems/actions/runs/43939350749/job/133621346123), in `openmp-fortran-offload-sampling`, with a sampling-thread `getenv` SIGSEGV. No amdsmi attribution was established; it must not be counted as an amdsmi regression just because the push changed amdsmi.

## Recommended policy shape

1. Remove routine full hipblaslt/prim/hipsparselt/RCCL/rocSHMEM runtime-suite fan-out for amdsmi-only changes. The audit found no confirmed unique recent catch sufficient to justify that blanket cost.
2. Retain TheRock's artifact-specific amdsmitst job and checked `amd-smi static` probe. Add cheap targeted CLI/loader/sanitizer checks where known consumers exercise something absent from that retained job; especially bare CLI and process-list behavior.
3. Preserve consumer build/layout checks for public-header changes. The RCCL incident is a strong argument for cheap compile/ABI protection, not for always running eight-GPU collectives. Test policy and build-stage selection are separate mechanisms and should be checked separately.
4. Make the intended replacement merge gates enforceable and handle fork PRs explicitly. Do not infer coverage merely from a workflow file's presence or green overall conclusion.
5. Keep consumer-specific integration tests, opt-in downstream testing for risky API/loader changes, and broader scheduled integration coverage. Review actual escape incidents after the newer self checks have accumulated meaningful history.

## Reproduction and evidence preservation

All GitHub metadata/log requests used authenticated `gh api`, `gh pr view`, `gh pr diff`, and `gh pr checks`. No comments, reviews, workflow dispatches, or repository-setting changes were posted. No source code was changed and no GPU builds were launched.

Raw JSON, workflow snapshots, scripts, and downloaded job logs are under [D:/scratch/codex/amdsmi-policy](D:/scratch/codex/amdsmi-policy). The full commands are in the collection scripts, including the exact REST endpoints and pagination. Run the scripts with `D:/projects/TheRock/.venv/Scripts/python.exe`; they cache successful API responses, so reruns reproduce the saved snapshot unless those caches are deliberately refreshed.

Key files:

- `collect.py`, `prs.json`, `commits.json`, `commit-pr-associations.json`: labelled cohort, PR metadata, regular workflow inventories, and verified merge-rate join.
- `other_runs.py`, `other-<PR>.json`: same-branch standalone and TheRock ASAN run inventories.
- `jobs.py`, `jobs-<RUN>.json`, `jobs-progress.txt`: all-attempt job inventories and failed enumeration diagnostics.
- `recover.py`, `partial-jobs-<RUN>.json`: fallback recovery for incomplete job histories.
- `logs.py`, `logs/<JOB>.log`, `logs/<JOB>.error`: full raw log output or endpoint error, not only excerpts.
- `audit_stats.py`, `failure-inventory.json`: job/attempt/PR association details, failed steps, log availability, and pure-path PR flags.
- `focus.py`, `focus-cases.json`, `focus-summary.txt`: stricter same-SHA, self-pass candidates relevant to removed Linux consumer tests.
- `long_history.py`, `commits-12mo.json`, `history-matches.txt`, `incident-*.json`: long-term history and incident source material.
- `sources/`, `history-*.json`, `develop-rules.json`: remote workflow/configuration snapshots and coverage change dates.
- `metrics.py`, `example-jobs.json`, `example-amdsmi.log`, `example-rocprofiler.log`: the linked push-run measurements and full log outputs.

Limitations: label/path discovery can miss an issue never attributed to amdsmi; branch-associated runs can include mixed changes or reused branches; a final PR diff does not reconstruct every intermediate revision. Many older logs return HTTP 410, and some job enumeration requests return HTTP 502/404. These are recorded as unavailable, not classified as flakes or successful coverage. No numerical upper bound on undetected amdsmi regressions is claimed.

Generated with Codex.
