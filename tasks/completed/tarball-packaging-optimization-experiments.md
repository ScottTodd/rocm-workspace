# Multi-architecture tarball packaging optimization evidence

## Purpose and scope

This document records the investigation, experiments, implementation decisions,
validation, and follow-up questions behind the tarball packaging optimization
stack on `ROCm/TheRock` branch
`users/scotttodd/tarball-optimize-4`.

The reviewed range is:

```text
base: c04a9dd6dd6c3f7f5430bc64866640ffc2b213cb
head: 91a7a9338daac3febc2ac97a0ffe0e2933e8adc6
```

The work was motivated by
[ROCm/TheRock issue 7584](https://github.com/ROCm/TheRock/issues/7584).
Release publication intentionally waits for all ROCm package forms so that an
incomplete release is not published. This makes the slowest packaging job the
critical path. The goal here was to reduce that critical path without weakening
the aggregate completeness check or changing the user-facing `.tar.gz` format.

This report is deliberately more detailed than a PR description. It is intended
to preserve the evidence and reasoning needed to review, maintain, or revisit
the optimization.

### Surrounding workflow decisions and non-goals

The investigation began while correcting release-workflow dependencies in
[PR 7598](https://github.com/ROCm/TheRock/pull/7598). That change is the base of
this branch, not part of the optimization diff reviewed here.

The broader discussion reached two scope decisions:

- Keep the common `publish_to_release_buckets` completeness gate. Publishing a
  partial release earlier would reduce latency but weaken protection against an
  incomplete user-facing release.
- Treat building framework wheels, publishing those wheels, and testing them as
  separable future workflow stages. PyTorch/JAX artifact-index versus release-
  index behavior was not changed in this tarball optimization stack.

The work therefore focused on making the slow aggregate prerequisite cheaper,
not bypassing it.

## Original bottleneck

A representative release workflow showed:

| Packaging job | Duration |
|---|---:|
| Python packages | 13m28s |
| Tarballs | 1h21m24s |
| Native DEB packages | 49m51s |
| Native RPM packages | 17m47s |

The ASan release case was substantially worse:

| Packaging job | Duration |
|---|---:|
| Python packages | 1h38m56s |
| Tarballs | 4h03m24s |
| Native DEB packages | 1h39m36s |
| Native RPM packages | 1h15m48s |

Related ASan packaging investigations are tracked in
[issue 6775](https://github.com/ROCm/TheRock/issues/6775) and
[issue 6454](https://github.com/ROCm/TheRock/issues/6454).

Native package work in
[PR 7380](https://github.com/ROCm/TheRock/pull/7380) independently optimizes
DEB/RPM construction. That makes tarball optimization more important, because
otherwise the release aggregate simply shifts more decisively to waiting on
tarballs.

## Optimization stack

The branch contains five commits:

| Commit | Change | Intended effect |
|---|---|---|
| `e30726e49` | Cache extracted artifacts for tarball staging | Decompress each artifact once and hardlink it into every family/multiarch staging tree. |
| `756bfdd82` | Parallelize tarball compression with zlib-ng | Use multiple threads inside each gzip stream while retaining `.tar.gz` compatibility. |
| `b72d9e066` | Prioritize large tarball compression tasks | Start multiarch and test archives first so smaller work can fill the tail. |
| `3a25e6c79` | Fail when artifact fetch finds no matches | Report the real input-selection failure instead of failing later on a missing staging directory. |
| `91a7a9338` | Use level 9 tarball compression | Recover and slightly improve system-gzip archive size while keeping tarballs off the critical path. |

### Extraction cache design

Before this change, generic artifacts were downloaded once but decompressed
again for each per-family tree and again for the multiarch trees. ASan artifacts
are unusually large, making redundant decompression and file copies especially
expensive.

The new cache:

1. Extracts an archive into a cache directory using the existing
   `ArtifactPopulator` behavior.
2. Writes `artifact_manifest.txt` last; the manifest is the completion marker.
3. Reuses the exploded artifact directory on subsequent flatten operations.
4. Uses the existing `PatternMatcher` hardlink-first behavior to avoid copying
   regular-file data. Cross-device hardlink failures fall back to copies.
5. Requires flattened outputs to remain read-only while the cache is active,
   because outputs can share inodes with cached files.

The cache lives under the tarball job's `.work` directory. It is shared across
the sequential family and multiarch staging passes in one invocation.

### Compression design

The system `tar` process still constructs the tar byte stream. Its stdout is
piped into `zlib_ng.gzip_ng_threaded`, preserving the `.tar.gz` format expected
by existing users and tooling.

The defaults at the final head are:

```text
backend: zlib-ng
compression level: 9
threads per archive: 8
archive workers: automatic
```

Automatic worker count is:

```text
min(task count, max(1, available CPUs // (compression threads + 1)))
```

The extra CPU per archive represents the concurrent `tar` producer. Linux CPU
affinity is used when available, so a runner constrained to fewer CPUs does not
size the pool from the host's unconstrained count.

The system-gzip backend and explicit worker/thread options remain available for
A/B measurements and troubleshooting.

### Scheduling design

Tasks use coarse semantic priorities:

```text
multiarch tests > multiarch > family tests > family
```

This avoids an additional directory walk or maintained size estimate. The
observed archives follow that size order: multiarch tests are the largest,
followed by multiarch runtime/development content, family test archives, and
regular family archives. Starting the largest expected work first reduces the
chance that a single large archive extends the end of the job after workers
become idle.

## Experiment methodology

### General CI controls

Paired CI experiments used the same input artifact workflow run and the same
target-family selection. Both regular and test tarballs were enabled. Runs used
the `aws-linux-scale-rocm-prod` runner label; the observed runners exposed 96
CPUs to the job.

For the full non-ASan comparison, all 16 Linux AMDGPU target families were used:

```text
gfx94X-dcgpu;gfx110X-all;gfx1151;gfx120X-all;gfx90a;gfx950-dcgpu;
gfx900;gfx90c;gfx906;gfx908;gfx101X-dgpu;gfx103X-all;gfx1150;
gfx1152;gfx1153;gfx125X-dcgpu
```

Input workflow run: `32843555429`.

For the ASan comparison, `gfx94X-dcgpu` was used with input workflow run
`31754588494`. The historical 4h03m ASan observation and the controlled
gfx94X-only baseline are not identical scopes; the controlled pair is used for
before/after calculations.

The first full-stack experiments accidentally requested the `ci` artifact
bucket even though their input runs had `dev` artifacts. Those failures are
documented below and were replaced with runs using the correct release type.

### Phase timing extraction

The Python script logs three stable markers:

```text
Building tarballs for ...
Compressing N tarballs ...
Done. Tarballs in ...
```

The intervals used below are:

- **Staging:** first marker to compression marker.
- **Compression:** compression marker to done marker.
- **Script total:** first marker to done marker.

GitHub step durations include shell and process startup around those markers;
whole-job duration also includes checkout, dependency installation, credential
setup, and upload. The script intervals isolate the code being optimized.

Logs and metadata were retrieved with authenticated GitHub CLI calls, for
example:

```powershell
gh api "repos/ROCm/TheRock/actions/runs/<RUN_ID>/jobs?per_page=100&page=1"
gh api `
  -H "Accept: application/vnd.github+json" `
  -H "X-GitHub-Api-Version: 2026-03-10" `
  repos/ROCm/TheRock/actions/jobs/<JOB_ID>/logs
```

### Local compression microbenchmark

Local compression experiments ran on Windows with 32 available CPUs. The input
was a cached `amd-llvm` development staging tree containing 4,098 regular files
and 1.15 GiB of logical file data. The same staged directory was compressed
repeatedly. System gzip was warmed and zlib-ng used eight threads for the level
sweep.

A concurrent source build was sometimes active on the same system, so local
timings were treated as directional. Full-scale CI results, not the local
microbenchmark alone, determined the final setting.

### Archive correctness comparison

Correctness was checked at three levels:

1. Unit/integration tests constructed real artifacts and verified contents,
   executable bits, hardlink groups, symlinks, and reuse after deleting the
   original compressed archive.
2. A local direct-versus-cached tree comparison inventoried entry kinds, sizes,
   permissions, symlink targets, and hardlink groups, then byte-compared every
   regular file.
3. A remote baseline-versus-optimized `gfx90c` tarball comparison streamed both
   complete archives. For each tar member it recorded type, size, mode,
   ownership, names, mtime, link target, device metadata, PAX headers, and a
   SHA-256 digest of every regular-file payload.

The remote comparison used the `gfx90c` tarball from baseline run `32843555429`
and level-6 optimized run `32903348931`. It was chosen because it was the
smallest family archive while still containing a complete ROCm install tree.

## Results

### Extraction cache isolation: four-family experiment

The first pair kept system gzip unchanged to isolate extraction reuse:

- [Baseline run 32788407121](https://github.com/ROCm/TheRock/actions/runs/32788407121)
- [Extraction-cache run 32788431419](https://github.com/ROCm/TheRock/actions/runs/32788431419)

Both used `gfx94X-dcgpu;gfx110X-all;gfx1151;gfx120X-all` and built ten archives
including test and multiarch variants.

| Phase | Baseline | Extraction cache | Change |
|---|---:|---:|---:|
| Staging | 5m52s | 1m03s | 82.2% reduction, 5.61x faster |
| Compression | 8m11s | 7m35s | 7.3% reduction; unchanged code, attributed to run variance |
| Script total | 14m02s | 8m38s | 38.5% reduction, 1.63x faster |

This established that repeated artifact extraction was a real bottleneck before
changing compression.

### Full non-ASan comparison at zlib-ng level 6

- [System-gzip baseline run 32843555429](https://github.com/ROCm/TheRock/actions/runs/32843555429)
- [Optimized level-6 run 32903348931](https://github.com/ROCm/TheRock/actions/runs/32903348931)

Both built 34 archives for all 16 families.

| Phase | Baseline | Optimized level 6 | Change |
|---|---:|---:|---:|
| Staging | 56m55s | 2m46s | 95.1% reduction, 20.59x faster |
| Compression | 21m56s | 4m55s | 77.6% reduction, 4.46x faster |
| Script total | 1h18m51s | 7m41s | 90.3% reduction, 10.27x faster |
| Upload | about 1m30s | about 1m27s | Essentially unchanged |

The extraction cache produced the larger absolute saving. Threaded compression
then removed most of the remaining compression time.

### Controlled ASan comparison at zlib-ng level 6

- [System-gzip ASan baseline run 31754588494](https://github.com/ROCm/TheRock/actions/runs/31754588494)
- [Optimized ASan level-6 run 32904676806](https://github.com/ROCm/TheRock/actions/runs/32904676806)

Both built four `gfx94X-dcgpu`/multiarch archives, including tests.

| Phase | Baseline | Optimized level 6 | Change |
|---|---:|---:|---:|
| Staging | 1h15m04s | 13m34s | 81.9% reduction, 5.54x faster |
| Compression | 57m15s | 19m35s | 65.8% reduction, 2.92x faster |
| Script total | 2h12m20s | 33m09s | 75.0% reduction, 3.99x faster |
| Upload | about 1m55s | about 1m38s | No meaningful regression |

ASan remains more expensive because its inputs and output archives are much
larger, but the optimized job is no longer close to the historical ASan Python,
DEB, or RPM packaging durations.

### Compression-level microbenchmark

All zlib-ng cases used eight threads. Sizes are exact bytes.

| Backend/level | Time | Size | Size versus warmed system gzip |
|---|---:|---:|---:|
| System gzip, warmed | 22.890s | 219,154,772 | baseline |
| zlib-ng level 6 | 2.026s | 223,470,427 | +1.97% |
| zlib-ng level 7 | 2.460s | 221,742,724 | +1.18% |
| zlib-ng level 8 | 5.841s | 220,501,646 | +0.61% |
| zlib-ng level 9 | 5.413s | 217,343,726 | -0.83% |

Level 9 was about 4.2x faster than warmed system gzip in this microbenchmark and
slightly smaller. The level-8/level-9 timing inversion is another reason not to
overinterpret a single local run.

### Final level-9 CI results

- [Non-ASan level-9 run 32989643966](https://github.com/ROCm/TheRock/actions/runs/32989643966)
- [ASan level-9 run 32989724543](https://github.com/ROCm/TheRock/actions/runs/32989724543)

| Scope | Staging | Compression | Script total | Full build step |
|---|---:|---:|---:|---:|
| Non-ASan, 34 archives | 2m45s | 4m22s | 7m07s | 7m07s |
| ASan, 4 archives | 13m33s | 19m00s | 32m33s | 32m33s |

Against the matching system-gzip baselines:

| Scope | Staging improvement | Compression improvement | Total improvement |
|---|---:|---:|---:|
| Non-ASan | 95.2%, 20.67x | 80.1%, 5.02x | 91.0%, 11.08x |
| ASan | 81.9%, 5.54x | 66.8%, 3.01x | 75.4%, 4.07x |

In these individual runs, level 9 was 34-36 seconds faster than level 6 as well
as smaller. The size improvement is deterministic enough to guide the setting;
the small speed improvement should be treated as runner/storage variance, not a
claim that zlib-ng level 9 is intrinsically faster than level 6.

The resulting tarball build is below the historical concurrent packaging jobs:

- Non-ASan: 7m07s versus Python 13m28s, RPM 17m47s, and DEB 49m51s.
- ASan: 32m33s versus RPM 1h15m48s and Python/DEB near 1h39m.

This meets the primary goal: tarball construction is no longer the aggregate
publication bottleneck in the measured release configurations.

### Archive sizes

The script labels these values `MB` but computes them with a `1024**2` divisor;
the table therefore describes reported MiB.

| Scope | System gzip | zlib-ng level 6 | zlib-ng level 9 |
|---|---:|---:|---:|
| Non-ASan, 34 archives total | 130,002.3 | 133,058.1 (+2.35%) | 128,680.9 (-1.02%) |
| ASan, 4 archives total | 144,758.5 | 147,353.8 (+1.79%) | 143,314.2 (-1.00%) |

Level 9 reduced total size by 3.29% versus level 6 for non-ASan and 2.74% for
ASan. It also made the final output about 1% smaller than the original system
gzip output in both controlled comparisons.

Representative individual archives:

| Archive | System gzip | Level 6 | Level 9 |
|---|---:|---:|---:|
| `gfx90c` regular | 1,680.5 MiB | 1,724.1 MiB | 1,659.1 MiB |
| ASan `gfx94X-dcgpu` regular | 30,332.1 MiB | 30,866.7 MiB | 30,029.5 MiB |
| ASan `gfx94X-dcgpu-tests` | 42,047.1 MiB | 42,810.1 MiB | 41,627.7 MiB |

### Correctness results

#### Local direct-versus-cache tree

The preserved comparison command was:

```powershell
D:\projects\TheRock\.venv\Scripts\python.exe `
  D:\scratch\codex\verify_tarball_cache_benchmark.py `
  D:\scratch\codex\tarball-cache-benchmark-32675368657-windows\micro-amd-llvm-dev\01-direct `
  D:\scratch\codex\tarball-cache-benchmark-32675368657-windows\micro-amd-llvm-dev\02-cached `
  --workers 8
```

Result:

```text
MATCH: 01-direct: 4352 entries, 4098 files, 1 hardlink groups,
1.15 GiB compared in 4.6s
```

Entry kinds, file sizes, permissions, symlink targets, hardlink groups, and all
regular-file bytes matched.

#### Complete remote `gfx90c` semantic comparison

Results:

- 29,202 members in each archive.
- 25,478 regular files hashed.
- 8,671,754,001 regular-file bytes hashed per archive.
- Zero baseline-only paths.
- Zero optimized-only paths.
- Zero content-hash differences.
- Zero differences in type, size, mode, uid, gid, uname, gname, link target,
  device major/minor values, or PAX headers.
- All 29,202 members differed in `mtime` only.

The exact decompressed tar stream lengths were both 8,694,763,520 bytes, but
their SHA-256 hashes differed:

```text
baseline:  fd18beb264d20ebce79762293f0e95e010c94a97069cf29154a88db8351ee19c
optimized: 9a933cc5e89237bcf232382717cfaec3d6d353e8367044f8f29da762891060c4
```

The first differing tar byte was in the root member's mtime field. Member order
also differed: the baseline traversal began with `./share/doc/rocm-dbgapi`,
while the cached traversal began with `./share/doc/half`.

This does **not** indicate file corruption. `ArtifactPopulator` writes regular
files during flattening instead of preserving source artifact mtimes, so
separate packaging runs already receive packaging-time mtimes. Cached exploded
directories are traversed with filesystem iteration, which can also change tar
member order. The semantic archive contents matched completely apart from those
timestamps.

If byte-for-byte reproducible decompressed tar streams become a requirement,
member sorting and a timestamp policy should be designed separately. Normalizing
timestamps could change user-visible extracted metadata.

### Unit test and static-check results

Final targeted command:

```powershell
cd D:\projects\TheRock\build_tools
D:\projects\TheRock\.venv\Scripts\python.exe -m pytest `
  --override-ini=cache_dir=D:/scratch/codex/pytest-cache/TheRock-build-tools-review `
  -p no:cacheprovider `
  tests/artifact_manager_tool_test.py tests/build_tarballs_test.py
```

Result after the review follow-ups: **50 passed in 0.49s** on Windows/Python
3.13.5. The original 49 tests also passed from an isolated archive of commit
`91a7a9338` in 0.54s.

The pytest cache was explicitly kept outside the source checkout and the cache
provider was disabled. Earlier apparent sandbox hangs were associated with a
sandbox-owned `.pytest_cache`, not with the lightweight tests themselves.

`git diff --check c04a9dd6d..HEAD` passed. A focused secret-pattern scan over
all five changed files found no matches.

## Failed experiments and what they taught us

Two first attempts at the full-stack CI experiment failed:

- [Run 32896356513](https://github.com/ROCm/TheRock/actions/runs/32896356513)
- [Run 32896525656](https://github.com/ROCm/TheRock/actions/runs/32896525656)

They selected `s3://therock-ci-artifacts/...`, while the input workflow runs had
published to the `dev` artifact bucket. The backend correctly listed zero
artifacts, but `artifact_manager.py` returned success after printing
`No matching artifacts found to download`. `build_tarballs.py` then called
`shutil.disk_usage()` on a staging directory that had never been created and
raised a misleading `FileNotFoundError`.

The corrected behavior raises `RuntimeError` immediately with the backend URI
and target families. Corrected experiments used the `dev` release type and
succeeded. These failures were input-configuration errors, not evidence of a
cache or compression regression, but they exposed a worthwhile fail-fast gap.

## Thread contention and runner sizing

The local contention harness compressed ten copies of the same 1.15 GiB staging
tree using combinations of archive workers and threads per archive. It measured
batch wall time, per-archive wall time, process CPU time, overall CPU use, and
disk I/O. The exact console output was not preserved, so no unsupported numeric
claims from that exploratory run are reproduced here.

The durable conclusion was to avoid nominal oversubscription by budgeting
`threads + 1` CPUs for each active archive. This led to the current automatic
worker policy.

Observed CI scheduling at the final settings:

- 96 CPUs, 34 normal tasks: ten workers, each with eight zlib-ng threads plus a
  concurrent `tar` producer.
- 96 CPUs, four ASan tasks: four workers because task count, nominally using
  about 36 runnable CPU threads during compression.

The optimized job is no longer primarily a network-bound job. Staging still
uses download/decompression/file traversal, but threaded compression visibly
consumes multiple cores per archive. Downsizing will therefore trade wall time
for cost rather than being free.

There is substantial headroom relative to the other packaging jobs, especially
for ASan. A 64-core runner is a plausible next experiment because it can still
run all four ASan archives concurrently with eight compressor threads each. A
32-core runner automatically drops to three archive workers, which creates
additional waves for 34-archive releases and leaves one ASan archive waiting.
Whether that remains below the aggregate critical path must be measured rather
than inferred.

Recommended runner-size experiment:

1. Reuse the same normal and ASan input workflow run IDs from this report.
2. Compare 96-, 64-, and 32-core instances with no other code changes.
3. Record staging, compression, upload, whole-job duration, CPU utilization,
   disk throughput/queue depth, network throughput, and runner cost.
4. For each size, also test a small grid around the automatic policy, such as
   four versus eight compression threads and the corresponding worker count.
5. Choose the cheapest size that keeps tarball completion safely earlier than
   the next-slowest packaging job, including normal run-to-run variance.

## Alternatives Considered

### Publish through a staging index before every package form is complete

A staging index or partial publication could let downstream framework work
start earlier, but it weakens the single completeness check that prevents an
incomplete ROCm release from becoming user-facing. The preferred direction is
to separate downstream build and publish phases where useful while retaining
the final aggregate publication gate. This PR improves the gate's slowest
prerequisite instead.

### Retain system gzip only and parallelize archives

The baseline already compressed many independent archives concurrently, which
works reasonably well when there are many modest archives. It performs poorly
for ASan, where only four very large archives exist and each system-gzip process
is effectively single-threaded. Retaining this alone could not address the
57-minute controlled ASan compression phase.

### Python `tarfile` with gzip

The prior implementation notes and exploratory experience found Python's
default `tarfile` gzip path slower and larger than the system `tar cfz` path.
It also remains single-threaded for compression. It was not pursued.

### `pigz`

`pigz` provides parallel gzip and would preserve `.tar.gz`, but introduces a
separate native executable that must be installed consistently on Linux and
Windows runners. The zlib-ng Python package provides a cross-platform wheel and
direct streaming API through the existing Python requirements flow, so it was
preferred.

### ISA-L / `python-isal`

ISA-L was prototyped through `igzip_threaded`. In a small smoke archive of the
`build_tools/tests` tree, the ISA-L output was 652,406 bytes versus 564,858 bytes
for the zlib-ng candidate, about 15.5% larger. The levels and workload were not
a definitive apples-to-apples benchmark, but the result reinforced the known
speed-versus-ratio tradeoff. Because release file size matters, zlib-ng was the
better candidate.

### Zstandard and `.tar.zst`

Zstandard would likely compress and decompress faster with a strong size ratio,
and TheRock already uses `.tar.zst` internally for build artifacts. Release
tarballs are user-facing `.tar.gz` files, however. Changing format would require
coordinating every downloader, installer, documentation path, and user
environment. That compatibility migration was out of scope.

### 7-Zip/libarchive or platform-specific compression tools

These add external-tool discovery, version differences, and cross-platform
behavior to a path that already works with system `tar` plus a Python wheel.
There was no measured benefit sufficient to justify the operational complexity.

### Start compression while later families are still staging

This could overlap CPU work with network and extraction work, but it complicates
resource control and increases contention on the same disk. It also makes
largest-first scheduling harder because the largest multiarch tasks are only
ready after family staging. With the final 7-minute normal and 33-minute ASan
results, the added pipeline complexity is not justified.

### Shard archives across multiple runners

Sharding can reduce wall time, but adds workflow fan-out/fan-in, repeated setup,
more downloads, and additional runner cost. The single-runner result is already
below the aggregate packaging critical path. Sharding should only be revisited
if target-family count or ASan payload size grows enough to reverse that.

### Determine priority from live directory sizes

Measuring each staged tree could produce a more exact ordering, but requires
additional traversal or bookkeeping over very large trees. The coarse category
priority captures the dominant size ordering with almost no complexity. Within
a category, exact family ordering has much less effect than ensuring multiarch
and test archives start first.

### Use a persistent extraction cache across jobs or workflow runs

Cross-run caching could save more work, but requires robust invalidation and
integrity validation. Artifact filenames do not include a content digest, and
an interrupted download or a same-name artifact from another run must not be
silently reused. The current cache is deliberately job-local. Content-addressed
or run-ID-scoped persistence is possible future work but was not needed for the
measured gains.

### Lower compression levels 6, 7, or 8

Level 6 maximized speed but made full release output 1.8-2.4% larger than system
gzip. Levels 7 and 8 improved the ratio in the local sweep. Level 9 recovered
all of the size and remained much faster than the baseline in full CI, so it is
the better release default.

## Limitations and interpretation cautions

- CI comparisons are separate runs on separate instances, not repeated samples
  on one controlled machine. Small timing differences, especially level 6
  versus level 9, are noise-sensitive.
- The paired runs use identical artifact inputs and target selections, which
  controls the largest sources of variation, but shared cloud storage and host
  performance can still vary.
- The controlled ASan experiment covers `gfx94X-dcgpu`, not every scope that
  contributed to the historical 4h03m observation.
- Local benchmarks ran on Windows and sometimes alongside a source build. They
  were used to choose candidates and levels, not to predict final CI time alone.
- Full semantic archive comparison was performed on one representative normal
  family archive. Unit tests and successful full CI runs add breadth, but the
  30-42 GiB ASan archives were not all rehashed member-by-member.
- Separate runs do not produce byte-identical tar streams because tar member
  mtimes and traversal order are not normalized.

## Review follow-ups completed

- Added concise source comments explaining the empirically chosen level 9,
  eight-thread default, the `tar` producer CPU, and the extraction-cache role
  in sequential staging.
- Strengthened the zlib-ng unit test with a regular-file payload assertion.
- Added a behavioral test for rebuilding an incomplete extraction-cache entry.
- Renamed the fetch-failure test group to cover both command and propagated
  exception failures accurately.

## Recommended follow-up work

1. Benchmark 64- and 32-core CI runners before changing the fleet size.
2. Track tarball duration as target families and ASan payloads grow; only pursue
   staging/compression overlap or runner sharding if tarballs re-enter the
   release critical path.
3. Consider deterministic member order and timestamp policy separately if
   reproducible archives become a requirement.

## Bottom line

The combined changes reduced controlled non-ASan tarball construction from
1h18m51s to 7m07s and controlled ASan construction from 2h12m20s to 32m33s.
Level 9 made the output about 1% smaller than the original system-gzip output in
both comparisons. Local and remote validation found no file-content or semantic
metadata regressions apart from expected packaging-time mtimes and tar traversal
order. In the measured release configurations, tarballs are no longer the
aggregate publication bottleneck.

Generated with Codex
