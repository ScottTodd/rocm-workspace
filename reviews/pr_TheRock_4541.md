# PR Review: Add a dedicated multi-arch stage for WSL rocdxg

* **PR:** [#4541](https://github.com/ROCm/TheRock/pull/4541)
* **Author:** jayhawk-commits (Joseph Macaranas)
* **Reviewed:** 2026-05-13
* **Base:** `main`
* **Branch:** `users/jayhawk-commits/wsl-rocdxg-stage-draft`

---

## Summary

Adds a dedicated `wsl-rocdxg` multi-arch CI stage that builds the WSL-only
`rocdxg` bridge library from `rocm-systems`. The stage is modeled as its own
entry in `BUILD_TOPOLOGY.toml` with a `THEROCK_ENABLE_WSL_ROCDXG` feature and
a `WSL` feature group. The CI job starts on a Windows runner for checkout and
Windows SDK discovery, then enters a WSL Ubuntu shell where artifact fetch,
configure, build, and artifact push happen using the Linux platform.

**Net changes:** +580 lines, -8 lines across 14 files

---

## Overall Assessment

**⚠️ CHANGES REQUESTED** — The PR is well-structured and CI passes, but there
is a log upload platform mismatch that splits this stage's outputs across two
S3 prefixes, and an unused CMake variable passed to the subproject. Both should
be resolved before merge.

**Strengths:**

- Clean separation of the WSL stage as its own build topology entry with proper
  dependency on `base`
- Good use of `WSLENV` path bridging for Windows SDK headers
- Thorough documentation in `docs/development/wsl_rocdxg.md`
- CMakeLists.txt guards (`FATAL_ERROR` if `THEROCK_WSL_WIN_SDK` not set)
- Build script uses `set -euo pipefail`
- CI passed end-to-end: the WSL stage completed in ~12 minutes with all steps
  succeeding

**Issues:**

- Logs upload to `windows/` S3 prefix while artifacts upload to `linux/`
- `THEROCK_BUNDLE_SYSDEPS` passed to subproject but unused

---

## CI Evidence

**Run:** [25810250320](https://github.com/ROCm/TheRock/actions/runs/25810250320)

**WSL ROCDXG job:** [75825366897](https://github.com/ROCm/TheRock/actions/runs/25810250320/job/75825366897?pr=4541) — **success** (15:56:30 → 16:08:16, ~12min)

Key step timings:
| Step | Duration | Notes |
|------|----------|-------|
| Set up WSL with Ubuntu | 3m40s | One-time WSL install overhead |
| Configure | 3m32s | Includes TheRock full configure |
| Build stage | 1m28s | rocdxg compile + install |
| Push stage artifacts | 3s | Small artifact |

The wsl-rocdxg job runs in parallel with compiler-runtime (~35min), so it
does not increase overall pipeline wall-clock time.

**Log locations (mismatch — see finding below):**
- Logs: https://therock-ci-artifacts.s3.amazonaws.com/25810250320-windows/logs/wsl-rocdxg/index.html
- Artifacts: https://therock-ci-artifacts.s3.amazonaws.com/25810250320-linux/index.html

**Configure log warnings:** `THEROCK_BUNDLE_SYSDEPS` and
`THEROCK_STAGE_INSTALL_ROOT` reported as unused CMake variables.

**Build log warnings:** Compiler warnings in upstream `rocm-systems` code
(bitfield sizing in `d3dkmdt.h`, format specifier mismatches, snprintf buffer
overflow potential). These are pre-existing upstream issues, not introduced by
this PR.

**Unrelated test failures:** `rocblas` and `rocprofiler-compute` tests failed
in the gfx94X-dcgpu test suite — unrelated to the WSL stage.

---

## Detailed Review

### 1. Workflow: `multi_arch_build_wsl_rocdxg_artifacts.yml`

#### ⚠️ IMPORTANT: Log upload goes to wrong S3 prefix

The "Upload stage logs" step (line 231) runs on the Windows host (no
`shell: wsl-bash {0}`), while the "Push stage artifacts" step (line 218)
runs inside WSL with `--platform linux`. The `post_stage_upload.py` script
auto-detects the platform via `platform.system().lower()` (it has no
`--platform` argument), so:

- **Artifacts** → `25810250320-linux/` (correct — artifacts are Linux)
- **Logs** → `25810250320-windows/logs/wsl-rocdxg/` (misleading — this is
  a Linux-platform stage)

This splits the stage's outputs across two S3 prefixes, making it confusing
to find related logs and artifacts. Someone looking at the Linux artifact
index won't see the wsl-rocdxg logs, and someone looking at the Windows log
index will find logs for a stage that doesn't exist in the Windows pipeline.

**Recommendation:** Either:
1. Run the log upload step inside WSL (`shell: wsl-bash {0}`) so
   `platform.system()` returns `'Linux'`, or
2. Add `--platform` support to `post_stage_upload.py` and pass
   `--platform=linux` in this workflow

Option 2 is more explicit and doesn't require the WSL shell to remain
active for the log upload.

#### 💡 SUGGESTION: Consider the `Report` step shell context

The "Report" step (line 206) runs with the default `bash` shell (Windows
host) and does `ls -lh "${THEROCK_HOST_BUILD_DIR}"/artifacts/*.tar.xz`.
Since `THEROCK_HOST_BUILD_DIR` is a Windows-style path with backslash
(`${{ github.workspace }}\build-wsl-rocdxg`), this works in Git Bash on
Windows but is fragile. Consider using forward slashes for consistency, or
explicitly setting `shell: wsl-bash {0}` here too.

### 2. CMake: `core/wsl-rocdxg/CMakeLists.txt` and `core/CMakeLists.txt`

#### ⚠️ IMPORTANT: Unused `THEROCK_BUNDLE_SYSDEPS` in subproject

In `core/CMakeLists.txt` (line 249), the `therock_cmake_subproject_declare`
passes `-DTHEROCK_BUNDLE_SYSDEPS=OFF` to the wrapper subproject. But
`core/wsl-rocdxg/CMakeLists.txt` doesn't use `THEROCK_BUNDLE_SYSDEPS`
anywhere — it just generates and runs the build script. The configure log
confirms CMake reports it as unused.

**Recommendation:** Either:
1. Remove `-DTHEROCK_BUNDLE_SYSDEPS=OFF` from the `CMAKE_ARGS` in
   `therock_cmake_subproject_declare` (if the outer configure already handles
   it), or
2. Add `set(THEROCK_BUNDLE_SYSDEPS OFF CACHE BOOL "" FORCE)` to the wrapper
   CMakeLists.txt to acknowledge and consume the variable

Option 1 is simpler — the variable doesn't serve a purpose inside the
wrapper subproject.

### 3. Build Topology: `BUILD_TOPOLOGY.toml`

#### 💡 SUGGESTION: Consider `disable_platforms` on the artifact

The `wsl-rocdxg` artifact entry has no `disable_platforms`, which is fine
given the `FATAL_ERROR` guard in CMakeLists.txt and the dedicated feature
group (`WSL`, defaulting to `OFF`). However, many other Linux-only artifacts
use `disable_platforms = ["windows"]` as an additional guard. While WSL is a
special case (it's not quite Linux and not quite Windows), adding a comment
explaining why `disable_platforms` is intentionally omitted would help future
readers understand the decision.

### 4. Workflow: `multi_arch_build_portable_linux.yml`

#### 💡 SUGGESTION: Stage numbering comment is fragile

The PR renumbers all stage comments (3 → 4, 4 → 5, etc.) to insert
`wsl-rocdxg` at position 3. This is fine for now, but these comments have
a history of getting out of sync as stages are added. Consider whether the
numbering adds enough value to maintain, or whether stage names alone
suffice.

### 5. Artifact Descriptor: `core/artifact-wsl-rocdxg.toml`

The descriptor defines `lib`, `dev`, `doc` components, all pointing to
`core/wsl-rocdxg/stage`. This matches the `COMPONENTS` list in
`therock_provide_artifact()`. The installed files from the CI log confirm
the stage produces:

- `lib/`: `librocdxg.so`, `librocdxg.so.1`, `librocdxg.so.1.1.0`,
  `librocdxg.pc`
- `lib/cmake/rocdxg/`: CMake config files
- `share/doc/rocdxg/`: `LICENSE.md`

This correctly maps to `lib`, `dev`, and `doc` components. No issues.

### 6. Build Script: `core/wsl-rocdxg/wsl_build_rocdxg.sh.in`

The generated build script is clean and well-guarded. Uses `set -euo pipefail`,
validates inputs, and runs cmake configure/build/install + copy to stage dir.

#### 💡 SUGGESTION: `rm -rf` of build/install/stage dirs

Line 30 does `rm -rf "$build_root" "$install_root" "$stage_root"` for a clean
build every time. In CI this is fine (fresh workspace each run), but for local
developer iteration this means no incremental builds. This is acceptable for a
wrapper subproject that builds quickly (~88 seconds per CI), but worth noting
for future reference.

### 7. Documentation

The new `docs/development/wsl_rocdxg.md` is thorough and well-structured,
covering execution model, build topology, configure behavior, workflow
differences, and troubleshooting. Cross-references from `ci_overview.md`,
`windows_support.md`, and the development README are all appropriate.

No issues.

### 8. Security

The `WSLENV` line at step "Push stage artifacts" (line 221) bridges
`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_SESSION_TOKEN` into WSL.
This is necessary for the artifact push to authenticate with S3 from within
WSL. The credentials come from the `configure_aws_artifacts_credentials`
action and are short-lived OIDC tokens. No concerns.

---

## Recommendations

### ⚠️ IMPORTANT:

1. **Fix log upload platform mismatch** — logs should go to the `linux/`
   S3 prefix alongside artifacts, not `windows/`. Add `--platform` support
   to `post_stage_upload.py` or run the upload from WSL.
2. **Remove unused `THEROCK_BUNDLE_SYSDEPS`** from the subproject
   `CMAKE_ARGS` to eliminate the CMake warning.

### 💡 Consider:

1. Add a comment on the `wsl-rocdxg` artifact in `BUILD_TOPOLOGY.toml`
   explaining why `disable_platforms` is not used (WSL is a special case).
2. Use forward slashes in `THEROCK_HOST_BUILD_DIR` env var for consistency.
3. Consider whether stage numbering comments in
   `multi_arch_build_portable_linux.yml` are worth maintaining.

### 📋 Future Follow-up:

1. Address upstream compiler warnings in `rocm-systems` rocdxg code
   (format specifier mismatches, snprintf buffer overflow, unused
   `ftruncate` return value) — not in scope for this PR.
2. Migration to Windows ARC build runners with WSL pre-installed (already
   noted in PR description).

---

## Testing Recommendations

- [x] CI run passes end-to-end (confirmed: all steps succeeded)
- [ ] Verify the log upload fix produces logs in the `linux/` S3 prefix
- [ ] Run `python build_tools/topology_to_cmake.py --validate-only` after
  any topology changes (author already validated)
- [ ] Run `python -m pytest build_tools/github_actions/tests/configure_ci_path_filters_test.py`
  (author already validated)

---

## Conclusion

**Approval Status: ⚠️ CHANGES REQUESTED**

The PR introduces a well-designed WSL stage with clean topology modeling,
good documentation, and passing CI. Two issues should be resolved before
merge: the log upload platform mismatch (logs going to `windows/` when
artifacts go to `linux/`) and the unused `THEROCK_BUNDLE_SYSDEPS` CMake
variable in the subproject. Neither is difficult to fix.
