# PR Review: Make artifact archives reproducible

* **PR:** https://github.com/ROCm/TheRock/pull/4265
* **Author:** `PeterCDMcLean`
* **Branch:** `users/pmclean/normalize_archive_metadata` → `main`
* **Head:** `2c4e68029adf728922cbc519d54930eb4b619505`
* **Reviewed:** 2026-08-28
* **Focus:** Correctness, side effects, and unintended consequences

---

## Summary

This PR makes artifact archives and the `rocm-sdk-devel` wheel's secondary tarball deterministic by normalizing tar member timestamps and ownership and by sorting member insertion order. The normalized metadata does not propagate uniformly through later packaging: release tarball and RPM staging replace the epoch mtimes, while the native DEB path preserves them for files that are not subsequently modified. The devel-wheel portion also has a more complex, order-sensitive extractor and exposes a separate data-loss regression.

**Net changes:** +280/-10 across five Python files, including nine new tests.

---

## Overall Assessment

**❌ CHANGES REQUESTED** — the reproducibility objective is sound, but the new mixed file/directory ordering causes a reproducible data-loss regression when the devel wheel is expanded. Epoch mtimes also create an incremental-build hazard after devel-wheel and native-DEB upgrades that should be addressed or explicitly accepted before merge.

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

### ❌ BLOCKING: Epoch mtimes can suppress downstream rebuilds after SDK upgrades

[`normalize_tarinfo()` forces every member mtime to zero](https://github.com/ROCm/TheRock/blob/2c4e68029adf728922cbc519d54930eb4b619505/build_tools/_therock_utils/archive_util.py#L12-L27). The devel-wheel extractor calls `tarfile.extract()` for regular files and directories, which restores that value; the reproduction above confirms an installed file mtime of `0.0`.

That matters because `rocm-sdk-devel` contains headers, libraries, and build metadata intended to be consumed by build systems. After upgrading the wheel in an existing environment, changed SDK inputs still appear older than already-built external objects and executables. Timestamp-based tools such as Ninja or Make can therefore skip recompilation or relinking unless users clean their build trees manually.

The same concern reaches at least one non-Python distribution path. The native-package workflow fetches artifacts without `--flatten`, so [`artifact_manager.py` uses `TarFile.extractall()` and restores the archive mtimes](https://github.com/ROCm/TheRock/blob/2c4e68029adf728922cbc519d54930eb4b619505/build_tools/artifact_manager.py#L428-L434). The DEB builder then stages those files with [`shutil.copytree()` and `shutil.copy2()`](https://github.com/ROCm/TheRock/blob/2c4e68029adf728922cbc519d54930eb4b619505/build_tools/packaging/linux/deb_package.py#L411-L451), whose [documented default behavior preserves file metadata including modification times](https://docs.python.org/3/library/shutil.html#shutil.copy2). As a result, untouched SDK inputs such as headers can remain dated January 1970 in the DEB payload. Files rewritten by RUNPATH conversion, stripping, or package generation will instead have later times, so the resulting package can contain a mixture of epoch and build-time mtimes.

This is a correctness risk, not only cosmetic metadata: upgrading the native SDK package can leave a changed header older than an existing object file and suppress the rebuild that should consume it.

#### Propagation through repackaging

| Output | What its staging path does | Result of this PR's `mtime = 0` | Practical consequence |
|---|---|---|---|
| Generic artifact `.tar.zst` | Writes normalized `TarInfo` directly | Preserved | Artifact bytes and metadata become deterministic; raw preserving extraction produces epoch-dated files |
| `rocm-sdk-devel` wheel | `tarfile.extract()` restores member metadata | Preserved | Changed installed SDK inputs can look older than downstream build outputs |
| Release `.tar.gz` | Fetches with `--flatten`; `ArtifactPopulator` writes new files, then system `tar` archives that staging tree | Replaced by flatten/staging time | Incremental freshness is retained, but this PR does **not** make final release tarballs timestamp-reproducible |
| Native DEB | Non-flattening `extractall()`, followed by metadata-preserving `copytree()`/`copy2()` | Preserved for untouched files; rewritten/generated files get later times | Native-package upgrades can have the same stale incremental-build hazard; payload timestamps may be internally inconsistent |
| Native RPM | The spec copies sources into `%{buildroot}` with `cp -R`, without the [`-p`/`--preserve=timestamps` option](https://www.gnu.org/software/coreutils/manual/html_node/cp-invocation.html) | Replaced by RPM staging time | Incremental freshness is retained, but this PR does **not** make final RPM payload timestamps reproducible |

DEB's `SOURCE_DATE_EPOCH` handling does not repair this: [`dpkg-buildpackage` derives the value from the newest changelog entry when it is unset](https://manpages.debian.org/bookworm/dpkg-dev/dpkg-buildpackage.1.en.html), and [`dpkg-deb` uses it to clamp tar-entry mtimes](https://manpages.debian.org/testing/dpkg/dpkg-deb.1.en.html), not to advance older ones, so an input mtime of zero remains zero. [RPM supports a `%build_mtime_policy`](https://rpm.org/docs/4.20.x/manual/buildprocess.html), but this repository does not set one in the generated spec or workflow. Ownership also follows different rules downstream: DEB's `--root-owner-group` and RPM's `%defattr(..., root, root, ...)` normalize package ownership independently, whereas release tarball flattening replaces the artifact owner with the staging user's ownership.

Other consumers are less exposed:

- `ArtifactPopulator` writes file contents itself and does not restore tar mtimes.
- Bootstrap paths create fresh `.prebuilt` markers, which drive new stage stamps.
- `install_rocm_from_artifacts.py` removes and recreates its output directory before extraction.

**Required action:** decide and test installed-time semantics for every preserving consumer, especially the devel wheel and native DEB packages. At minimum, document that an SDK upgrade requires a clean downstream build; silently presenting changed inputs as January 1970 is a surprising behavioral change.

#### Options and tradeoffs

The artifact archives and their final distribution formats do not necessarily need the same policy. Some repackaging paths already replace archived mtimes accidentally, while the devel wheel and DEB path can preserve them into installed build inputs.

| Option | Pros | Cons |
|---|---|---|
| **1. Normalize artifact archives, but assign fresh mtimes when materializing installable SDKs** | Keeps generic artifact hashes reproducible; wheel and DEB upgrades make installed headers and libraries newer than existing downstream outputs; makes the tarball/RPM/DEB/wheel policy intentional instead of depending on each copy primitive | Installed trees are not timestamp-reproducible; reinstalling identical contents can trigger unnecessary rebuilds; all preserving paths must be covered, including DEB staging, not just wheel extraction |
| **2. Store a deterministic, version-advancing timestamp such as `SOURCE_DATE_EPOCH`** | Archive and installed mtimes remain deterministic; later releases will usually look newer and trigger downstream rebuilds; follows a common reproducible-build convention; can be applied consistently to final tarballs, DEBs, RPMs, and wheels | Requires an explicit timestamp source in every archive-producing path; commit or release timestamps are not guaranteed to be monotonic in every workflow; identical file trees built from different commits can receive different archive hashes, weakening the PR's “same content, same SHA” goal |
| **3. Normalize generic artifact archives only; downstream packagers explicitly choose their own mtimes** | Directly solves the artifact collision prerequisite in issue #4202; keeps the canonical build artifact deterministic while allowing release tarballs, native packages, and wheels to use install-appropriate semantics | Requires an explicit policy at every repackaging boundary; final formats are reproducible only if their chosen policy is deterministic; more plumbing than changing a single low-level helper |
| **4. Normalize only in CI; preserve real mtimes for release builds** | CI jobs that contend for an artifact key can produce stable hashes; release installs retain useful mtimes if releases truly use a separate mode | “CI” and “release” overlap because releases and native packages are built in CI; identical source produces different archives across environments; CI no longer validates the archive behavior shipped by the release path; an ambient environment check introduces hidden policy into a low-level utility |
| **5. Keep epoch mtimes everywhere they survive and require clean downstream builds after upgrades** | Simplest implementation; strongest reproducibility for formats that actually preserve the normalized metadata; no additional timestamp plumbing | Preserves the stale incremental-build risk for wheels and DEBs; does not make the current release tarball or RPM path reproducible because those paths replace mtimes; shifts cleanup cost to SDK users |
| **6. Preserve real mtimes and make #4202 compare a canonical content hash instead of the compressed archive SHA** | Conflict detection can ignore metadata and compression differences directly; installed timestamps remain useful; can define exactly which attributes are semantically significant | Substantially more implementation and format complexity; archives themselves remain non-reproducible; requires producing, storing, and validating a second digest definition; broader than this prerequisite PR |

Option 1 has the cleanest separation of concerns if reproducible generic artifacts and safe incremental upgrades are both requirements. Option 3 is the lowest-scope change if reproducibility is only needed for generic artifact collision detection. Option 4 is workable only if “CI” and “release” are explicit, mutually exclusive build modes; that is not true for the current GitHub Actions release model, so an environment-variable check alone would be fragile.

---

## Side-Effect Inventory

| Change | Observable effect | Assessment |
|---|---|---|
| `mtime = 0` | `tar -tvf` and preserving extractors show January 1970; wheel expansion and untouched DEB inputs can install epoch-dated SDK files; release tarball and RPM staging replace the value | Undesirable for wheel/DEB incremental upgrades; inconsistent reproducibility across final formats |
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
2. Define and test installed mtime behavior for preserving SDK consumers, especially `rocm-sdk-devel` and native DEB packages.

### ⚠️ Required before merge

1. Rerun the cancelled Linux wheel coverage after the workflow's unrelated failures are cleared or selectively rerun those jobs.

---

## Conclusion

**Approval Status: ❌ CHANGES REQUESTED**

The generic artifact-archive normalization is otherwise convincing, but the shared `add_tree()` refactor currently violates an ordering assumption in the devel installer and demonstrably drops an archived empty directory. Fixing the ordering is small and should happen before merge. The epoch-mtime behavior should also be treated as an installed SDK semantic decision across wheels and native packages, not merely archive metadata; the current pipeline preserves it into DEBs but discards it from release tarballs and RPMs.

Generated with Codex
