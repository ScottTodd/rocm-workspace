# Fine-grained artifact reuse for `rocm-libraries` bump PRs

Date: 2026-08-14

Related issue: [ROCm/TheRock#3399](https://github.com/ROCm/TheRock/issues/3399)

Timing source: [ROCm/TheRock Actions run 31742388474](https://github.com/ROCm/TheRock/actions/runs/31742388474),
Linux `gfx94X-dcgpu` math-libs job and its
[published build logs](https://therock-ci-artifacts.s3.amazonaws.com/31742388474-linux/logs/math-libs/gfx94X-dcgpu/index.html).

## Executive summary

This report evaluates whether TheRock CI should reuse individual artifacts
inside the `math-libs` build stage for bump PRs that update the
`rocm-libraries` submodule.

The analysis covers the 10 most recent merged `rocm-libraries` bumps on
TheRock `main` as of 2026-08-14. Those bumps rolled up 340 commits and had
3,928 changed-file entries across their 10 monorepo comparisons.

The result supports a cautious view of fine-grained reuse:

- A direct-folder-only policy could reuse 93 of 180 artifact instances across
  the sample: 51.7%, or 9.3 of 18 artifacts per bump.
- A dependency-aware policy could safely reuse only 44 of 180 artifact
  instances: 24.4%, or 4.4 artifacts per bump.
- The 18 artifacts account for 10,093.8 seconds, or 168.23 minutes, of summed
  subproject build duration in the measured run. These builds overlap; the
  corresponding job took 90 minutes 40 seconds of wall time.
- Direct-folder-only reuse would avoid an average of 40.4 summed build minutes
  per bump, or 24.0% of measured artifact build work.
- Dependency-aware reuse would avoid an average of 23.2 summed build minutes
  per bump, or 13.8% of measured artifact build work.
- Four of the 10 bumps would avoid only about 9.4 seconds of dependency-aware
  work: `libhipcxx` plus `support`. The latest bump would avoid only 3.2 summed
  minutes.
- A minority of bumps could avoid substantial background work when `prim`,
  `composable-kernel`, `fft`, or `hiptensor` were reusable. The best sampled
  case avoided 62.1 summed minutes, or 36.9% of measured artifact work.
- `blas` was directly affected in all 10 bumps. It accounts for 88.88 summed
  minutes, 52.8% of measured artifact work, and contained the last-finishing
  subproject in the measured job.
- `miopen` was directly modified in only five bumps, but was safely reusable
  in none because its declared dependencies include `blas`,
  `composable-kernel`, and `rand`.
- `rocwmma` was directly modified in none of the bumps, but was safely reusable
  in none because it depends on `blas`.

The summed-duration savings are workload proxies, not wall-clock predictions.
Because every bump still rebuilds `blas`, none removes the observed build
critical path. Reusing other artifacts may make `blas` faster indirectly by
reducing CPU and memory contention, but that effect cannot be calculated from
one completed run. A representative A/B CI experiment is needed before using
the summed-duration percentages as expected wall-time savings.

## Question and scope

The motivating proposal is finer-grained than the stage-aware reuse described
in [issue #3399](https://github.com/ROCm/TheRock/issues/3399). The question here
is whether a TheRock bump PR can rebuild only the artifacts associated with
changed `rocm-libraries` projects while copying other artifacts from a baseline
run.

This report evaluates two policies:

1. **Direct-folder-only reuse:** rebuild an artifact when one of its mapped
   project folders changed. Reuse consumers even when a dependency changed.
2. **Dependency-aware reuse:** first identify directly changed artifacts, then
   rebuild every consumer reachable through the in-stage `artifact_deps`
   relationships in `BUILD_TOPOLOGY.toml`.

The second policy is the safer interpretation. The first is an optimistic
upper bound that assumes dependency changes are ABI-compatible and do not
require consumers to be rebuilt or relinked.

## Data sources

### TheRock bump commits

The commit sample came from the first-parent history of TheRock `main`, limited
to commits that changed the `rocm-libraries` gitlink:

```powershell
git -C D:/projects/TheRock log upstream/main --first-parent -- rocm-libraries
```

For each TheRock bump commit, `git ls-tree` identified the old and new
`rocm-libraries` SHAs. Complete local monorepo diffs were then used instead of
the GitHub comparison API, avoiding the API's compare-file limit.

The sample consists of these 10 consecutive merged bumps:

| Date | TheRock bump | `rocm-libraries` range | Rolled commits | Changed files |
|---|---|---|---:|---:|
| 2026-08-13 | [#7258 / `ba6f1b2`](https://github.com/ROCm/TheRock/pull/7258) | [`67811f1..962d005`](https://github.com/ROCm/rocm-libraries/compare/67811f1...962d005) | 68 | 1,640 |
| 2026-08-10 | [#7149 / `f5a34f5`](https://github.com/ROCm/TheRock/pull/7149) | [`58272b3..67811f1`](https://github.com/ROCm/rocm-libraries/compare/58272b3...67811f1) | 33 | 75 |
| 2026-08-06 | [#7134 / `999ee15`](https://github.com/ROCm/TheRock/pull/7134) | [`6aa4f41..58272b3`](https://github.com/ROCm/rocm-libraries/compare/6aa4f41...58272b3) | 31 | 205 |
| 2026-08-05 | [#7117 / `122dc6f`](https://github.com/ROCm/TheRock/pull/7117) | [`f857d8e..6aa4f41`](https://github.com/ROCm/rocm-libraries/compare/f857d8e...6aa4f41) | 8 | 134 |
| 2026-08-05 | [#7115 / `9b31329`](https://github.com/ROCm/TheRock/pull/7115) | [`9f3670b..f857d8e`](https://github.com/ROCm/rocm-libraries/compare/9f3670b...f857d8e) | 62 | 349 |
| 2026-08-03 | [#7059 / `ad0b692`](https://github.com/ROCm/TheRock/pull/7059) | [`c83e2d1..9f3670b`](https://github.com/ROCm/rocm-libraries/compare/c83e2d1...9f3670b) | 45 | 750 |
| 2026-07-31 | [#6992 / `42dfe24`](https://github.com/ROCm/TheRock/pull/6992) | [`bb8b1d6..c83e2d1`](https://github.com/ROCm/rocm-libraries/compare/bb8b1d6...c83e2d1) | 7 | 97 |
| 2026-07-30 | [#6983 / `2ee5410`](https://github.com/ROCm/TheRock/pull/6983) | [`06e7c58..bb8b1d6`](https://github.com/ROCm/rocm-libraries/compare/06e7c58...bb8b1d6) | 48 | 294 |
| 2026-07-29 | [#6920 / `73389f3`](https://github.com/ROCm/TheRock/pull/6920) | [`eea3da6..06e7c58`](https://github.com/ROCm/rocm-libraries/compare/eea3da6...06e7c58) | 10 | 80 |
| 2026-07-28 | [#6908 / `0200ab5`](https://github.com/ROCm/TheRock/pull/6908) | [`baa9375..eea3da6`](https://github.com/ROCm/rocm-libraries/compare/baa9375...eea3da6) | 28 | 304 |
| **Total** | **10 bumps** | | **340** | **3,928** |

The changed-file total is the sum of per-range file counts. A path changed in
more than one bump is counted once in each applicable comparison.

### Artifact mapping and dependency graph

The analysis used these TheRock sources:

- `build_tools/artifact_subprojects.json` for artifact-to-subproject aliases.
- `BUILD_TOPOLOGY.toml` for stage membership and `artifact_deps`.
- `math-libs/CMakeLists.txt`, `math-libs/BLAS/CMakeLists.txt`, and
  `ml-libs/CMakeLists.txt` for current artifact producers and physical source
  folder mappings.
- The run's [top-level artifact catalog](https://therock-ci-artifacts.s3.amazonaws.com/31742388474-linux/index.html)
  to verify which artifact names were actually emitted.

There is not currently a one-to-one agreement among all of those files.
`artifact_subprojects.json` contains a `sparse` entry and omits several newer
artifacts, while the measured run emits no separate `sparse` or `solver`
artifact. Sparse and solver subprojects are included in the `blas` artifact.
The measured run emits these 18 math/ML artifacts:

```text
blas, composable-kernel, fft, hipblasltprovider,
hipdnn-integration-tests, hipdnn-samples, hipdnn,
hipkernelprovider, hiptensor, hipthreads, libhipcxx,
miopen, miopenprovider, prim, rand, rocalution,
rocwmma, support
```

The artifact catalog and CMake producers were treated as authoritative for the
denominator. The JSON manifest plus the CMake source directories supplied the
project mappings.

Changes under `.github/`, documentation, policy-bot tooling, Codecov
configuration, and other monorepo-only automation were ignored when deciding
whether build artifacts changed. Changes to `dnn-providers/cmake` and the
shared DNN CTest infrastructure were treated as affecting the DNN provider and
integration-test artifacts.

### Timing run and logs

The timing sample is workflow run
[31742388474](https://github.com/ROCm/TheRock/actions/runs/31742388474):

| Field | Value |
|---|---|
| Workflow | Multi-Arch CI, run 14620 |
| Event and branch | `push` on `main` |
| Head SHA | `6ed44dfed8c636d27edc201cce868c09c57f9a71` |
| Run created | 2026-08-13 20:44:54 UTC |
| Overall run conclusion | failure |
| Measured job | Linux release, math-libs, `gfx94X-dcgpu` / `gfx942` |
| Measured job conclusion | success |
| Measured job start | 2026-08-13 23:07:53 UTC |
| Measured job completion | 2026-08-14 00:38:33 UTC |
| Measured job wall time | 90m40s |

The published directory contains 45 `_build.log` files. For each log, the
final timing marker has this form:

```text
END <completion epoch> <elapsed seconds> <exit code>
```

For example, `composable_kernel_build.log` ends with:

```text
END 1786664163.1204593 1119.743498802185 0
```

All 45 final markers were inspected. Thirty-three logs belong to the 18
artifact outputs and were aggregated below. Twelve shared third-party helper
logs were excluded from artifact totals because they are not uniquely owned by
one reusable math/ML artifact. Configure, install, archive splitting, upload,
and artifact-copy time are also excluded; the user-provided timing method
measures only the `_build.log` phase.

## Source-change results

### Direct touch frequency

The table below shows how often each artifact was directly affected by mapped
source changes. Shared DNN CMake/CTest changes are included in the affected DNN
artifact counts.

| Artifact | Directly affected bumps | Directly untouched bumps |
|---|---:|---:|
| `blas` | 10 | 0 |
| `hipdnn` | 9 | 1 |
| `hipdnn-integration-tests` | 8 | 2 |
| `hipkernelprovider` | 8 | 2 |
| `composable-kernel` | 7 | 3 |
| `hipthreads` | 7 | 3 |
| `miopen` | 5 | 5 |
| `prim` | 5 | 5 |
| `rocalution` | 5 | 5 |
| `fft` | 4 | 6 |
| `hipdnn-samples` | 4 | 6 |
| `hiptensor` | 4 | 6 |
| `miopenprovider` | 4 | 6 |
| `rand` | 4 | 6 |
| `hipblasltprovider` | 3 | 7 |
| `libhipcxx` | 0 | 10 |
| `rocwmma` | 0 | 10 |
| `support` | 0 | 10 |

The direct-only result looks promising in artifact-count terms: 93 of 180
artifact instances, or 51.7%, are untouched. It is also the risky policy. For
example, `rocwmma` is untouched in every bump but consumes changed `blas`
artifacts in every bump.

### Dependency-aware reuse candidates

Applying in-stage dependency invalidation reduces the reusable set to 44 of
180 artifact instances, or 24.4%.

| Bump | Directly untouched | Dependency-aware reusable artifacts |
|---|---:|---|
| #7258 | 4/18 | 3: `libhipcxx`, `rand`, `support` |
| #7149 | 12/18 | 6: `composable-kernel`, `hiptensor`, `libhipcxx`, `prim`, `rand`, `support` |
| #7134 | 9/18 | 5: `hipthreads`, `libhipcxx`, `prim`, `rand`, `support` |
| #7117 | 13/18 | 8: `composable-kernel`, `fft`, `hiptensor`, `hipthreads`, `libhipcxx`, `prim`, `rand`, `support` |
| #7115 | 3/18 | 2: `libhipcxx`, `support` |
| #7059 | 6/18 | 2: `libhipcxx`, `support` |
| #6992 | 15/18 | 9: `composable-kernel`, `fft`, `hipdnn`, `hiptensor`, `hipthreads`, `libhipcxx`, `prim`, `rand`, `support` |
| #6983 | 10/18 | 2: `libhipcxx`, `support` |
| #6920 | 13/18 | 5: `fft`, `libhipcxx`, `prim`, `rand`, `support` |
| #6908 | 8/18 | 2: `libhipcxx`, `support` |
| **Average** | **9.3/18** | **4.4/18** |

Two examples show why the dependency closure matters:

- `miopen` is directly untouched in five bumps but is never dependency-aware
  reusable because `blas` changes in all 10.
- `rocwmma` is directly untouched in all 10 but is never dependency-aware
  reusable because it depends on `blas`.

## Measured build time by artifact

Artifact duration is the sum of the final elapsed-duration field from each
constituent `_build.log`. It measures avoided background build work, not
serial wall time.

| Artifact | Summed seconds | Summed minutes | Share of artifact build work | Dependency-aware reusable bumps |
|---|---:|---:|---:|---:|
| `blas` | 5,332.5 | 88.88 | 52.8% | 0 |
| `prim` | 1,272.6 | 21.21 | 12.6% | 5 |
| `composable-kernel` | 1,119.7 | 18.66 | 11.1% | 3 |
| `rocwmma` | 563.4 | 9.39 | 5.6% | 0 |
| `fft` | 501.9 | 8.37 | 5.0% | 3 |
| `hiptensor` | 396.5 | 6.61 | 3.9% | 3 |
| `hipdnn` | 198.6 | 3.31 | 2.0% | 1 |
| `rand` | 183.5 | 3.06 | 1.8% | 6 |
| `miopen` | 174.8 | 2.91 | 1.7% | 0 |
| `hipkernelprovider` | 84.1 | 1.40 | 0.8% | 0 |
| `hipdnn-integration-tests` | 68.5 | 1.14 | 0.7% | 0 |
| `hipdnn-samples` | 59.5 | 0.99 | 0.6% | 0 |
| `rocalution` | 50.4 | 0.84 | 0.5% | 0 |
| `hipthreads` | 44.2 | 0.74 | 0.4% | 3 |
| `miopenprovider` | 30.1 | 0.50 | 0.3% | 0 |
| `libhipcxx` | 9.3 | 0.16 | 0.1% | 10 |
| `hipblasltprovider` | 4.0 | 0.07 | <0.1% | 0 |
| `support` | <0.1 | <0.01 | <0.1% | 10 |
| **Total** | **10,093.8** | **168.23** | **100.0%** | |

The two artifacts reusable in every sampled bump are also the cheapest:
`libhipcxx` took 9.3 seconds and `support` took less than 0.1 seconds. Together
they account for about 9.4 seconds, or 0.1%, of measured work.

The suspicion that reusable artifacts are always cheap is not fully true.
Occasionally reusable artifacts include `prim` at 21.21 minutes,
`composable-kernel` at 18.66 minutes, `fft` at 8.37 minutes, and `hiptensor` at
6.61 minutes. Those four artifacts account for nearly all of the meaningful
dependency-aware savings in the favorable bumps.

## Estimated avoided build work per bump

The percentages below use 168.23 summed artifact build minutes as the
denominator.

| Bump | Direct-only avoided work | Direct-only share | Dependency-aware avoided work | Dependency-aware share |
|---|---:|---:|---:|---:|
| #7258 | 12.6m | 7.5% | 3.2m | 1.9% |
| #7149 | 65.0m | 38.6% | 49.7m | 29.5% |
| #7134 | 36.1m | 21.5% | 25.2m | 15.0% |
| #7117 | 72.5m | 43.1% | 58.8m | 35.0% |
| #7115 | 9.5m | 5.7% | 0.2m | 0.1% |
| #7059 | 25.4m | 15.1% | 0.2m | 0.1% |
| #6992 | 77.7m | 46.2% | 62.1m | 36.9% |
| #6983 | 30.1m | 17.9% | 0.2m | 0.1% |
| #6920 | 55.2m | 32.8% | 32.8m | 19.5% |
| #6908 | 20.3m | 12.1% | 0.2m | 0.1% |
| **Average** | **40.4m** | **24.0%** | **23.2m** | **13.8%** |

The dependency-aware distribution is bimodal:

- Four bumps avoid only 9.4 seconds.
- The latest bump avoids 3.2 summed minutes.
- The other five bumps avoid 25.2 to 62.1 summed minutes, depending primarily
  on whether `prim`, `composable-kernel`, `fft`, and `hiptensor` are reusable.
- The median dependency-aware avoided work is about 14.2 summed minutes, but
  the median obscures the split between negligible and favorable cases.

## Critical-path interpretation

The measured job ran for 90m40s, while its artifact-owned subproject build
durations sum to 168.23 minutes. Subprojects execute in the background and
overlap, so subtracting an avoided-work total from 90m40s would be invalid.

`blas` is the key constraint:

- It accounts for 52.8% of summed artifact build duration.
- Its `hipBLASLt` subproject alone took 3,202.7 seconds, or 53.38 minutes.
- Its `hipSPARSELt` subproject took 837.6 seconds, or 13.96 minutes.
- `hipSPARSELt` produced the latest artifact-owned build `END` marker at
  2026-08-14 00:38:02 UTC, about 31 seconds before the job completed.
- `blas` was directly affected in every sampled bump.

If the remaining tasks kept the same durations and scheduling, removing the
reusable artifact builds would not move the final build completion time because
the `blas` chain still finishes last. Real wall time could improve indirectly:
removing concurrent builds may give the remaining `blas` work more CPU, memory,
or I/O capacity. The existing logs do not quantify that contention effect.

Therefore:

- 13.8% is an average avoided-work estimate, not an expected 13.8% wall-time
  reduction.
- Zero minutes is the unchanged-schedule critical-path result, not a claim that
  freeing resources has no benefit.
- Actual wall-time savings lie between those interpretations and require an A/B
  run to measure.

## Conclusions

1. Fine-grained reuse triggers often under direct path matching, but dependency
   correctness removes more than half of those candidates.
2. The always-reusable tail is effectively free to build. Reusing only
   `libhipcxx` and `support` does not justify meaningful implementation
   complexity.
3. There is a potentially useful but intermittent middle tier:
   `prim`, `composable-kernel`, `fft`, and `hiptensor`.
4. The dominant artifact and observed critical path, `blas`, was invalidated
   in every sampled bump.
5. `miopen` is a concrete counterexample to direct-folder-only reasoning: its
   own source is untouched in half the sample, but its dependency cone changes
   every time.
6. Artifact-count reuse rates overstate value. Timing-weighted,
   dependency-aware reuse falls from 24.4% of artifact instances to 13.8% of
   summed measured work.
7. Even the timing-weighted percentage likely overstates wall-clock value
   because the reused work does not remove the final `blas` chain.

The current evidence does not support implementing broad fine-grained reuse on
the expectation of proportional wall-time savings. A narrower prototype may
still be worthwhile if it can reuse `prim` and `composable-kernel` with little
additional policy complexity, but it should be judged by measured job wall
time, not artifact counts or summed subproject duration alone.

## Recommendations

1. **Do not use direct-folder-only reuse as the correctness policy.** At a
   minimum, close over declared artifact dependencies.
2. **Fix the mapping source of truth before automation.** Reconcile
   `artifact_subprojects.json`, `BUILD_TOPOLOGY.toml`, CMake artifact producers,
   and the emitted artifact catalog.
3. **Instrument artifact scheduling directly.** Emit artifact start, end,
   elapsed time, dependency-wait time, and resource usage rather than inferring
   artifact totals from subproject logs.
4. **Run representative A/B experiments.** Select at least:
   - a negligible-reuse bump such as #7115, #7059, #6983, or #6908;
   - a favorable-reuse bump such as #6992 or #7117;
   - the latest bump #7258.
5. **Measure wall time and runner consumption separately.** Fine-grained reuse
   may reduce CPU work without reducing the final job completion time.
6. **Include copy, download, extraction, and artifact assembly overhead.** The
   `_build.log` analysis does not include those costs.
7. **Prefer a narrow optimization if complexity must be minimized.** The only
   material reusable targets in this sample are `prim`,
   `composable-kernel`, `fft`, and `hiptensor`; the always-reusable artifacts
   are too cheap to matter.

## Alternatives considered

### Preserve stage-level reuse only

This is the simplest model and aligns with issue #3399. It does not help
`rocm-libraries` bumps because the submodule change invalidates the math-libs
stage, but it avoids new dependency and mixed-baseline correctness rules.

### Reuse every directly untouched artifact

This produces the optimistic 24.0% average avoided-work result. It risks using
consumers built against stale headers, libraries, generated databases, or ABI
assumptions when their dependencies changed. `miopen` and `rocwmma` demonstrate
the scale of this difference.

### Reuse all dependency-aware candidates

This is the policy analyzed as safe in this report. It produces a 13.8%
average avoided-work estimate, but four bumps gain effectively nothing and the
observed critical path remains.

### Reuse only selected expensive, well-isolated artifacts

A smaller policy for `prim`, `composable-kernel`, `fft`, and `hiptensor` could
capture most favorable-case savings while limiting mapping complexity. It
still needs dependency closure, baseline validation, and A/B timing evidence.

## Appendix A: artifact-owned build logs

The links below point to the exact files whose final `END` duration was used.

| Artifact | Subproject log | Duration |
|---|---|---:|
| `blas` | [`hipBLAS-common_build.log`](https://therock-ci-artifacts.s3.amazonaws.com/31742388474-linux/logs/math-libs/gfx94X-dcgpu/hipBLAS-common_build.log) | 0.0s |
| `blas` | [`hipBLASLt_build.log`](https://therock-ci-artifacts.s3.amazonaws.com/31742388474-linux/logs/math-libs/gfx94X-dcgpu/hipBLASLt_build.log) | 3,202.7s |
| `blas` | [`hipBLAS_build.log`](https://therock-ci-artifacts.s3.amazonaws.com/31742388474-linux/logs/math-libs/gfx94X-dcgpu/hipBLAS_build.log) | 66.6s |
| `blas` | [`hipSOLVER_build.log`](https://therock-ci-artifacts.s3.amazonaws.com/31742388474-linux/logs/math-libs/gfx94X-dcgpu/hipSOLVER_build.log) | 38.6s |
| `blas` | [`hipSPARSELt_build.log`](https://therock-ci-artifacts.s3.amazonaws.com/31742388474-linux/logs/math-libs/gfx94X-dcgpu/hipSPARSELt_build.log) | 837.6s |
| `blas` | [`hipSPARSE_build.log`](https://therock-ci-artifacts.s3.amazonaws.com/31742388474-linux/logs/math-libs/gfx94X-dcgpu/hipSPARSE_build.log) | 38.8s |
| `blas` | [`origami_build.log`](https://therock-ci-artifacts.s3.amazonaws.com/31742388474-linux/logs/math-libs/gfx94X-dcgpu/origami_build.log) | 5.4s |
| `blas` | [`rocBLAS_build.log`](https://therock-ci-artifacts.s3.amazonaws.com/31742388474-linux/logs/math-libs/gfx94X-dcgpu/rocBLAS_build.log) | 249.9s |
| `blas` | [`rocRoller_build.log`](https://therock-ci-artifacts.s3.amazonaws.com/31742388474-linux/logs/math-libs/gfx94X-dcgpu/rocRoller_build.log) | 275.0s |
| `blas` | [`rocSOLVER_build.log`](https://therock-ci-artifacts.s3.amazonaws.com/31742388474-linux/logs/math-libs/gfx94X-dcgpu/rocSOLVER_build.log) | 429.8s |
| `blas` | [`rocSPARSE_build.log`](https://therock-ci-artifacts.s3.amazonaws.com/31742388474-linux/logs/math-libs/gfx94X-dcgpu/rocSPARSE_build.log) | 187.9s |
| `composable-kernel` | [`composable_kernel_build.log`](https://therock-ci-artifacts.s3.amazonaws.com/31742388474-linux/logs/math-libs/gfx94X-dcgpu/composable_kernel_build.log) | 1,119.7s |
| `fft` | [`hipFFT_build.log`](https://therock-ci-artifacts.s3.amazonaws.com/31742388474-linux/logs/math-libs/gfx94X-dcgpu/hipFFT_build.log) | 46.6s |
| `fft` | [`rocFFT_build.log`](https://therock-ci-artifacts.s3.amazonaws.com/31742388474-linux/logs/math-libs/gfx94X-dcgpu/rocFFT_build.log) | 455.3s |
| `hipblasltprovider` | [`hipblasltprovider_build.log`](https://therock-ci-artifacts.s3.amazonaws.com/31742388474-linux/logs/math-libs/gfx94X-dcgpu/hipblasltprovider_build.log) | 4.0s |
| `hipdnn-integration-tests` | [`hipdnn_integration_tests_build.log`](https://therock-ci-artifacts.s3.amazonaws.com/31742388474-linux/logs/math-libs/gfx94X-dcgpu/hipdnn_integration_tests_build.log) | 68.5s |
| `hipdnn-samples` | [`hipDNN_samples_build.log`](https://therock-ci-artifacts.s3.amazonaws.com/31742388474-linux/logs/math-libs/gfx94X-dcgpu/hipDNN_samples_build.log) | 59.5s |
| `hipdnn` | [`hipDNN_build.log`](https://therock-ci-artifacts.s3.amazonaws.com/31742388474-linux/logs/math-libs/gfx94X-dcgpu/hipDNN_build.log) | 198.6s |
| `hipkernelprovider` | [`hipkernelprovider_build.log`](https://therock-ci-artifacts.s3.amazonaws.com/31742388474-linux/logs/math-libs/gfx94X-dcgpu/hipkernelprovider_build.log) | 84.1s |
| `hiptensor` | [`hipTensor_build.log`](https://therock-ci-artifacts.s3.amazonaws.com/31742388474-linux/logs/math-libs/gfx94X-dcgpu/hipTensor_build.log) | 396.5s |
| `hipthreads` | [`hipthreads_build.log`](https://therock-ci-artifacts.s3.amazonaws.com/31742388474-linux/logs/math-libs/gfx94X-dcgpu/hipthreads_build.log) | 44.2s |
| `libhipcxx` | [`libhipcxx_build.log`](https://therock-ci-artifacts.s3.amazonaws.com/31742388474-linux/logs/math-libs/gfx94X-dcgpu/libhipcxx_build.log) | 9.3s |
| `miopen` | [`MIOpen_build.log`](https://therock-ci-artifacts.s3.amazonaws.com/31742388474-linux/logs/math-libs/gfx94X-dcgpu/MIOpen_build.log) | 174.8s |
| `miopenprovider` | [`miopenprovider_build.log`](https://therock-ci-artifacts.s3.amazonaws.com/31742388474-linux/logs/math-libs/gfx94X-dcgpu/miopenprovider_build.log) | 30.1s |
| `prim` | [`hipCUB_build.log`](https://therock-ci-artifacts.s3.amazonaws.com/31742388474-linux/logs/math-libs/gfx94X-dcgpu/hipCUB_build.log) | 263.8s |
| `prim` | [`rocPRIM_build.log`](https://therock-ci-artifacts.s3.amazonaws.com/31742388474-linux/logs/math-libs/gfx94X-dcgpu/rocPRIM_build.log) | <0.1s |
| `prim` | [`rocPRIM_tests_build.log`](https://therock-ci-artifacts.s3.amazonaws.com/31742388474-linux/logs/math-libs/gfx94X-dcgpu/rocPRIM_tests_build.log) | 523.9s |
| `prim` | [`rocThrust_build.log`](https://therock-ci-artifacts.s3.amazonaws.com/31742388474-linux/logs/math-libs/gfx94X-dcgpu/rocThrust_build.log) | 484.9s |
| `rand` | [`hipRAND_build.log`](https://therock-ci-artifacts.s3.amazonaws.com/31742388474-linux/logs/math-libs/gfx94X-dcgpu/hipRAND_build.log) | 13.1s |
| `rand` | [`rocRAND_build.log`](https://therock-ci-artifacts.s3.amazonaws.com/31742388474-linux/logs/math-libs/gfx94X-dcgpu/rocRAND_build.log) | 170.5s |
| `rocalution` | [`rocALUTION_build.log`](https://therock-ci-artifacts.s3.amazonaws.com/31742388474-linux/logs/math-libs/gfx94X-dcgpu/rocALUTION_build.log) | 50.4s |
| `rocwmma` | [`rocWMMA_build.log`](https://therock-ci-artifacts.s3.amazonaws.com/31742388474-linux/logs/math-libs/gfx94X-dcgpu/rocWMMA_build.log) | 563.4s |
| `support` | [`mxDataGenerator_build.log`](https://therock-ci-artifacts.s3.amazonaws.com/31742388474-linux/logs/math-libs/gfx94X-dcgpu/mxDataGenerator_build.log) | <0.1s |

## Appendix B: excluded shared helper build logs

The following 12 `_build.log` files were inspected but excluded from artifact
timing totals because they are common helper dependencies rather than uniquely
owned math/ML artifact work:

```text
therock-FunctionalPlus_build.log
therock-catch2_build.log
therock-eigen_build.log
therock-flatbuffers_build.log
therock-fmt_build.log
therock-frugally-deep_build.log
therock-googletest_build.log
therock-libdivide_build.log
therock-msgpack-cxx_build.log
therock-nlohmann-json_build.log
therock-spdlog_build.log
therock-yaml-cpp_build.log
```

Assisted-by: Codex
