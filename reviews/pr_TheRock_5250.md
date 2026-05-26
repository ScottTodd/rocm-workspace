# PR Review: ROCm/TheRock#5250

* **PR:** https://github.com/ROCm/TheRock/pull/5250
* **Title:** Use DWARF4 for ASAN builds to fix dwz compatibility
* **Author:** raramakr
* **Base:** `main`
* **Head:** `785a9d402fc4cbf096121548d92a5c9a63a11411`
* **Reviewed:** 2026-05-21
* **Net changes:** +19/-13 across 3 files

---

## Summary

This PR adds `-gdwarf-4` to the Linux sanitizer presets and passes
`THEROCK_SANITIZER` into the `amd-llvm` subproject so
`compiler/pre_hook_amd-llvm.cmake` can add DWARF4 flags to LLVM runtimes for
ASAN builds.

CI evidence was partially available: `gh pr checks` showed unit tests,
pre-commit, foundation, and compiler-runtime jobs passing, with many release
build jobs still pending at review time. `gh pr view` was unavailable in this
environment because GitHub CLI authentication was not configured, so PR metadata
was fetched through the public REST API.

## Overall Assessment

**CHANGES REQUESTED** - The packaging compatibility issue is plausible, but the
fix is applied at the wrong level and changes all users of the sanitizer presets
instead of the packaging path that invokes `dh_dwz`.

## Findings

### BLOCKING: `dh_dwz` compatibility is baked into the default sanitizer presets

The PR adds `-gdwarf-4` directly to the base `CMAKE_C_FLAGS` and
`CMAKE_CXX_FLAGS` for `linux-release-asan`,
`linux-release-host-asan`, and `linux-release-tsan`:

* [`CMakePresets.json` lines 46-49](https://github.com/ROCm/TheRock/blob/785a9d402fc4cbf096121548d92a5c9a63a11411/CMakePresets.json#L46)
* [`CMakePresets.json` lines 73-76](https://github.com/ROCm/TheRock/blob/785a9d402fc4cbf096121548d92a5c9a63a11411/CMakePresets.json#L73)
* [`CMakePresets.json` lines 99-102](https://github.com/ROCm/TheRock/blob/785a9d402fc4cbf096121548d92a5c9a63a11411/CMakePresets.json#L99)

That means any local, CI, or diagnostic build using these presets gets forced
down to DWARF4 even when no Debian packaging step is being run. The evidence
supports a narrower packaging-tool limitation: Debian bookworm/trixie package
`dwz` as 0.15, and the Debian manpage says `dwz` handles most DWARF5 but still
does not support some forms/sections including `.debug_str_offsets`. Sourceware
also described DWZ 0.14 as supporting most DWARF5 while excluding the
`.debug_str_offsets` class of cases.

The proposed change turns that post-processing limitation into a global
sanitizer build policy. That weakens the default debug-info format for sanitizer
developers and CI, and it makes TheRock's general build presets depend on the
capabilities of one packaging tool.

**Required action:** keep the default sanitizer presets on the toolchain's
normal DWARF behavior, and move this compatibility handling to the Debian
packaging path. Acceptable approaches include using a `dh_dwz` toolchain that can
handle the emitted debug info, disabling/overriding `dh_dwz` only for affected
sanitizer packages, or adding an explicit packaging-only compatibility option or
preset that passes `-gdwarf-4`. If TheRock intentionally wants these release
sanitizer presets to mean "Debian-package-compatible", name and document that
contract explicitly instead of making it an implicit downgrade.

References:

* Debian `dwz` package versions: https://packages.debian.org/search?keywords=dwz
* Debian bookworm `dwz` manpage: https://manpages.debian.org/bookworm/dwz/dwz.1.en.html
* DWZ 0.14 release notes: https://sourceware.org/pipermail/dwz/2021q1/001066.html

### IMPORTANT: TSAN scope is inconsistent with the LLVM runtimes hook

`linux-release-tsan` gets `-gdwarf-4` in the preset, but the nested LLVM
runtimes workaround only runs when `THEROCK_SANITIZER` is `ASAN` or
`HOST_ASAN`:

* [`CMakePresets.json` lines 90-102](https://github.com/ROCm/TheRock/blob/785a9d402fc4cbf096121548d92a5c9a63a11411/CMakePresets.json#L90)
* [`compiler/pre_hook_amd-llvm.cmake` lines 42-44](https://github.com/ROCm/TheRock/blob/785a9d402fc4cbf096121548d92a5c9a63a11411/compiler/pre_hook_amd-llvm.cmake#L42)

If TSAN packages have the same `dh_dwz` failure mode, this does not appear to
cover the compiler-rt runtimes path that motivated the hook. If TSAN packages do
not have that failure mode, then the preset change is over-scoped.

**Recommendation:** either include TSAN in the runtimes handling with evidence
that it is needed, or remove TSAN from this PR's DWARF4 changes and keep the fix
limited to the affected ASAN packaging flow.

### SUGGESTION: Correct the dwz version comment and describe the actual unsupported form

The new comment says this is for `dwz < 0.15`, but the PR description calls out
0.14/0.15 and current Debian stable/oldstable package data points at 0.15. The
claim that `dwz` "doesn't support DWARF5" is also broader than the published
tooling notes; the sharper statement is that these `dwz` versions cannot handle
the specific DWARF5 forms/sections being emitted, such as `.debug_str_offsets`.

**Recommendation:** if this hook remains, make the comment precise and include
the actual `dh_dwz` failure message or a link to the packaging bug it works
around.

## Testing Recommendations

Before merging a revised fix, run the sanitizer package build that reproduces
the `dh_dwz` failure and show both the failing log and the passing log. Also
verify a non-packaging sanitizer configure still uses the expected default DWARF
mode unless an explicit packaging compatibility option is selected.
