# PR Review: ROCm/TheRock#4803

* **PR:** https://github.com/ROCm/TheRock/pull/4803
* **Title:** `[WIP] packaging: add Windows MSI installer for ROCm runtimes`
* **Branch:** `users/idass1990/windows-installer-packaging`
* **Base:** `main`
* **Reviewed:** 2026-06-15
* **Head SHA:** `f5339ecaea6c1b698acbeb9ddc07d8d4b196676f`
* **Net changes:** +1726 / -0 across 4 files

---

## Summary

This PR adds a Windows MSI WiX source generator, unit tests, and user/developer
documentation for ROCm runtime installers. The direction of using artifact TOML
descriptors as the package source of truth is reasonable, but the current
implementation has several correctness gaps that can produce incomplete MSIs or
MSIs with invalid Windows Installer component identity.

## Overall Assessment

**CHANGES REQUESTED** - The PR should not merge until the MSI component identity
rules, artifact descriptor semantics, stale documentation, and failing CI are
fixed.

## Detailed Findings

### [BLOCKING] Component GUIDs are reused for different install locations

The generator assigns each file component GUID from only `install_rel`:
[`generate_msi_wxs.py` lines 767-773](https://github.com/ROCm/TheRock/blob/f5339ecaea6c1b698acbeb9ddc07d8d4b196676f/build_tools/packaging/windows/generate_msi_wxs.py#L767-L773).
That path is relative to the package install root, but the actual MSI target
path also includes the versioned subdirectory built at
[`generate_msi_wxs.py` lines 719-724](https://github.com/ROCm/TheRock/blob/f5339ecaea6c1b698acbeb9ddc07d8d4b196676f/build_tools/packaging/windows/generate_msi_wxs.py#L719-L724).
It also ignores which package is being generated, even though `hip-runtime` and
`runtimes` share artifacts and install to different subdirectories:
[`generate_msi_wxs.py` lines 95-152](https://github.com/ROCm/TheRock/blob/f5339ecaea6c1b698acbeb9ddc07d8d4b196676f/build_tools/packaging/windows/generate_msi_wxs.py#L95-L152).

That means `bin/foo.dll` gets the same Component GUID when installed under
`hip-runtime-7.14.0`, `hip-runtime-7.15.0`, and `runtimes-7.14.0`. Microsoft
documents that changing the target location of a component resource requires a
new component code; otherwise component reference counting, repair, and
uninstall behavior can be damaged. See Microsoft's guidance on
[changing component codes](https://learn.microsoft.com/en-us/windows/win32/msi/changing-the-component-code)
and [consequences of breaking component rules](https://learn.microsoft.com/en-us/windows/win32/msi/what-happens-if-the-component-rules-are-broken).

**Required action:** Derive component GUIDs from the full component identity,
including package identity and final target location, or remove the version and
package variability from the install path if components are meant to be shared.
Add tests that generate both `hip-runtime` and `runtimes`, and at least two
versions, and verify shared `install_rel` values do not reuse a Component GUID
when the target path differs.

### [BLOCKING] Bare `run` components are collected as empty instead of catch-all

The generator says it mirrors the artifact builder defaults, but it maps
`run` defaults to an empty include list:
[`generate_msi_wxs.py` lines 195-200](https://github.com/ROCm/TheRock/blob/f5339ecaea6c1b698acbeb9ddc07d8d4b196676f/build_tools/packaging/windows/generate_msi_wxs.py#L195-L200).
The collection loop then only globs the explicit/default include patterns:
[`generate_msi_wxs.py` lines 364-409](https://github.com/ROCm/TheRock/blob/f5339ecaea6c1b698acbeb9ddc07d8d4b196676f/build_tools/packaging/windows/generate_msi_wxs.py#L364-L409).
For a bare `run` entry, that means no files are collected.

The real artifact builder treats a bare `run` component as a catch-all after
the transitive `lib` component has claimed its files:
[`artifact_builder.py` lines 60-69](https://github.com/ROCm/TheRock/blob/f5339ecaea6c1b698acbeb9ddc07d8d4b196676f/build_tools/_therock_utils/artifact_builder.py#L60-L69).
The target descriptors rely on this behavior. For example, `amd-comgr` and
`hipcc` have bare `run` entries in
[`artifact-amd-llvm.toml` lines 49-57](https://github.com/ROCm/TheRock/blob/f5339ecaea6c1b698acbeb9ddc07d8d4b196676f/compiler/artifact-amd-llvm.toml#L49-L57).
Those files are part of the `runtimes` package definition, so the generated MSI
can omit required compiler runtime tools while still succeeding.

**Required action:** Reuse the artifact builder's `ArtifactDescriptor` /
`ComponentScanner` logic, or faithfully model the component extends chain and
empty-include catch-all semantics. Add tests using the real `artifact-amd-llvm`
and `artifact-core-kpack` style descriptors so bare `run` entries are covered.

### [BLOCKING] The generator can write an empty or incomplete WXS and still exit successfully

If no files are collected, the generator prints a warning but still writes a
WXS file:
[`generate_msi_wxs.py` lines 640-645](https://github.com/ROCm/TheRock/blob/f5339ecaea6c1b698acbeb9ddc07d8d4b196676f/build_tools/packaging/windows/generate_msi_wxs.py#L640-L645).
The tests explicitly lock in this behavior:
[`generate_msi_wxs_test.py` lines 406-414](https://github.com/ROCm/TheRock/blob/f5339ecaea6c1b698acbeb9ddc07d8d4b196676f/build_tools/packaging/windows/generate_msi_wxs_test.py#L406-L414).
Similarly, remote artifact downloads silently skip 404s:
[`generate_msi_wxs.py` lines 269-275](https://github.com/ROCm/TheRock/blob/f5339ecaea6c1b698acbeb9ddc07d8d4b196676f/build_tools/packaging/windows/generate_msi_wxs.py#L269-L275).

For packaging, an incomplete installer is worse than a failed generator. A
missing stage tree, missing archive, malformed descriptor, or empty package
should fail fast unless the component is explicitly optional and the package
definition expects it.

**Required action:** Convert these warning/skip paths into errors for required
package inputs. Preserve optionality only where it is represented in the
artifact descriptor or package definition, and add tests that verify missing
required files fail the command.

### [BLOCKING] End-user docs still claim unsupported installer behavior

The README still says the installer removes legacy System32 ROCm DLLs
automatically:
[`README.md` lines 132-147](https://github.com/ROCm/TheRock/blob/f5339ecaea6c1b698acbeb9ddc07d8d4b196676f/build_tools/packaging/windows/README.md#L132-L147).
The current generator has no such custom action, and the test suite asserts
that `RemoveLegacyROCmDlls` is absent:
[`generate_msi_wxs_test.py` lines 452-456](https://github.com/ROCm/TheRock/blob/f5339ecaea6c1b698acbeb9ddc07d8d4b196676f/build_tools/packaging/windows/generate_msi_wxs_test.py#L452-L456).

The README also documents `TARGETDIR` for install-time custom directories:
[`README.md` lines 29-33](https://github.com/ROCm/TheRock/blob/f5339ecaea6c1b698acbeb9ddc07d8d4b196676f/build_tools/packaging/windows/README.md#L29-L33),
but the generator wires the override through `INSTALLFOLDER`:
[`generate_msi_wxs.py` lines 682-692](https://github.com/ROCm/TheRock/blob/f5339ecaea6c1b698acbeb9ddc07d8d4b196676f/build_tools/packaging/windows/generate_msi_wxs.py#L682-L692).
The developer guide uses `INSTALLFOLDER`, so the two docs contradict each other.

**Required action:** Either implement the documented behavior and add tests for
it, or remove the System32 cleanup claim from the README and PR description.
Update the custom directory docs to use the property that the generated MSI
actually supports, and align the registry path documentation with the package
specific `registry_key` values.

### [IMPORTANT] CI is not clean

`gh pr checks` shows current failures on this head:

* `pre-commit` failed in run `27431608708`, job `81083118520`.
* `gitleaks / Gitleaks scan` failed in run `27431608720`, job `81083119358`.
* `Linux::release / Build Multi-Arch Stages / compiler-runtime / Stage - Compiler Runtime`
  failed/cancelled in run `27431609088`, job `81083173339`; the Windows compiler
  runtime job was cancelled after that.

For pre-commit, `gh run view 27431608708 --repo ROCm/TheRock --log-failed`
showed `black` reformatted
`build_tools/packaging/windows/generate_msi_wxs_test.py`, and `mdformat`
modified markdown tables in `build_tools/packaging/windows/msi-generator-usage.md`.

**Recommendation:** Run `pre-commit run --all-files`, inspect the gitleaks
result, and get the build checks green before requesting another review.

## Verification

Local verification performed from a detached scratch worktree at
`D:/scratch/codex/pr4803-wt`:

```powershell
D:\projects\TheRock\.venv\Scripts\python.exe -m pytest packaging/windows/generate_msi_wxs_test.py
```

Result: `41 passed in 0.24s`.

Also checked:

```powershell
git -c safe.directory=D:/projects/TheRock -C D:/projects/TheRock diff --check faa3419fe581219075e8b73a05ebe4cb1166f17e...f5339ecaea6c1b698acbeb9ddc07d8d4b196676f
```

Result: no whitespace errors.

No WiX compilation or MSI install/uninstall test was run locally.

---

Generated with Codex.
