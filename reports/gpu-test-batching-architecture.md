# GPU Test Batching Architecture Options

See https://github.com/ROCm/TheRock/issues/7272

## Recommendation

Use a phased design with one shared execution-plan schema:

1. First reduce avoidable setup in the existing one-job-per-test architecture:
   target artifact selection, add phase metrics, preload container images, and
   prototype the persistent artifact cache proposed in
   [TheRock #3674](https://github.com/ROCm/TheRock/issues/3674).
2. Add GitHub-native batching for tests with exactly compatible environments.
   Start with three runtime-balanced batches for the 11 tests that use
   `--blas --tests` on the common 1-GPU runner.
3. If the remaining scale justifies it, let a remote test service consume the
   same execution-plan records. Do not make a Bazel remote-execution migration
   a prerequisite for the first two phases.

This retains a low-risk path to meaningful savings while making the planning
work reusable by a future external scheduler.

## Current Architecture

The current flow has three distinct responsibilities:

1. `determine_rocm_test_dependencies.py` walks the committed consumer graph and
   emits a set of project/test keys.
2. `fetch_test_configurations.py` filters the test catalog, expands test type
   and shard configuration, selects runner labels, constructs container
   options, and emits `sanity_component` plus `components` JSON.
3. `test_artifacts.yml` gates the component fan-out on a dedicated sanity job,
   then expands `components` into reusable `test_component.yml` workflows. The
   reusable workflow expands each component's shards into separate jobs.

Dependency selection should remain independent of batching. Batching is an
execution-planning concern and belongs after the selected component records
have been created.

The component records already contain most compatibility inputs a planner
needs:

- platform and build variant
- runner pool and GPU count
- container image and options
- artifact-selection flags
- additional requirements
- test command and timeout
- shard count
- expected-failure and benchmark metadata

## Immediate Artifact-Selection Finding

`hip-tests` and `rocprofiler-sdk` currently specify only:

```text
--tests
```

In `install_rocm_from_artifacts.py`, `args.tests` affects whether `_test`
archives are added for a selected component family, but it is not itself a
component-family selector. With no other selector, the script deliberately
passes no include patterns to `fetch_artifacts.py`. That means all artifacts
are selected.

A dry-run against run 31329423314's Linux `gfx94X-dcgpu`/`gfx942` artifact set
showed:

| Selection | Archive count |
|---|---:|
| Current `--tests` behavior | 266 |
| Candidate hip-tests base + `core-hiptests_test` | 18 |
| Existing `--rocprofiler-sdk --tests` selector | 21 |

Archive count is not byte size, and the candidate hip-tests set has not been
validated by running the test. Still, this is likely the best first audit:

- Change rocprofiler-sdk to the already-supported
  `--rocprofiler-sdk --tests` selection if its test dependencies validate.
- Add an explicit hip-tests selector that includes its test archive and exact
  runtime dependencies.
- Compare installed manifests and execute the full/quick test variants before
  landing either change.

## Options

Complexity estimates are rough one-engineer implementation and rollout ranges,
not commitments.

| Option | Complexity | Potential gain | Main trade-off |
|---|---|---|---|
| Target artifact sets and instrument phases | Small, days | Potentially large for the two all-artifact jobs; enables trustworthy estimates elsewhere | Dependency omissions can make tests fail or, worse, silently skip |
| Preload container layers | Small/medium, 1-3 weeks depending on runner ownership | Addresses part of the 1h 21m container initialization measured in the sample run | Specialized images and ephemeral/DinD runner topology complicate cache placement |
| Content-addressed artifact/environment cache | Medium/large, 2-6 weeks | Addresses part of the 1h 32m setup-environment total while retaining per-test jobs | Cache integrity, concurrency, eviction, and writable-prefix isolation |
| Exact-environment GitHub-native batches | Medium, 2-4 weeks | About 10-25% whole-run runner reduction initially; 28m modeled for the 11-job BLAS group in the sample | Reruns and check status occur at batch granularity |
| Adaptive cross-artifact batching | Large, 1-2 months | Could approach 20-35% whole-run reduction if artifact unions remain efficient | More planner policy, state leakage, artifact bloat, and critical-path risk |
| Remote test scheduler using current scripts | Extra large, multi-month | Can approach the observed 50% overhead ceiling with warm workers and dense scheduling | New service, scheduler, result UI, security, cancellation, and operational burden |
| Bazel plus GPU-aware remote execution | Extra large, likely multi-quarter | Similar scheduling ceiling plus broader hermetic-build benefits | Current Python/CTest/pytest tests are not Bazel actions; GPU and multi-GPU resource scheduling is executor-specific |

## Option 1: Preserve Per-Test Jobs and Make Them Warm

This option keeps native GitHub logs, checks, and individual job reruns.

### Container cache

The hip-tests log from run 31329423314 shows a full image pull occupying nearly
the entire 60-second container-initialization step. Preload pinned images into
the runner/node image or use a runner image that already provides the test
environment. Measure cold-pull rate and p50/p95 initialization separately for
the default and specialized images.

### Artifact cache

The existing download helper skips a download when its destination archive
already exists, but the test installer deletes the output directory before
every install and downloaded archives are normally deleted after extraction.
The current behavior therefore does not provide a cross-job cache.

A durable cache should be outside the job workspace:

```text
THEROCK_RUNNER_CACHE_ROOT/
  archives/<backend-object-identity>/archive
  extracted/<archive-digest>/<extractor-version>/...
  environments/<sorted-artifact-digests>/<flattener-version>/...
```

Required properties:

- content or backend ETag/size validation, not existence-only validation
- lock files plus write-to-temp and atomic rename
- bounded LRU/age eviction
- immutable cache entries
- job-local writable materialization via reflink, copy, overlay, or another
  copy-on-write mechanism
- cache keys that include platform, GPU targets, artifact identity, and
  extraction/flattening implementation version

Do not let multiple tests mutate one shared flattened directory. Several tests
create CTest state, compile examples, or otherwise write under the current
workspace.

## Option 2: GitHub-Native Exact-Environment Batches

This is the recommended first architectural batching experiment.

### Planner location

Refactor `fetch_test_configurations.py` into pure phases:

```text
selected project keys
  -> selected component configs
  -> shard-level TestUnit records
  -> compatible TestBatch records + standalone TestUnit records
```

`determine_rocm_test_dependencies.py` remains unchanged.

Suggested records:

```text
TestUnit
  id                         # rocblas/shard-1-of-6
  component
  shard_index / total_shards
  test_script / timeout
  test_type / expected failure
  artifact features
  additional requirements
  estimated duration
  isolation policy

TestBatch
  id
  compatibility key
  runner capability selector
  container image/options
  artifact feature union
  units[]
  timeout
```

Prefer normalized artifact features over opaque shell strings in the long-term
schema. The first pilot can require exact `fetch_artifact_args` equality.

### Compatibility key

The pilot should batch only records matching all of:

- platform and build variant
- CPU, 1-GPU, or multi-GPU capability
- runner pool/capability class
- container image and container options
- exact artifact-selection flags
- exact additional-requirements set
- sanitizer/backend mode
- isolation class

Batch before choosing a concrete weighted runner label, then make one weighted
selection per batch. Grouping after the current per-component random selection
would fragment otherwise compatible tests and make batches non-deterministic.

Keep these standalone initially:

- CPU-only tests
- multi-GPU tests
- benchmarks
- expected failures and known flakes
- specialized privileged/debugger/profiler/media images
- tests known to mutate global GPU or artifact-prefix state
- units whose estimated runtime already meets the batch target

### Batch sizing

Use duration-balanced bins, not a fixed number of tests. A reasonable pilot
target is 6-10 minutes of test work and at most four component slots per batch.
Apply longest-processing-time-first assignment within a compatibility group.

The 11 sample-run tests with `--blas --tests` are a natural pilot:

| Metric | Current 11 jobs | Three balanced batches, modeled |
|---|---:|---:|
| Test time | 19m 41s | 19m 41s |
| Runner time | 58m 34s | about 30m 17s |
| Test utilization | 33.6% | about 65.0% |
| Runner time saved | - | about 28m 17s |

The model assumes the identical artifact/environment setup is paid once per
batch at the group's observed mean. A deliberately conservative model that
assumes none of the environment-setup time is removed still saves about 11m.

Three balanced bins also preserve useful parallelism: the observed test times
can be divided into bins of roughly 6m25s-6m42s each.

### Workflow shape

Have the configuration job output two arrays:

```text
standalone_components
batches
```

Keep the existing `test_components` reusable-workflow path for standalone
records. Add a parallel `test_batches` matrix invoking a new
`test_batch.yml` reusable workflow.

For a maximum batch size of four, use four static test slots in the reusable
workflow. Each slot:

- is conditional on a unit existing
- runs as its own GitHub step, preserving a foldable log section
- uses `continue-on-error: true`
- writes a structured result and JUnit/log artifact
- runs GPU cleanup in an `always()` step before the next slot

An always-running final step evaluates all slot outcomes and fails the batch if
any non-expected unit failed. Static slots are repetitive, but they preserve
much better GitHub UI behavior than one opaque dynamic loop and avoid the fact
that GitHub Actions cannot dynamically generate steps at runtime.

### Failure and retry semantics

- `Re-run failed jobs` reruns the batch, not one component.
- Existing `test_labels` or `workflow_dispatch` can still select a single
  component for a targeted rerun.
- A flaky component should be marked standalone or given an automatic
  unit-level retry policy.
- Continue after unit failures so one failure does not suppress later tests.
- Preserve a reproduction command and separate log/JUnit file for every unit.

Keep the current dedicated sanity gate during the first batching rollout so
only one architectural semantic changes at a time. Once batching is stable,
test replacing the dedicated gate with a batch-local sanity preflight; the
sample sanity job spent 26m53s on setup for a 3-second test and delayed creation
of all downstream jobs.

## Option 3: Adaptive Cross-Artifact Batches

After exact-environment batching, allow a batch to use the union of compatible
artifact feature sets. This can absorb more of the 20 sub-minute common-runner
tests identified in the sample.

The planner needs estimated artifact bytes and setup cost, not just test
duration. Its objective becomes multi-dimensional:

```text
minimize runner setup + test time
subject to runner/image compatibility,
           maximum batch test duration,
           maximum artifact-union bytes,
           maximum failure-domain size
```

This requires the installer to resolve feature flags into an explicit artifact
manifest before scheduling. Otherwise the planner cannot know whether combining
two components adds no files or hundreds of archives.

Main risks are larger prefixes, dependency conflicts, writable state leakage,
and accidental serialization of tests that currently finish in parallel.

## Option 4: Remote Test Scheduling

A coordinator GitHub job could submit `TestUnit` records to a GPU-aware service,
wait for completion, publish a job summary, and upload per-unit logs and JUnit
results. GPU workers could retain prepared images and immutable artifact caches
and schedule units densely.

This is a credible end state if GPU demand and queue pressure justify owning a
service. Design the `TestUnit` schema and result format during GitHub-native
batching so the service can reuse them.

The service must provide:

- resource matching for GPU family/count, CPU, memory, image, and privileges
- leases, heartbeats, cancellation, timeouts, and orphan recovery
- per-unit isolation and cleanup
- authenticated artifact access and result integrity
- log streaming and durable per-unit logs/JUnit
- retry policy and a targeted retest API
- quotas, fairness, metrics, and worker/cache health

Separate GitHub Check Runs can be created per unit with a GitHub App if native
visibility is important, but the built-in job rerun button still cannot rerun a
remote unit. A slash command, check action, or workflow-dispatch input would be
needed.

### Bazel versus a thin scheduler

Bazel remote execution is attractive when tests are already hermetic Bazel
actions with declared inputs. The current tests are Python drivers over CTest,
pytest, installed ROCm prefixes, privileged containers, and sometimes multiple
GPUs. Converting them into correct remote actions and finding or extending an
executor with the required GPU resource model is a much larger project than
adding scheduling.

If remote scheduling is pursued primarily for test efficiency, start with a
thin service that runs the existing `TestUnit` command in prepared containers.
Adopt Bazel RE only if TheRock also wants the broader hermetic build/test and
content-addressed execution model.

## Phased Rollout

### Phase 0: measurement and input reduction

- Add sub-phase timings and byte counts to setup.
- Audit the two all-artifact `--tests` configurations.
- Collect at least 10 representative runs.
- Preload the default image on one runner pool for an A/B comparison.

### Phase 1: cache

- Add archive-cache support with validation and atomic writes.
- Then add extracted/environment cache layers if archive hits are insufficient.
- Measure hit rate and p50/p95 setup improvement.

### Phase 2: exact BLAS batching

- Add `TestUnit`/`TestBatch` planning and three BLAS batches.
- Keep all other components and sanity on the existing path.
- Compare runner time, wall time, queue time, failure diagnosis, and rerun cost.

### Phase 3: broader planning

- Add more exact-environment groups.
- Add historical duration input and stable bin packing.
- Consider artifact unions and batch-local sanity only after the pilot data.

### Phase 4: remote scheduling decision

- Recalculate the remaining avoidable GPU capacity after filtering, caching,
  and GitHub-native batching.
- Build a remote-service prototype only if that remaining capacity and queue
  latency justify its ongoing operational cost.

## Alternatives Considered

### Put all tests in one GitHub job

This maximizes setup amortization but creates a long critical path, a large
failure domain, and expensive reruns. It also mixes CPU, 1-GPU, 8-GPU, and
special-image requirements. It is not recommended.

### Batch only by component count

Equal-sized batches can have badly imbalanced duration and incompatible
artifact/image requirements. Use compatibility constraints and duration bins.

### Implement batching in dependency selection

The consumer graph answers what should run; batching answers where and with
what other tests it should run. Combining them would make both policy layers
harder to test and reuse.

### Wait for a full remote-execution architecture

The measured setup waste is large enough to act on now, and the proposed unit
manifest makes GitHub-native work reusable by a future service.

Assisted-by: Codex
