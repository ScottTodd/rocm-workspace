# PR Review: Make artifact archives reproducible

* **PR:** https://github.com/ROCm/TheRock/pull/4265
* **Author:** `PeterCDMcLean`
* **Branch:** `users/pmclean/normalize_archive_metadata` → `main`
* **Head:** `2c4e68029adf728922cbc519d54930eb4b619505`
* **Reviewed:** 2026-08-28
* **Focus:** Correctness, side effects, and unintended consequences

---

## Summary

This PR makes artifact archives and the `rocm-sdk-devel` wheel's secondary tarball deterministic by normalizing tar member timestamps and ownership and by sorting member insertion order. The artifact-archive portion is well contained: its primary reader (`ArtifactPopulator`) copies file bytes and executable bits rather than restoring tar mtimes. The devel-wheel portion has a more complex, order-sensitive extractor and exposes two unintended consequences.

**Net changes:** +280/-10 across five Python files, including nine new tests.

---

## Overall Assessment

**❌ CHANGES REQUESTED** — the reproducibility objective is sound, but the new mixed file/directory ordering causes a reproducible data-loss regression when the devel wheel is expanded. Epoch mtimes also create an incremental-build hazard after devel-wheel upgrades that should be addressed or explicitly accepted before merge.

**Strengths:**

- The manifest remains first in artifact archives, preserving `ArtifactPopulator`'s streaming contract.
- Modes, file types, sizes, symlink targets, and the hardlink relationship are not erased by `normalize_tarinfo()`.
- The new archive-level regression tests exercise real files and prove byte-for-byte stability after mtime changes.
- Artifact and Python-package build jobs passed on both Linux and Windows; the Windows wheel test also passed.

---

## Findings

### ❌ BLOCKING: Alphabetically mixing directories with files can delete devel-wheel entries during expansion

[`add_tree()` combines `filenames` and `dirnames` before sorting](https://github.com/ROCm/TheRock/blob/2c4e68029adf728922cbc519d54930eb4b619505/build_tools/_therock_utils/archive_util.py#L44-L55), and [`populate_devel_files()` now uses that helper](https://github.com/ROCm/TheRock/blob/2c4e68029adf728922cbc519d54930eb4b619505/build_tools/_therock_utils/py_packaging.py#L650-L661). This changes an important property of the old loop: every file in a directory was emitted before every child directory.

The runtime devel-wheel extractor is order-sensitive. On the first file or symlink in a parent, [`_lock_and_expand()` deletes that entire parent directory before extracting the member](https://github.com/ROCm/TheRock/blob/2c4e68029adf728922cbc519d54930eb4b619505/build_tools/packaging/python/templates/rocm/src/rocm_sdk/_devel.py#L416-L444). Directory members are cleaned and extracted separately [later in the same loop](https://github.com/ROCm/TheRock/blob/2c4e68029adf728922cbc519d54930eb4b619505/build_tools/packaging/python/templates/rocm/src/rocm_sdk/_devel.py#L493-L498).

If a child directory sorts before a sibling file, the extractor creates the directory and then deletes it when the file causes the parent cleanup. Non-empty directories are recreated later when their children are extracted, but empty directories are lost, and recreated directories no longer necessarily retain the archived directory metadata.

I reproduced this against the PR head's real `add_tree()` and real `_lock_and_expand()` with a tree containing `pkg/a_empty/` and `pkg/z_file.txt`:

```text
> D:\projects\TheRock\.venv\Scripts\python.exe repro_devel_old_order.py
archive members: ['pkg/z_file.txt', 'pkg/a_empty']
file exists: True
empty directory exists: True

> D:\projects\TheRock\.venv\Scripts\python.exe repro_devel_order.py
archive members: ['pkg/a_empty', 'pkg/z_file.txt']
file exists: True
file mtime: 0.0
empty directory exists: False
```

**Required action:** preserve deterministic file-before-directory order. A streaming implementation also avoids materializing the entire `os.walk()` result:

```python
for root, dirnames, filenames in os.walk(source_dir):
    dirnames.sort()  # Also controls os.walk traversal order.
    for name in sorted(filenames):
        add_member(root, name)
    for name in dirnames:
        add_member(root, name)
```

Add a regression that sends an empty directory plus a later-sorting sibling file through `add_tree()` and the devel expansion path, then verifies that the directory survives. The current exact-order unit test instead pins the unsafe mixed ordering.

### ⚠️ IMPORTANT: Epoch mtimes can suppress downstream rebuilds after a devel-wheel upgrade

[`normalize_tarinfo()` forces every member mtime to zero](https://github.com/ROCm/TheRock/blob/2c4e68029adf728922cbc519d54930eb4b619505/build_tools/_therock_utils/archive_util.py#L12-L27). The devel-wheel extractor calls `tarfile.extract()` for regular files and directories, which restores that value; the reproduction above confirms an installed file mtime of `0.0`.

That matters because `rocm-sdk-devel` contains headers, libraries, and build metadata intended to be consumed by build systems. After upgrading the wheel in an existing environment, changed SDK inputs still appear older than already-built external objects and executables. Timestamp-based tools such as Ninja or Make can therefore skip recompilation or relinking unless users clean their build trees manually.

This risk is narrower for normal artifact workflows:

- `ArtifactPopulator` writes file contents itself and does not restore tar mtimes.
- Bootstrap paths create fresh `.prebuilt` markers, which drive new stage stamps.
- `install_rocm_from_artifacts.py` removes and recreates its output directory before extraction.

It remains directly applicable to the new `py_packaging.py` call site.

**Required action:** decide and test the installed-time semantics for the devel wheel. At minimum, document that an SDK wheel upgrade requires a clean downstream build; silently presenting changed inputs as January 1970 is a surprising behavioral change.

#### Options and tradeoffs

The artifact archives and the devel-wheel tarball do not necessarily need the same policy. Artifact readers generally copy into a clean tree or ignore archived mtimes, while the devel wheel installs build inputs into an environment that can outlive downstream build outputs.

| Option | Pros | Cons |
|---|---|---|
| **1. Normalize archive mtimes everywhere, but set devel files to expansion time when installing** | Keeps CI and release archive bytes reproducible; identical archives retain identical hashes; an SDK upgrade makes installed headers and libraries newer than existing downstream outputs; cleanly separates distribution reproducibility from installed filesystem semantics | Installed trees are not timestamp-reproducible; reinstalling identical contents can trigger unnecessary downstream rebuilds; extraction must restore file and directory times carefully after all members are written |
| **2. Store a deterministic, version-advancing timestamp such as `SOURCE_DATE_EPOCH`** | Archive and installed mtimes remain deterministic; later releases will usually look newer and trigger downstream rebuilds; follows a common reproducible-build convention | Requires an explicit timestamp source in every archive-producing path; commit or release timestamps are not guaranteed to be monotonic in every workflow; identical file trees built from different commits can receive different archive hashes, weakening the PR's “same content, same SHA” goal |
| **3. Normalize artifact archives only; preserve real mtimes in the devel-wheel tarball** | Directly solves the generic-artifact collision prerequisite in issue #4202; preserves current devel-wheel installation behavior; smallest behavioral change | The devel wheel remains non-reproducible; rebuilding the same release can produce different wheel hashes; gives the two archive writers different policies and gives up part of this PR's expanded scope |
| **4. Normalize only in CI; preserve real mtimes for release builds** | CI jobs that contend for an artifact key can produce stable hashes; non-CI release installs retain useful mtimes | “CI” and “release” overlap because releases are commonly built in CI; identical source produces different archives across environments; release artifacts remain non-reproducible; CI no longer validates the archive behavior shipped by the release path; an ambient environment check introduces hidden policy into a low-level utility |
| **5. Keep epoch mtimes everywhere and require clean downstream builds after upgrades** | Simplest implementation; strongest byte-for-byte reproducibility; no additional policy or timestamp plumbing | Preserves the stale incremental-build risk; shifts cleanup cost to every devel-wheel user; easy to miss unless prominently documented; makes installed timestamps uninformative |
| **6. Preserve real mtimes and make #4202 compare a canonical content hash instead of the compressed archive SHA** | Conflict detection can ignore metadata and compression differences directly; installed timestamps remain useful; can define exactly which attributes are semantically significant | Substantially more implementation and format complexity; archives themselves remain non-reproducible; requires producing, storing, and validating a second digest definition; broader than this prerequisite PR |

Option 1 has the cleanest separation of concerns if both reproducible release wheels and safe incremental upgrades are requirements. Option 3 is the lowest-risk change if reproducibility is only needed for generic artifact collision detection. Option 4 is workable only if “CI” and “release” are explicit, mutually exclusive build modes; that is not true for the current GitHub Actions release model, so an environment-variable check alone would be fragile.

---

## Side-Effect Inventory

| Change | Observable effect | Assessment |
|---|---|---|
| `mtime = 0` | `tar -tvf` and preserving extractors show January 1970; wheel expansion installs epoch-dated SDK files | Undesirable for incremental upgrades; see finding above |
| `uid/gid = 0`, `uname/gname = root` | Root or `--same-owner` extraction produces root-owned files instead of CI-builder ownership | Usually desirable for distribution archives; non-root extraction remains owned by the extracting user |
| Sorted artifact members | Archive hashes no longer depend on directory enumeration order | Desirable; manifest-first contract is preserved |
| Mixed sorted files/directories in `add_tree()` | Changes the ordering contract consumed by `_lock_and_expand()` | Blocking data-loss regression |
| `sorted(os.walk(...))` | Holds every yielded directory and its file lists until the walk completes | Avoidable peak-memory increase for large SDK trees; the proposed streaming fix removes it |
| Stable archive bytes | All archive hashes/cache keys change once, and later identical rebuilds converge | Expected migration effect |

Hardlink anchor names may change because sorting chooses a deterministic first path, but the extracted hardlink relationship remains equivalent. Compression size may also move slightly because member order changes; neither appears correctness-sensitive.

---

## Test and CI Evidence

### Local tests at the exact PR head

The source was exported from commit `2c4e68029adf728922cbc519d54930eb4b619505` into scratch and tested with TheRock's venv:

```text
> D:\projects\TheRock\.venv\Scripts\python.exe -m unittest tests.fileset_tool_test tests.archive_util_test
Ran 20 tests in 1.235s

OK (skipped=1)
```

The nine PR-added tests also passed independently in 0.562 seconds. They do not exercise `add_tree()` through `_lock_and_expand()`, which is why the ordering regression is not detected.

### PR checks

At review time, `gh pr checks` reported 137 passing, four failing, six cancelled, and 33 skipped checks.

- [Linux Python package build](https://github.com/ROCm/TheRock/actions/runs/33094183267/job/98618178546): passed.
- [Windows Python package build](https://github.com/ROCm/TheRock/actions/runs/33094183267/job/98635316187): passed.
- [Windows ROCm wheel test](https://github.com/ROCm/TheRock/actions/runs/33094183267/job/98639109147): passed.
- Linux wheel tests were cancelled after other failures in the workflow.
- [Windows rocFFT](https://github.com/ROCm/TheRock/actions/runs/33094183267/job/98637726834) failed because `rocfft-test_quick_suite` hit its 600-second CTest timeout.
- The two Linux rocGDB checks failed in jobs explicitly labeled `(xfail)`, including `gdb.dwarf2/dw2-param-error.exp` and timeout cases: [GPU job](https://github.com/ROCm/TheRock/actions/runs/33094183267/job/98618801724), [corefile job](https://github.com/ROCm/TheRock/actions/runs/33094183267/job/98618801207).
- [CI Summary](https://github.com/ROCm/TheRock/actions/runs/33094183267/job/98665579769) failed as a consequence.

Those GPU-test failures have no evident causal connection to the host-side tar-writing diff, but the overall PR CI is not green.

---

## Recommendations

### ❌ REQUIRED (Blocking)

1. Restore deterministic file-before-directory ordering in `add_tree()` and add an integration regression through the devel-wheel expansion path.

### ⚠️ Required before merge

1. Resolve or explicitly define the installed mtime behavior for `rocm-sdk-devel`, with coverage for upgrade/incremental-build semantics.
2. Rerun the cancelled Linux wheel coverage after the workflow's unrelated failures are cleared or selectively rerun those jobs.

---

## Conclusion

**Approval Status: ❌ CHANGES REQUESTED**

The artifact-archive normalization is otherwise convincing, but the shared `add_tree()` refactor currently violates an ordering assumption in the devel installer and demonstrably drops an archived empty directory. Fixing the ordering is small and should happen before merge. The epoch-mtime behavior should also be treated as an installed SDK semantic decision, not merely archive metadata.

Generated with Codex
