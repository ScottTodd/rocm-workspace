# PR Review: ROCm/TheRock#5778

* **PR:** https://github.com/ROCm/TheRock/pull/5778
* **Title:** `Link per-ISA device files into rocm-sdk-devel`
* **Author:** `marbre`
* **Branch:** `users/marbre/devel-device-file-links`
* **Base:** `main`
* **Reviewed:** 2026-06-11
* **Head SHA:** `9954dab50fd0789ee097a40a9d8bb89ff88ed154`
* **Related PR:** https://github.com/ROCm/TheRock/pull/5784
* **Net changes:** +595 / -1 across 7 files

---

## Summary

This PR adds a device-wheel manifest and a `rocm-sdk init/path` reconciliation
step that hardlinks per-ISA device payloads from the shared
`rocm-sdk-libraries` overlay into the expanded `rocm-sdk-devel` tree. The
overall approach matches the packaging constraints: wheel install hooks are not
available, directory hardlinks are not portable, and hardlinks preserve the
existing symlink-to-hardlink behavior used during devel extraction.

The related parity test in #5784 is the right end-to-end guard for the original
bug: it fails with current packages where `_rocm_sdk_libraries` has per-ISA
payloads missing from `_rocm_sdk_devel`, and the linked Windows comment shows it
passing with wheels from this PR's CI run.

## Overall Assessment

**CHANGES REQUESTED** - The main design is sound, but two edge cases in the new
reconcile path should be fixed before merge: the new Windows lock does not
serialize processes when the lock file is empty, and missing manifest targets are
still recorded in the owning wheel's `RECORD` even though no hardlink was
created or verified.

## Findings

### IMPORTANT: Windows reconcile lock is ineffective for a new empty lock file

[`_reconcile_device_links()`](https://github.com/ROCm/TheRock/blob/9954dab50fd0789ee097a40a9d8bb89ff88ed154/build_tools/packaging/python/templates/rocm/src/rocm_sdk/_devel.py#L348-L350)
opens `.devel_reconcile.lock` in append mode and passes it to `FileLock`. For a
new lock file, `FileLock` records `original_file_size == 0` and on Windows calls
[`msvcrt.locking(..., self.original_file_size)`](https://github.com/ROCm/TheRock/blob/9954dab50fd0789ee097a40a9d8bb89ff88ed154/build_tools/packaging/python/templates/rocm/src/rocm_sdk/_devel.py#L451-L466).

I checked this locally with the PR head on Windows: while one process held
`_devel.FileLock` on an empty file, a child process also acquired `_devel.FileLock`
on the same file and printed `child_filelock_succeeded`. So the new reconcile
lock does not provide cross-process exclusion on Windows until the file has
nonzero size.

Impact: concurrent `rocm-sdk init/path` calls can both enter the slow reconcile
path on Windows. The loop rechecks each destination before creating it, which
reduces the race window, but two processes can still both observe a missing
destination and then race through unlink/hardlink and `RECORD` rewrite logic at
[`_devel.py#L361-L375`](https://github.com/ROCm/TheRock/blob/9954dab50fd0789ee097a40a9d8bb89ff88ed154/build_tools/packaging/python/templates/rocm/src/rocm_sdk/_devel.py#L361-L375). That can produce a spurious init failure or partial RECORD repair in the
parallel first-use case.

**Recommendation:** Ensure the Windows lock range is always nonzero. For example,
make `FileLock` lock `max(os.path.getsize(file.name), 1)` bytes and use the same
stored lock length during unlock, or initialize `.devel_reconcile.lock` with one
byte before locking. Add a small subprocess-based Windows test for the empty-file
case so this does not regress.

### IMPORTANT: Missing device targets are recorded even when no link is created

Inside `_reconcile_device_links()`, `recorded_names.append(...)` happens before
the hardlink target is checked. If the manifest target is missing,
[`hardlink_target.is_file()` fails and the code continues](https://github.com/ROCm/TheRock/blob/9954dab50fd0789ee097a40a9d8bb89ff88ed154/build_tools/packaging/python/templates/rocm/src/rocm_sdk/_devel.py#L358-L370),
but [`_ensure_record_entries(record_path, recorded_names)`](https://github.com/ROCm/TheRock/blob/9954dab50fd0789ee097a40a9d8bb89ff88ed154/build_tools/packaging/python/templates/rocm/src/rocm_sdk/_devel.py#L375) still records that devel path in the device wheel's
`RECORD`.

I reproduced the edge case with a synthetic site-packages tree: one manifest
entry, no libraries target, and a pre-existing file at the would-be devel path.
Reconcile returned `created=0`, but the devel path was added to `RECORD`; a
simulated `pip uninstall` pass over that RECORD then deleted the pre-existing
devel file.

Impact: a corrupted or partially removed device wheel can claim ownership of a
devel path that this reconcile did not create or verify. That undermines the
RECORD ownership invariant the PR is trying to establish, and can make uninstall
remove stale or unrelated devel content.

**Recommendation:** Prefer fail-fast here: if the target shipped by the same
device wheel is missing, raise an error that identifies the wheel and manifest
entry. If best-effort behavior is required, only add a RECORD name after the
destination is known to be a correct hardlink to the manifest target. Add a unit
test where the manifest exists but the target file does not.

## Additional Notes

* #5784's parity test is useful coverage for the original missing-device-files
  bug, but it does not exercise the two edge cases above. It should still be
  merged after rebasing onto this fix.
* The PR documents the one-shot trampoline behavior in `rocm_sdk_core._cli` and
  `docs/packaging/python_packaging.md`. The GitHub discussion also notes that
  user-facing release/install docs should mention rerunning `rocm-sdk init` or
  `rocm-sdk path` after adding/removing a device wheel in an already-expanded
  environment.
* CI metadata shows unit tests and pre-commit passing for #5778, and the related
  #5784 comments show the new parity test failing before this PR and passing
  with this PR's CI wheels on Windows. Several package/GPU checks and gitleaks
  are still reported failing on #5778; the Actions job-log endpoint returned
  `HTTP 403 Must have admin rights`, so I could not inspect those failures from
  this environment.

## Verification Performed

* Reviewed PR #5778 diff and REST metadata.
* Reviewed PR #5784 diff, comments, and check metadata.
* Ran a local synthetic missing-target/RECORD scenario against the checked-out PR
  head.
* Ran a local two-process Windows check against `_devel.FileLock` showing that an
  empty lock file does not exclude a second process.

Generated by Codex.
