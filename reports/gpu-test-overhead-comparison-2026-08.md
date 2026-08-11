# GPU Test Overhead Across Quick, Standard, and Comprehensive Runs

## Scope

This report compares three representative workflow runs:

- [TheRock run 31329423314](https://github.com/ROCm/TheRock/actions/runs/31329423314):
  `gfx94X-dcgpu`, quick filter.
- [rockrel run 31451903419](https://github.com/ROCm/rockrel/actions/runs/31451903419):
  nightly release, `gfx94X-dcgpu`, comprehensive filter, attempt 2.
- [rocm-libraries run 31016432598](https://github.com/ROCm/rocm-libraries/actions/runs/31016432598):
  postsubmit, standard filter, three hipsparse and three rocsparse shards on
  Linux gfx94X and Windows gfx1151.

The same definitions are used throughout:

- **Runner time:** job `completed_at - started_at`.
- **Test time:** duration of the top-level step named `Test`.
- **Overhead:** runner time minus test time.
- **Queue time:** job `started_at - created_at`, reported separately and not
  counted as runner occupancy.

GitHub Jobs API timestamps have one-second resolution. Failed jobs are included
in the raw totals. When a setup failure caused `Test` to be skipped, its runner
time is necessarily all overhead.

## Executive Comparison

| Run | Filter | Leaf test/shard jobs | Runner time | Test time | Test utilization | Median job utilization | Median queue |
|---|---|---:|---:|---:|---:|---:|---:|
| TheRock 31329423314 | quick | 50 | 6h 16m 14s | 3h 7m 59s | 50.0% | 33.1% | 30m 54s |
| rockrel 31451903419 | comprehensive | 87 | 39h 53m 10s | 17h 33m 8s | 44.0% | 37.2% | 35m 42s |
| rocm-libraries 31016432598 | standard, Linux + Windows | 12 | 3h 31m 47s | 37m 7s | 17.5% | 14.8% | 40s |

The raw data does not show progressively better aggregate utilization at the
larger filter levels. That does not mean batching is equally attractive in all
three cases. Each run is dominated by a different inefficiency:

- **Quick:** many legitimately short tests; batching compatible short tests is
  useful after avoiding unnecessarily broad artifact inputs.
- **Comprehensive:** long shards are more balanced, but cold container pulls,
  slow artifact setup, and setup timeouts dominate. Caching, image preparation,
  network throughput, and setup reliability should come first.
- **rocm-libraries standard:** an extra full rocm-libraries checkout for one
  notification script dominates both platforms. Sparse checkout or moving the
  script removes the largest problem without sacrificing shard parallelism.

## TheRock Quick Baseline

The prior report contains the full analysis. The key results are:

| Metric | Value |
|---|---:|
| Jobs | 50 |
| Runner time | 6h 16m 14s |
| Test time | 3h 7m 59s (50.0%) |
| Overhead | 3h 8m 15s (50.0%) |
| Container initialization | 1h 21m 7s (21.6%) |
| Environment setup | 1h 31m 57s (24.4%) |
| Jobs whose test was under one minute | 24 |
| Utilization of those 24 jobs | 9.9% |

This is the strongest batching case because many tests remain very short even
when they execute successfully. The recommended exact-environment BLAS pilot
would replace 11 jobs with three duration-balanced batches and is modeled to
save about 11-28 minutes in that subset, depending on how much setup remains.

## rockrel Comprehensive Run

### Aggregate results

| Metric | Value |
|---|---:|
| Leaf test/shard jobs | 87 |
| Components | 50 |
| Successful jobs | 75 |
| Failed jobs | 12 |
| Runner time | 39h 53m 10s |
| Test time | 17h 33m 8s (44.0%) |
| Overhead | 22h 20m 2s (56.0%) |
| Container initialization | 10h 21m 43s (26.0%) |
| Environment setup | 10h 55m 6s (27.4%) |
| Other overhead | 1h 3m 13s (2.6%) |
| Median runner time | 24m 51s |
| Median test time | 8m 30s |
| Median overhead | 13m 25s |
| Median queue time | 35m 42s |
| First test start to last completion | 3h 14m 35s |

Nine jobs never reached `Test`, typically after the environment setup step ran
for roughly its 15-minute timeout. Excluding those nine jobs, the 78 jobs that
started `Test` consumed 36h 54m 3s, of which 17h 33m 8s was testing: **47.6%
utilization**. The median setup cost among test-started jobs was still 6m 52s,
and median container initialization was 5m 2s.

This makes setup performance and reliability first-order correctness concerns,
not just cost optimizations. A test suite that never starts because artifact or
environment preparation times out provides no validation.

### Sharded versus unsharded components

| Group | Jobs | Runner time | Test time | Overhead | Utilization |
|---|---:|---:|---:|---:|---:|
| Multi-shard components | 49 | 25h 1m 31s | 12h 30m 26s | 12h 31m 5s | 50.0% |
| Single-shard components | 38 | 14h 51m 39s | 5h 2m 42s | 9h 48m 57s | 33.9% |

The longer multi-shard work is better amortized than the single-shard work, but
it still spends one minute on overhead for every minute testing. Combining
shards into fewer jobs would remove repeated setup but directly trades away
the parallelism that sharding was designed to provide. A shared immutable cache
or prepared worker image can retain that parallelism.

### Runner cohorts

| Cohort | Jobs | Runner time | Test time | Utilization |
|---|---:|---:|---:|---:|
| Common 1-GPU CSP | 64 | 24h 53m 22s | 8h 54m 7s | 35.8% |
| Other 1-GPU | 19 | 13h 39m 15s | 8h 5m | 59.2% |
| 8-GPU | 2 | 1h 15m 30s | 30m | 39.7% |
| CPU | 2 | 5m 3s | 4m 1s | 79.5% |

The large gap between the 1-GPU pools suggests that cache warmth, image pull
behavior, network path, or provisioning topology should be measured by runner
pool. Aggregate workflow data alone is not sufficient for the caching design.
`fetch_artifacts.py` already overlaps downloads and extraction with separate
thread pools, so "parallel downloads" should be treated as a measurement and
tuning problem: record compressed bytes, download throughput, decompression
CPU time, concurrency, and storage throughput before changing worker counts or
archive compression.

### Sharded component totals

| Component | Shards | Runner | Test | Overhead | Utilization | Failures |
|---|---:|---:|---:|---:|---:|---:|
| hipblaslt | 6 | 1h 55m 32s | 44m 42s | 1h 10m 50s | 38.7% | 1 |
| hipsparselt | 6 | 2h 23m 22s | 1h 0m 19s | 1h 23m 3s | 42.1% | 0 |
| rocblas | 6 | 2h 48m 38s | 1h 31m 46s | 1h 16m 52s | 54.4% | 0 |
| rocroller | 5 | 2h 40m 54s | 1h 57m 38s | 43m 16s | 73.1% | 2 |
| rocwmma | 5 | 1h 3m 1s | 1m 55s | 1h 1m 6s | 3.0% | 1 |
| hip-tests | 4 | 1h 46m 46s | 48m 57s | 57m 49s | 45.8% | 0 |
| miopen | 4 | 4h 36m 38s | 2h 59m 42s | 1h 36m 56s | 65.0% | 0 |
| hipsparse | 3 | 1h 32m 19s | 18m 40s | 1h 13m 39s | 20.2% | 0 |
| rocsolver | 3 | 1h 4m 31s | 26m 48s | 37m 43s | 41.5% | 0 |
| rocsparse | 3 | 2h 33m 18s | 1h 40m 1s | 53m 17s | 65.2% | 0 |
| hipfft | 2 | 1h 20m 48s | 43m 6s | 37m 42s | 53.3% | 0 |
| rocprim | 2 | 1h 15m 44s | 16m 52s | 58m 52s | 22.3% | 0 |

The results support selective rather than blanket batching. `rocroller`,
`miopen`, and `rocsparse` already obtain substantial value from parallel shards.
`rocwmma` and `hipsparse` deserve separate investigation: their shard counts do
not produce balanced useful work in this run.

### Failed jobs

Nine failures skipped `Test` after setup trouble: hipblaslt shard 6,
hipdnn_install, hipdnn-integration-tests, hipdnn-samples, hiptensor, rccl,
rocrand, rocroller shard 4, and rocwmma shard 5. Three additional jobs reached
and failed `Test`: rocprofiler-sdk, rocroller shard 1, and rocshmem.

Treating all 12 as normal performance samples would understate test utilization,
but excluding them entirely would hide a major infrastructure reliability and
capacity problem. Both raw and test-started figures are therefore reported.

### Complete per-component totals

| Component | Jobs | Runner | Test | Overhead | Test % | Container | Setup env | Failures |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| amdsmi | 1 | 11m 27s | 14s | 11m 13s | 2.0% | 3m 48s | 6m 56s | 0 |
| aqlprofile | 1 | 11m 38s | 2s | 11m 36s | 0.3% | 4m 16s | 6m 52s | 0 |
| hipblas | 1 | 20m 32s | 7m 38s | 12m 54s | 37.2% | 4m 36s | 7m 51s | 0 |
| hipblaslt | 6 | 1h 55m 32s | 44m 42s | 1h 10m 50s | 38.7% | 26m 2s | 41m 21s | 1 |
| hipblasltprovider | 1 | 11m 57s | 42s | 11m 15s | 5.9% | 3m 18s | 7m 24s | 0 |
| hipcub | 1 | 36m 55s | 9m 46s | 27m 9s | 26.5% | 16m 11s | 9m 50s | 0 |
| hipdnn | 1 | 18m 35s | 38s | 17m 57s | 3.4% | 12m 23s | 4m 45s | 0 |
| hipdnn_install | 1 | 18m 52s | 0s | 18m 52s | 0.0% | 3m 18s | 15m | 1 |
| hipdnn-integration-tests | 1 | 18m 15s | 0s | 18m 15s | 0.0% | 3m 23s | 14m 12s | 1 |
| hipdnn-samples | 1 | 19m 2s | 0s | 19m 2s | 0.0% | 3m 23s | 15m | 1 |
| hipfft | 2 | 1h 20m 48s | 43m 6s | 37m 42s | 53.3% | 25m 14s | 10m 45s | 0 |
| hipfile | 1 | 43s | 12s | 31s | 27.9% | 11s | 11s | 0 |
| hipkernelprovider | 1 | 9m 34s | 4s | 9m 30s | 0.7% | 1m 49s | 6m 41s | 0 |
| hiprand | 1 | 11m 11s | 3s | 11m 8s | 0.4% | 3m 29s | 7m 18s | 0 |
| hipsolver | 1 | 11m 10s | 44s | 10m 26s | 6.6% | 3m 44s | 6m 18s | 0 |
| hipsparse | 3 | 1h 32m 19s | 18m 40s | 1h 13m 39s | 20.2% | 43m 26s | 27m 20s | 0 |
| hipsparselt | 6 | 2h 23m 22s | 1h 0m 19s | 1h 23m 3s | 42.1% | 52m 12s | 27m 35s | 0 |
| hiptensor | 1 | 22m 34s | 0s | 22m 34s | 0.0% | 6m 44s | 15m | 1 |
| hip-tests | 4 | 1h 46m 46s | 48m 57s | 57m 49s | 45.8% | 12m 49s | 43m 17s | 0 |
| hipthreads | 1 | 15m 8s | 4m 20s | 10m 48s | 28.6% | 3m 43s | 6m 32s | 0 |
| hipthreads_examples | 1 | 27m 41s | 28s | 27m 13s | 1.7% | 16m 39s | 9m 21s | 0 |
| libhipcxx_amdclang | 1 | 24m 51s | 12m 27s | 12m 24s | 50.1% | 4m 32s | 7m 28s | 0 |
| libhipcxx_hiprtc | 1 | 16m 49s | 7m 28s | 9m 21s | 44.4% | 5m 2s | 3m 53s | 0 |
| miopen | 4 | 4h 36m 38s | 2h 59m 42s | 1h 36m 56s | 65.0% | 55m 8s | 38m 51s | 0 |
| miopenprovider | 1 | 24m 12s | 12m 12s | 12m | 50.4% | 7m 50s | 3m 44s | 0 |
| origami | 1 | 32m 20s | 1s | 32m 19s | 0.1% | 18m 34s | 12m 33s | 0 |
| rccl | 1 | 33m 11s | 0s | 33m 11s | 0.0% | 18m 13s | 14m 5s | 1 |
| rocalution | 1 | 9m 46s | 2m 26s | 7m 20s | 24.9% | 2m 43s | 4m 15s | 0 |
| rocblas | 6 | 2h 48m 38s | 1h 31m 46s | 1h 16m 52s | 54.4% | 30m 38s | 43m 20s | 0 |
| rocdecode | 1 | 15m 42s | 2m 36s | 13m 6s | 16.6% | 5m 4s | 7m 32s | 0 |
| rocfft | 1 | 1h 24m 47s | 55m 36s | 29m 11s | 65.6% | 17m 7s | 10m 43s | 0 |
| rocgdb-cpu | 1 | 4m 20s | 3m 49s | 31s | 88.1% | 8s | 14s | 0 |
| rocgdb-gpu | 1 | 28m 48s | 16m 12s | 12m 36s | 56.2% | 4m 58s | 7m 16s | 0 |
| rocjpeg | 1 | 12m 5s | 31s | 11m 34s | 4.3% | 3m 26s | 7m 44s | 0 |
| rocprim | 2 | 1h 15m 44s | 16m 52s | 58m 52s | 22.3% | 35m 29s | 18m 48s | 0 |
| rocprofiler-compute | 1 | 1h 6m 25s | 43m 57s | 22m 28s | 66.2% | 13m 49s | 6m 50s | 0 |
| rocprofiler-sdk | 1 | 40m 26s | 15m | 25m 26s | 37.1% | 5m 26s | 12m 8s | 1 |
| rocprofiler-systems | 1 | 45m 55s | 21m 50s | 24m 5s | 47.5% | 16m 15s | 6m 46s | 0 |
| rocrand | 1 | 21m 22s | 0s | 21m 22s | 0.0% | 5m 41s | 15m | 1 |
| rocr-debug-agent | 1 | 12m 54s | 22s | 12m 32s | 2.8% | 4m 25s | 7m 40s | 0 |
| rocroller | 5 | 2h 40m 54s | 1h 57m 38s | 43m 16s | 73.1% | 16m 46s | 24m 10s | 2 |
| rocrtst | 1 | 15m 4s | 3m 21s | 11m 43s | 22.2% | 2m 12s | 9m 8s | 0 |
| rocshmem | 1 | 42m 19s | 30m | 12m 19s | 70.9% | 8m 9s | 3m 43s | 1 |
| rocsolver | 3 | 1h 4m 31s | 26m 48s | 37m 43s | 41.5% | 15m 30s | 20m 51s | 0 |
| rocsparse | 3 | 2h 33m 18s | 1h 40m 1s | 53m 17s | 65.2% | 34m 29s | 16m 50s | 0 |
| rocthrust | 1 | 18m 20s | 6m 17s | 12m 3s | 34.3% | 4m 38s | 7m | 0 |
| rocwmma | 5 | 1h 3m 1s | 1m 55s | 1h 1m 6s | 3.0% | 16m 2s | 42m 6s | 1 |
| rpp | 1 | 50m 39s | 38m 7s | 12m 32s | 75.3% | 8m 53s | 3m 13s | 0 |
| sanity | 1 | 8m 47s | 3s | 8m 44s | 0.6% | 5m 32s | 2m 56s | 0 |
| tensilelite | 1 | 17m 23s | 5m 36s | 11m 47s | 32.2% | 4m 26s | 6m 50s | 0 |

## rocm-libraries Standard Run

### Aggregate and platform split

| Scope | Jobs | Runner | Test | Overhead | Utilization |
|---|---:|---:|---:|---:|---:|
| Combined | 12 | 3h 31m 47s | 37m 7s | 2h 54m 40s | 17.5% |
| Linux gfx94X | 6 | 2h 46m 50s | 23m | 2h 23m 50s | 13.8% |
| Windows gfx1151 | 6 | 44m 57s | 14m 7s | 30m 50s | 31.4% |

The overhead breakdown is:

| Scope | Runner init | Checkout/fetch | Setup environment | Other |
|---|---:|---:|---:|---:|
| Combined | 7m 36s | 2h 19m 50s | 23m 57s | 3m 17s |
| Linux | 7m 34s | 1h 54m 25s | 20m 53s | 58s |
| Windows | 2s | 25m 25s | 3m 4s | 2m 19s |

Of the 2h 19m 50s checkout total, **2h 17m 58s** came from the step named
`Checkout rocm-libraries repository for scripts`. The other repository fetches
and checkouts totaled only 1m 52s.

At the run's commit, that step performed a normal checkout of the current
rocm-libraries repository into `rocm-libraries/`. Its only subsequent use in
the workflow was:

```text
rocm-libraries/.github/scripts/notify_teams.py
```

The current local workflow retains the same full checkout. Sparse-checking out
`.github/scripts`, moving the notification helper into the already-checked-out
TheRock `build_tools`, packaging it as an action, or running notification in a
separate failure-only job should remove most of this cost.

If only that full scripts checkout is removed and every other measured cost
stays constant, modeled utilization becomes:

| Scope | Current | Without full scripts checkout |
|---|---:|---:|
| Combined | 17.5% | 50.3% |
| Linux gfx94X | 13.8% | 43.2% |
| Windows gfx1151 | 31.4% | 68.6% |

That change preserves all six-way shard parallelism. It should be preferred to
batching the shards merely to avoid repeated full checkouts.

### Per-component totals

| Platform/component | Shards | Runner | Test | Overhead | Utilization | Checkout | Setup env |
|---|---:|---:|---:|---:|---:|---:|---:|
| Linux hipsparse | 3 | 1h 20m 15s | 9m 7s | 1h 11m 8s | 11.4% | 56m 3s | 11m 2s |
| Linux rocsparse | 3 | 1h 26m 35s | 13m 53s | 1h 12m 42s | 16.0% | 58m 22s | 9m 51s |
| Windows hipsparse | 3 | 20m 7s | 2m 20s | 17m 47s | 11.6% | 15m 14s | 1m 28s |
| Windows rocsparse | 3 | 24m 50s | 11m 47s | 13m 3s | 47.4% | 10m 11s | 1m 36s |

### Per-shard results

| Platform | Component | Shard | Runner | Test | Overhead | Init | Checkout | Setup env | Test % |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Linux gfx94X | hipsparse | 1/3 | 27m 36s | 1m 55s | 25m 41s | 1m 34s | 21m 3s | 2m 55s | 6.9% |
| Linux gfx94X | hipsparse | 2/3 | 23m 25s | 3m 37s | 19m 48s | 44s | 14m 31s | 4m 21s | 15.4% |
| Linux gfx94X | hipsparse | 3/3 | 29m 14s | 3m 35s | 25m 39s | 1m 13s | 20m 29s | 3m 46s | 12.3% |
| Linux gfx94X | rocsparse | 1/3 | 30m 6s | 4m 17s | 25m 49s | 37s | 22m 18s | 2m 44s | 14.2% |
| Linux gfx94X | rocsparse | 2/3 | 30m 21s | 4m 41s | 25m 40s | 1m 15s | 20m 46s | 3m 31s | 15.4% |
| Linux gfx94X | rocsparse | 3/3 | 26m 8s | 4m 55s | 21m 13s | 2m 11s | 15m 18s | 3m 36s | 18.8% |
| Windows gfx1151 | hipsparse | 1/3 | 8m 27s | 1m 6s | 7m 21s | 0s | 6m 18s | 33s | 13.0% |
| Windows gfx1151 | hipsparse | 2/3 | 7m 8s | 36s | 6m 32s | 0s | 5m 51s | 26s | 8.4% |
| Windows gfx1151 | hipsparse | 3/3 | 4m 32s | 38s | 3m 54s | 0s | 3m 5s | 29s | 14.0% |
| Windows gfx1151 | rocsparse | 1/3 | 7m 38s | 3m 11s | 4m 27s | 0s | 3m 48s | 26s | 41.7% |
| Windows gfx1151 | rocsparse | 2/3 | 9m 4s | 3m 32s | 5m 32s | 1s | 4m 30s | 34s | 39.0% |
| Windows gfx1151 | rocsparse | 3/3 | 8m 8s | 5m 4s | 3m 4s | 1s | 1m 53s | 36s | 62.3% |

The standard tests themselves take roughly 1-5 minutes per shard. Batching all
three shards per component could amortize setup, but after the checkout defect
is removed it would serialize 9-14 minutes of Linux test work that currently
runs in parallel. Runner-side caches and prepared images are a better fit.

## Strategy by Filter Level

### Quick

Prioritize:

1. Exact artifact selection.
2. Exact-environment batching for short tests.
3. Container and environment caching.

Many tests are intrinsically too short to amortize even a healthy one-minute
setup, so batching remains valuable after infrastructure improvements.

### Standard

Prioritize:

1. Remove workflow-specific pathological overhead such as the full
   rocm-libraries scripts checkout.
2. Cache container layers, archives, extracted artifacts, and prepared
   environments.
3. Improve download and decompression concurrency/throughput.
4. Batch only sub-minute or persistently underutilized components after the
   corrected baseline is measured.

### Comprehensive

Prioritize:

1. Make setup reliable enough that all tests start.
2. Measure and improve image pull, artifact download, decompression, and
   flattening by runner pool.
3. Reuse immutable environments across shards while retaining shard
   parallelism.
4. Audit shard balance for components such as rocwmma, hipsparse, and rocprim.
5. Batch only short single-shard components or demonstrably undersized shards.

## Conclusion

The hypothesis is directionally correct after correcting obvious workflow and
infrastructure defects:

- Quick tests have a structural per-job granularity problem, so batching can
  remain important even with warm setup.
- Standard and comprehensive tests benefit more from sharing cached inputs and
  improving setup throughput while preserving shard parallelism.

However, the raw examples are not currently healthy baselines. The
rocm-libraries checkout consumes 65% of all runner time, and the comprehensive
run loses over 21 runner-hours to container/environment setup with nine tests
never starting. Fixing those issues should precede final batch-size or remote
scheduler decisions.

Assisted-by: Codex
