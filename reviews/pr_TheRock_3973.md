# PR Review: #3973 - Add Windows packaging requirements RFC document

* **PR:** https://github.com/ROCm/TheRock/pull/3973
* **Author:** LiamfBerry
* **Base:** `main` ← `windows-packaging-rfc`
* **Reviewed:** 2026-05-13
* **Status:** OPEN

---

## Summary

This PR adds RFC0012, defining Windows packaging requirements for ROCm software
built with TheRock. It covers MSI packaging, Winget integration, directory
layout, multi-version installation, environment variables, registry keys,
driver compatibility, and redistribution models. The RFC is a companion to
[RFC0009](https://github.com/ROCm/TheRock/blob/main/docs/rfcs/RFC0009-OS-Packaging-Requirements.md)
(Linux packaging) and cross-references it throughout.

**Net changes:** +571 lines, -0 lines across 1 file

---

## Overall Assessment

**⚠️ CHANGES REQUESTED** - Well-structured RFC with good breadth of coverage,
but has CI failures and several content gaps that should be resolved before merge.

**Strengths:**

- Comprehensive coverage of Windows packaging concerns (MSI, Winget, registry,
  env vars, driver decoupling, redistribution)
- Good cross-referencing with RFC0009 for Linux parity
- Clear versioning and upgrade behavior matrix
- Practical examples for CLI installation commands

**Issues:**

- Pre-commit CI failures (trailing whitespace, mdformat table formatting)
- RFC README index not updated
- Package tables have gaps (packages referenced in meta-packages but missing
  from fine-grained table)
- Interactive CLI example is technically misleading for MSI

---

## Detailed Review

### ❌ BLOCKING: Pre-commit CI failures

The `pre-commit` job
[fails](https://github.com/ROCm/TheRock/actions/runs/25823079176/job/75869126782)
with two issues in `RFC0012-Windows-Packaging-Requirements.md`:

1. **Trailing whitespace** on two lines:
   - Line 239: `### ROCm Installer Branding ` (trailing space)
   - Line 349: paragraph ending with trailing space

2. **mdformat table reformatting** — the Meta Packages table (line ~196) and
   Fine-Grained Packages table (line ~211) have column widths that don't match
   mdformat's expected output. The Version Handling table (line ~401) also
   requires reformatting.

**Required action:** Run `pre-commit run --all-files` locally and commit the
fixes. The tables just need column-width adjustments to satisfy mdformat.

### ❌ BLOCKING: RFC README index not updated

[`docs/rfcs/README.md`](https://github.com/ROCm/TheRock/blob/main/docs/rfcs/README.md)
lists RFCs up to RFC0011. RFC0012 needs to be added to the index, per the
"Adding an RFC" instructions in that file.

**Required action:** Add
`- [RFC0012: Windows Packaging Requirements](./RFC0012-Windows-Packaging-Requirements.md)`
to the index in `docs/rfcs/README.md`.

### ⚠️ IMPORTANT: Incomplete fine-grained package table

Several packages appear in the meta-packages table but have no corresponding
entry in the fine-grained packages table:

| Package | Referenced in | Missing from |
|---------|--------------|--------------|
| `amdrocm-sysdeps` | `amdrocm-runtimes.msi`, `amdrocm-core.msi` | Fine-grained table |
| `amdrocm-opencl` | `amdrocm-core-sdk.msi` | Fine-grained table |
| `amdrocm-opencl-devel` | `amdrocm-core-devel.msi` | Fine-grained table |

This makes it unclear what these packages contain. Readers looking at the
fine-grained table to understand package contents will not find them.

**Recommendation:** Either add rows for these packages to the fine-grained
table, or add a note explaining why they are excluded (e.g., "defined in
RFC0009" or "contents TBD").

### ⚠️ IMPORTANT: Interactive CLI example is misleading

The "Interactive CLI mode" section (around line 299) shows this example:

```
msiexec /i amdrocm-core-sdk.msi

ROCm SDK Installer vX.Y.Z
Select components to install (space to toggle, enter to confirm):

  [x] HIP API headers and CMake configuration
  ...
```

MSI does not support console-based interactive menus. Running `msiexec /i`
without `/quiet` opens a standard Windows Installer GUI dialog, not a TUI with
`[x]` checkboxes. This example implies a custom launcher/wrapper application
that doesn't come from the MSI framework.

**Recommendation:** Either:
- Clarify that this interactive experience requires a separate launcher
  application that invokes MSI under the hood, or
- Replace the example with a description of the MSI dialog-based UI, or
- Note that the interactive CLI is provided by a ROCm-specific launcher tool
  (separate from `msiexec`)

### ⚠️ IMPORTANT: Device-specific use cases lack formatting

The five use cases under "Device-Specific Architecture Packages" (lines ~366–396)
are written as plain text paragraphs without structured formatting. For example:

```
1. **ISV installer invokes ROCm Runtime Core via winget**:

Winget starts launcher
Launcher automatically detects available GPU architectures
Runs installers for each GPU architecture (host installers and per device installers)
```

These read as bulleted steps but are formatted as consecutive lines, which
renders poorly in markdown.

**Recommendation:** Format each use case's steps as a numbered or bulleted list.

### 💡 SUGGESTION: Architecture naming inconsistency

The document uses `gfx-110x` (with hyphen, line 356) in one place but
`gfx1100` (no hyphen, line 395) elsewhere. TheRock uses the convention
`gfx110X` (capital X, no hyphen) for architecture family references.

**Recommendation:** Standardize on one naming convention, preferably matching
TheRock's existing pattern (`gfx110X`).

### 💡 SUGGESTION: OpenCL section wording

The sentence (line 182):

> "OpenCL will largely in part be sustained and no changes are expected to be
> implemented."

"Largely in part" is redundant. Consider simplifying to:

> "OpenCL will be sustained as-is and no changes are expected."

### 💡 SUGGESTION: `amd_comgr_3.dll` rename context

The OpenCL section mentions renaming `amd_comgr_3.dll` to `amd_comgr_opencl.dll`
"so that it can be shipped alongside the driver version 26.30 in Q3." This
references a specific driver version and timeline that may go stale. Consider
either removing the driver-version detail or noting it as a motivating example
rather than a binding requirement.

### 💡 SUGGESTION: `ROCM_PATH` "last-writer-wins" is stated twice

The "last-writer-wins" behavior for `ROCM_PATH` is explained both in the
Environment Variables section (line 458) and in the Registry Requirements
section for `CurrentVersion` (line 489). Consider consolidating into a single
note or cross-referencing to avoid redundancy.

### 📋 FUTURE WORK: Mapping to TheRock build outputs

The PR description mentions "how SDK components map to TheRock build outputs"
as a goal, but the RFC focuses on installer requirements rather than the
mapping from TheRock's artifact system (stages, components, `artifact-*.toml`)
to MSI packages. This mapping will likely need a follow-up RFC or appendix as
the implementation progresses.

---

## Recommendations

### ❌ REQUIRED (Blocking):

1. Fix pre-commit failures (trailing whitespace + mdformat table formatting)
2. Add RFC0012 to the `docs/rfcs/README.md` index

### ✅ Recommended:

1. Add missing packages (`amdrocm-sysdeps`, `amdrocm-opencl`) to the
   fine-grained packages table or explain their omission
2. Clarify that the interactive CLI example requires a launcher application
   separate from `msiexec`
3. Format the device-specific use case steps as markdown lists

### 💡 Consider:

1. Standardize GPU architecture naming to match TheRock conventions (`gfx110X`)
2. Simplify the OpenCL section wording
3. Remove or soften the driver-version reference in the comgr rename context
4. Consolidate the duplicate "last-writer-wins" explanations

---

## Testing Recommendations

Documentation-only change — no functional tests needed. Pre-commit must pass.

---

## Conclusion

**Approval Status: ⚠️ CHANGES REQUESTED**

The RFC is a solid requirements document that fills an important gap in TheRock's
packaging story. The blocking issues are straightforward to fix (pre-commit
formatting + README index). The important items around package table completeness
and the interactive CLI example should also be addressed before merge to avoid
reader confusion, but are less mechanical to resolve and may require input from
the packaging team.
