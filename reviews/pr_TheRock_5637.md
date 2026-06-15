# PR Review: ROCm/TheRock#5637

* **PR:** https://github.com/ROCm/TheRock/pull/5637
* **Title:** Extract therock-tools Python package
* **Head:** `648e584bd35d13ac10bb91b3d02bbaef4aaa518d`
* **Base:** `7acb34f6d8972a840fa067f6b4634b00ad46fa00`
* **Reviewed:** 2026-06-05
* **Scope:** Comprehensive review, focused on Python package extraction, CI wiring, and build-tool compatibility

---

## Summary

This PR moves artifact, fileset, topology, storage, and GitHub helper code into a new `python/therock-tools` package while keeping in-tree compatibility wrappers under `build_tools`. The overall direction is reasonable, and the split unit-test workflow does collect both suites: locally, the PR snapshot collected 651 `build_tools` tests and 298 `python/therock-tools` tests.

However, the compatibility layer is incomplete for old `_therock_utils` module paths that still have live callers. This already breaks the artifact-structure validation jobs in CI.

**Net changes:** +3223 / -2580 across 83 files.

---

## Overall Assessment

**CHANGES REQUESTED** - The PR has a verified CI-breaking import regression and an incremental build dependency tracking issue.

## Findings

### BLOCKING: Moved `_therock_utils` modules are not aliased for live callers

The PR description says it keeps `_therock_utils` aliases for existing in-tree imports, but the moved modules do not have compatibility aliases under `build_tools/_therock_utils`. The root artifact structure test still inserts `build_tools` on `sys.path` and imports `_therock_utils.artifacts` and `_therock_utils.archive_util`:

* [`tests/test_artifact_structure.py`](https://github.com/ROCm/TheRock/blob/648e584bd35d13ac10bb91b3d02bbaef4aaa518d/tests/test_artifact_structure.py#L37-L42)

In the PR snapshot, `build_tools/_therock_utils` contains only `branch_config.py`, `exe_stub_gen.py`, `git_mirrors.py`, and `py_packaging.py`. A local collection check reproduces the CI failure:

```text
D:\projects\TheRock\.venv\Scripts\python.exe -m pytest tests/test_artifact_structure.py --collect-only -q
E   ModuleNotFoundError: No module named '_therock_utils.artifacts'
```

CI evidence matches this: both artifact validation jobs fail in the `Validate artifact structure` step:

* Linux job: https://github.com/ROCm/TheRock/actions/runs/26989163878/job/79655077100
* Windows job: https://github.com/ROCm/TheRock/actions/runs/26989163878/job/79657002372

There is another live old-path caller in [`external-builds/pytorch/windows_patch_fat_wheel.py`](https://github.com/ROCm/TheRock/blob/648e584bd35d13ac10bb91b3d02bbaef4aaa518d/external-builds/pytorch/windows_patch_fat_wheel.py#L18-L19), which still imports `_therock_utils.pattern_match`; `import _therock_utils.pattern_match` fails the same way against the PR snapshot.

**Required action:** Either update every remaining live caller to import `therock_tools.*` and add the correct source path, or add explicit compatibility shim modules under `build_tools/_therock_utils` for every moved module that still has in-tree consumers. Add a unit/collection test that covers the root artifact-structure import path so this does not regress again.

### IMPORTANT: CMake custom commands only depend on `fileset_tool.py`, not its moved implementation modules

The build rules now execute `python -m therock_tools.fileset_tool`, and `fileset_tool.py` delegates behavior to sibling modules such as `artifact_builder.py`, `artifacts.py`, `hash_util.py`, `os_util.py`, and `pattern_match.py`. The CMake dependencies and subproject fingerprinting still track only `therock_tools/fileset_tool.py`:

* [`cmake/therock_artifacts.cmake`](https://github.com/ROCm/TheRock/blob/648e584bd35d13ac10bb91b3d02bbaef4aaa518d/cmake/therock_artifacts.cmake#L175-L228)
* [`cmake/therock_artifacts.cmake`](https://github.com/ROCm/TheRock/blob/648e584bd35d13ac10bb91b3d02bbaef4aaa518d/cmake/therock_artifacts.cmake#L293-L300)
* [`cmake/therock_subproject.cmake`](https://github.com/ROCm/TheRock/blob/648e584bd35d13ac10bb91b3d02bbaef4aaa518d/cmake/therock_subproject.cmake#L883-L921)
* [`cmake/therock_subproject.cmake`](https://github.com/ROCm/TheRock/blob/648e584bd35d13ac10bb91b3d02bbaef4aaa518d/cmake/therock_subproject.cmake#L1095-L1102)

Before this refactor, depending on the single script was enough. After the split, editing `artifact_builder.py` or `pattern_match.py` can leave artifact population, flattening, and subproject dist-copy outputs stale in incremental builds because Ninja has no dependency edge to those files, and the subproject fingerprint content also omits them.

**Recommendation:** Define one CMake list for the relevant `therock_tools` source files, for example a `CONFIGURE_DEPENDS` `GLOB_RECURSE` over `python/therock-tools/src/therock_tools/*.py` or an explicit maintained list, and use it consistently in `DEPENDS` and `_fprint_files`.

## CI Notes

`gh pr view` could not be used because this session is not authenticated (`HTTP 401: Requires authentication`). Public `gh pr diff`, `gh pr checks`, and REST job metadata were available. Anonymous log download from the Actions jobs endpoint returned GitHub's `403 Must have admin rights to Repository`, so raw logs beyond public step metadata were not available.

Additional failed jobs were visible in `gh pr checks`, including Linux sanity, Windows sanity, and Windows Python wheel tests. Public step metadata shows where they failed, but without raw logs I did not attribute them to a source issue.

## Verification Performed

```text
D:\projects\TheRock\.venv\Scripts\python.exe -m pytest --collect-only -q
```

from the PR snapshot's `build_tools` directory: 651 tests collected.

```text
D:\projects\TheRock\.venv\Scripts\python.exe -m pytest --collect-only -q
```

from the PR snapshot's `python/therock-tools` directory: 298 tests collected.

```text
D:\projects\TheRock\.venv\Scripts\python.exe -m pytest tests/test_artifact_structure.py --collect-only -q
```

from the PR snapshot root: fails with `ModuleNotFoundError: No module named '_therock_utils.artifacts'`.

## Conclusion

**Approval Status: CHANGES REQUESTED**

Fix the `_therock_utils` compatibility regression first because it is already failing required CI. Then update the CMake dependency/fingerprint tracking so the extracted fileset implementation is safe for incremental build iteration.

Generated with Codex.
