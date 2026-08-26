# Branch Review: users/scotttodd/tarball-optimize-4

* **Repository:** `ROCm/TheRock`
* **Branch:** `users/scotttodd/tarball-optimize-4`
* **Base:** `c04a9dd6dd6c3f7f5430bc64866640ffc2b213cb`
* **Head:** `91a7a9338daac3febc2ac97a0ffe0e2933e8adc6`
* **Reviewed:** 2026-08-26
* **Commits:** 5

---

## Summary

This branch optimizes multi-architecture release tarball construction by
extracting each source artifact once, reusing extracted files through hardlinks,
using threaded zlib-ng compression, limiting aggregate CPU demand, and starting
the expected largest compression tasks first. It also fails at the artifact
selection boundary when no inputs match, avoiding a later and misleading
`FileNotFoundError`.

**Net changes:** +508/-41 lines across five files.

The changes form one cohesive optimization stack. The new dependency is used
directly by the packaging script, the cache is opt-in at the general
`artifact_manager.py` layer and enabled by `build_tarballs.py`, and the old
system-gzip path remains available for A/B comparisons and troubleshooting.

---

## Overall Assessment

**APPROVED** — No blocking correctness, security, or architecture issues were
found. The optimization is strongly supported by full-scale CI data and
semantic archive comparisons. The documentation and test-coverage follow-ups
identified during review were addressed in follow-up commit `59977d4a7`.

**Strengths:**

- The extraction cache has a clear completion sentinel: the manifest is written
  only after extraction succeeds.
- The cache contract explicitly warns that hardlinked outputs must remain
  read-only.
- Failed compression removes a partial tarball, and the tar subprocess return
  code is propagated.
- CPU affinity is respected on Linux, with a portable CPU-count fallback.
- Compression task priority is represented by a dataclass rather than an opaque
  multi-field tuple.
- The priority comment clearly explains the scheduling objective: reduce the
  long tail by starting slow archives first.
- Tests use real archives and temporary files for the extraction cache instead
  of mocking the filesystem behavior being validated.
- No secrets, binary blobs, shell interpolation, or `shell=True` command
  execution were introduced.

**Important issues:** None outstanding.

---

## Detailed Review

### 1. Compression tuning rationale

**IMPORTANT: Explain why level 9, eight threads, and one extra CPU per archive
are the defaults.**

[`build_tarballs.py`](https://github.com/ROCm/TheRock/blob/91a7a9338daac3febc2ac97a0ffe0e2933e8adc6/build_tools/build_tarballs.py#L70-L72)
declares three performance-sensitive defaults without recording why those
values were chosen. The worker calculation later reserves
`compression_threads + 1` CPUs per archive, but does not explain that the extra
CPU is for the concurrent `tar` producer
([lines 273-286](https://github.com/ROCm/TheRock/blob/91a7a9338daac3febc2ac97a0ffe0e2933e8adc6/build_tools/build_tarballs.py#L273-L286)).

These choices are effective, but they look arbitrary without the experiment
context. That makes it easy for a future cleanup to remove the `+ 1`, lower the
compression level based only on a microbenchmark, or increase worker count and
silently reintroduce oversubscription.

**Recommendation:** Add concise qualitative comments near the constants and
worker formula. The comments should state that level 9 recovered the system-gzip
size while remaining off the packaging critical path, eight threads balances
intra-archive speed with archive-level concurrency, and each archive also has a
`tar` producer. Avoid embedding exact timing percentages in source comments;
those belong in the PR evidence.

Also expand the phase-one comment at
[`build_tarballs.py:379`](https://github.com/ROCm/TheRock/blob/91a7a9338daac3febc2ac97a0ffe0e2933e8adc6/build_tools/build_tarballs.py#L379)
to mention that sequential staging allows both downloaded archives and their
extracted contents to be reused across family and multiarch layouts.

**Resolution:** Addressed in follow-up commit `59977d4a7`. The defaults, extra `tar`
producer CPU, and sequential cache-reuse rationale now have concise source
comments without embedding benchmark-specific timings.

### 2. Compression output coverage

**IMPORTANT: Assert regular-file payload bytes in the zlib-ng test.**

[`TestCompressTarball.test_creates_tarball`](https://github.com/ROCm/TheRock/blob/91a7a9338daac3febc2ac97a0ffe0e2933e8adc6/build_tools/tests/build_tarballs_test.py#L84-L103)
executes the real zlib-ng streaming path and verifies that the archive is
readable and contains two expected member names. It never reads either member's
payload. The new implementation coordinates a subprocess pipe, a threaded gzip
writer, and exception cleanup; member-name checks alone provide weaker
protection than the code warrants.

**Recommendation:** Read `./bin/hello` with `extractfile()` and assert
`b"hello world"`. Checking its executable mode would also be useful if the test
sets one. One payload assertion is enough; there is no need to duplicate the
same coverage for every backend.

**Resolution:** Addressed in follow-up commit `59977d4a7`. The real zlib-ng archive test now
reads `./bin/hello` and asserts its complete payload.

### 3. Extraction-cache recovery coverage

**SUGGESTION: Cover recovery from an incomplete cache directory.**

The implementation deliberately removes a cache directory if its completion
manifest is absent, then writes the manifest last
([`artifact_manager.py:367-392`](https://github.com/ROCm/TheRock/blob/91a7a9338daac3febc2ac97a0ffe0e2933e8adc6/build_tools/artifact_manager.py#L367-L392)).
The existing real-archive test thoroughly covers first population and reuse,
including contents, modes, hardlinks, and symlinks, but not this recovery path
([`artifact_manager_tool_test.py:1097-1190`](https://github.com/ROCm/TheRock/blob/91a7a9338daac3febc2ac97a0ffe0e2933e8adc6/build_tools/tests/artifact_manager_tool_test.py#L1097-L1190)).

Consider precreating the archive's cache directory with a stale file and no
manifest, then verifying that extraction replaces it with a complete entry.
This is a cheap behavioral test for the cache's crash-recovery invariant.

**Resolution:** Addressed in follow-up commit `59977d4a7`. The new test precreates an
incomplete entry, verifies stale state is removed, checks the rebuilt manifest
and payload, and confirms the flattened output is hardlinked to the cache.

### 4. Test naming and comments

**SUGGESTION: Rename the broadened failure-test class.**

[`TestFetchFailureExitCode`](https://github.com/ROCm/TheRock/blob/91a7a9338daac3febc2ac97a0ffe0e2933e8adc6/build_tools/tests/artifact_manager_tool_test.py#L491)
now includes a test asserting a propagated `RuntimeError`, not an exit code.
`TestFetchFailures` and a matching class docstring would describe the group
more accurately.

**Resolution:** Addressed in follow-up commit `59977d4a7` by renaming the class to
`TestFetchFailures` and broadening its docstring.

### 5. Archive reproducibility

**FUTURE WORK: Normalize tar ordering and timestamps if byte-for-byte
reproducibility becomes a goal.**

The semantic comparison found identical paths, payload hashes, ownership,
permissions, links, device metadata, and PAX headers. Separate packaging runs
still differed in member ordering and modification times. Modification times
were already packaging-time values in the baseline because archive flattening
rewrites files; the cache is not introducing payload differences. Achieving
identical decompressed tar streams would require a separate policy decision,
such as sorting members and normalizing or preserving timestamps. That could
change user-visible extracted mtimes and should not be folded into this
performance PR without discussion.

### 6. Dependency and platform review

The new `zlib-ng>=1.0.0` requirement is justified by direct use. The installed
1.0.0 package reports a PSF-2.0 license and Python >=3.9 support. The real
compression tests pass on Windows, and the release and ASan workflows pass on
Linux. This gives useful cross-platform coverage without adding a separately
managed executable such as `pigz`.

---

## Test and CI Evidence

Local targeted command, run from `D:\projects\TheRock\build_tools`:

```powershell
D:\projects\TheRock\.venv\Scripts\python.exe -m pytest `
  --override-ini=cache_dir=D:/scratch/codex/pytest-cache/TheRock-build-tools-review `
  -p no:cacheprovider `
  tests/artifact_manager_tool_test.py tests/build_tarballs_test.py
```

Result after the review follow-ups: **50 passed in 0.49s**. An independent
snapshot of the originally reviewed commit passed its 49 tests in 0.54s.

`git diff --check c04a9dd6d..HEAD` passed. A focused secret-pattern scan over
the five changed files found no matches.

Current-head CI:

- [Level-9 release run 32989643966](https://github.com/ROCm/TheRock/actions/runs/32989643966): success; build script 7m07s.
- [Level-9 ASan run 32989724543](https://github.com/ROCm/TheRock/actions/runs/32989724543): success; build script 32m33s.

The complete benchmark methodology, phase timings, archive-size data, failed
experimental runs, semantic archive comparison, and alternatives considered are
recorded in
[`tasks/completed/tarball-packaging-optimization-experiments.md`](../tasks/completed/tarball-packaging-optimization-experiments.md).

---

## Recommendations

### Required

None.

### Resolved during review

1. Added qualitative rationale for compression level, thread count, CPU
   accounting, and sequential cache reuse.
2. Added a regular-file payload assertion to the zlib-ng archive test.
3. Added incomplete extraction-cache recovery coverage.
4. Renamed `TestFetchFailureExitCode` to match its broader scope.

### Future follow-up

1. Test the auto worker policy on 32- and 64-core CI runners before resizing
   the packaging fleet.
2. Consider reproducible tar ordering and timestamps as a separate change.
3. Revisit streaming staging directly into compression only if tarballs again
   become the release critical path; the current results do not justify that
   complexity.

---

## Conclusion

**Approval Status: APPROVED**

The optimization is correct in the tested scenarios, substantially reduces the
release critical path, and produces semantically equivalent archives. All four
documentation, coverage, and naming follow-ups identified during review are
addressed in follow-up commit `59977d4a7`.

Generated with Codex
