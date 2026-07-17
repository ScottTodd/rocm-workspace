# PR Review: ROCm/TheRock#5948

* **PR:** https://github.com/ROCm/TheRock/pull/5948
* **Title:** `fix(build_tools): use unique temp filename in _download_blob to avoid race`
* **Author:** `koteshyelamati`
* **Base:** `ROCm:main` at `2d417fa49bc4e657bcbcf0ae549238784175f0fe`
* **Head:** `koteshyelamati:fix/download-blob-temp-collision` at `d5bd9951a9fbb67011db2c24c6feab1edba4472e`
* **Reviewed:** 2026-06-18
* **Net changes:** +69 / -3 across 2 files

---

## Summary

This PR fixes a real race in `build_tools/fetch_dvc_artifacts.py`: concurrent
downloads to the same content-addressed destination no longer share a fixed
`<dest>.tmp` path. The approach matches the already-established `_store_in_cache`
pattern by using a UUID-suffixed temporary path, then atomically replacing the
destination.

The implementation direction looks correct, and the build-tools unit tests pass
on both Ubuntu and Windows in CI. The PR is not merge-ready because pre-commit
currently fails.

---

## Overall Assessment

**CHANGES REQUESTED** - The code fix is sound, but the PR fails the required
pre-commit check. There is also a small but useful test assertion gap now that
`_download_blob` creates dynamic temp filenames.

---

## Findings

### BLOCKING: pre-commit fails because `black` reformats the new test call

* **Where:** [`build_tools/tests/fetch_dvc_artifacts_test.py`](https://github.com/ROCm/TheRock/blob/d5bd9951a9fbb67011db2c24c6feab1edba4472e/build_tools/tests/fetch_dvc_artifacts_test.py#L444-L446)
* **Evidence:** The `pre-commit` job failed in CI:
  https://github.com/ROCm/TheRock/actions/runs/27733286587/job/82185207391

`black` rewrites:

```python
fda._download_blob(
    s3, remote, md5, dest, expected_size=len(data)
)
```

to:

```python
fda._download_blob(s3, remote, md5, dest, expected_size=len(data))
```

This is a required repository check, so the PR cannot merge as-is.

**Required action:** Run `pre-commit run black --files build_tools/tests/fetch_dvc_artifacts_test.py`
or `pre-commit run --all-files`, commit the formatting change, and rerun CI.

### IMPORTANT: failure-path tests still check the old fixed temp filename

* **Where:** [`build_tools/tests/fetch_dvc_artifacts_test.py`](https://github.com/ROCm/TheRock/blob/d5bd9951a9fbb67011db2c24c6feab1edba4472e/build_tools/tests/fetch_dvc_artifacts_test.py#L375-L403)

The PR changes `_download_blob` from a single predictable temp file to a
UUID-suffixed temp file. The existing MD5 mismatch test still verifies only
`dest.with_suffix(dest.suffix + ".tmp")`, which no longer corresponds to the
temp path this function creates. The size mismatch test checks that `dest` is
absent, but does not check for leftover temp files at all.

The implementation's `finally` block should clean up correctly, but the tests no
longer enforce the "no temp files left behind" invariant on error paths.

**Recommendation:** In both mismatch tests, assert that the destination
directory has no matching temp files, for example with `list(dest.parent.glob("*.tmp"))`.
That keeps the existing atomic-write cleanup invariant covered after this
filename change.

---

## CI Evidence

* `pre-commit`: failed because `black` reformatted
  `build_tools/tests/fetch_dvc_artifacts_test.py`.
* `Unit Tests :: ubuntu-24.04`: passed. The `Test build_tools` step completed
  successfully in run `27733286579`, job `82185207520`.
* `Unit Tests :: windows-2022`: passed. The `Test build_tools` step completed
  successfully in run `27733286579`, job `82185207476`.
* `Linux::release` and `Windows::release` had several failing or pending jobs
  in run `27733286789`. The release run was still in progress while reviewed,
  and logs for the failed component jobs returned HTTP 403. The job metadata I
  could inspect showed failures before component test execution, such as Linux
  driver/GPU sanity and Windows test-environment setup, so I did not attribute
  those failures to this PR.

---

## Other Review Notes

* The UUID temp filename change in `_download_blob` is consistent with the
  existing `_store_in_cache` pattern.
* No new secrets, binary files, shell execution, or credential-handling changes
  were introduced.
* The regression test uses an in-memory fake S3 client and a barrier to exercise
  the shared-destination race without external services, which is the right
  level of test for this bug.

---

## Testing Recommendations

Before merge, rerun:

```powershell
cd D:\projects\TheRock\build_tools
D:\projects\TheRock\.venv\Scripts\python.exe -m pytest tests\fetch_dvc_artifacts_test.py
pre-commit run --all-files
```

---

## Conclusion

**Approval Status: CHANGES REQUESTED**

Fix the `black` formatting failure before merge. Updating the error-path temp
cleanup assertions is not as severe as the failing check, but it would make the
test suite better match the new UUID temp-file behavior.

Authored-by: Codex
