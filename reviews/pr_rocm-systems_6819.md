# PR Review: ROCm/rocm-systems#6819

* **PR:** https://github.com/ROCm/rocm-systems/pull/6819
* **Title:** `[kpack] Add per-architecture page size and relocation type support`
* **Author:** `benrichard-amd`
* **Base:** `develop`
* **Head:** `users/benrichard-amd/kpack-archconfig`
* **Head SHA:** `961428c34c7f48517c0b622dd410009c9f2338fc`
* **Reviewed:** 2026-06-08
* **Scope:** Comprehensive review

---

## Summary

The PR introduces `ArchConfig` and threads architecture-specific page size and
relative relocation type through much of the ELF kpack surgery path. The final
diff changes 7 Python files with +89/-40 lines and currently leaves only the
x86_64 architecture config enabled.

## Overall Assessment

**CHANGES REQUESTED** - the transformation path still writes an x86_64
relocation type unconditionally, which breaks the non-x86 architecture support
this PR is trying to enable.

## Findings

### BLOCKING: Relocation rewrite still emits `R_X86_64_RELATIVE`

`set_pointer()` is used by the kpack transform to repoint wrapper pointers to
`.rocm_kpack_ref`:

* [`kpack_transform.py#L325-L334`](https://github.com/ROCm/rocm-systems/blob/961428c34c7f48517c0b622dd410009c9f2338fc/shared/kpack/python/rocm_kpack/elf/kpack_transform.py#L325-L334)
* [`operations.py#L197-L202`](https://github.com/ROCm/rocm-systems/blob/961428c34c7f48517c0b622dd410009c9f2338fc/shared/kpack/python/rocm_kpack/elf/operations.py#L197-L202)

That call reaches `update_relocation_addend()`, which still converts the
relocation to `R_X86_64_RELATIVE` and has an x86-specific docstring:

* [`operations.py#L223-L253`](https://github.com/ROCm/rocm-systems/blob/961428c34c7f48517c0b622dd410009c9f2338fc/shared/kpack/python/rocm_kpack/elf/operations.py#L223-L253)

On a future non-x86 entry in `_ARCH_CONFIGS`, this writes the wrong relocation
type into the ELF. The new verifier then uses `surgery.arch_config.r_relative`
and ignores relocations whose type does not match that value, so the bad
relocation can pass the new post-transform check instead of being reported:

* [`kpack_transform.py#L345-L358`](https://github.com/ROCm/rocm-systems/blob/961428c34c7f48517c0b622dd410009c9f2338fc/shared/kpack/python/rocm_kpack/elf/kpack_transform.py#L345-L358)

**Required action:** make `update_relocation_addend()` use
`surgery.arch_config.r_relative` when `convert_to_relative=True`, update the
docstring/imports, and add a unit test with a non-x86 `r_relative` value that
would fail if `R_X86_64_RELATIVE` is written.

### IMPORTANT: Unsupported ELF machines silently fall back to x86_64 constants

`get_arch_config()` returns `_DEFAULT_ARCH_CONFIG`, which is the x86_64 page
size and relocation type, for any unrecognized `e_machine`:

* [`types.py#L578-L587`](https://github.com/ROCm/rocm-systems/blob/961428c34c7f48517c0b622dd410009c9f2338fc/shared/kpack/python/rocm_kpack/elf/types.py#L578-L587)

That is risky for architecture-sensitive binary rewriting. If an unsupported
ELF is processed before its mapping is added, kpack will mutate it using x86_64
rules instead of failing before making changes.

**Recommendation:** either include the architecture configs this PR intends to
support, or make unknown `e_machine` values fail fast with a clear unsupported
architecture error. Keep an explicit x86_64 mapping for existing behavior.

### IMPORTANT: New architecture-dependent behavior is not covered by tests

The existing type tests still exercise the default x86_64 relocation type only:

* [`test_types.py#L5-L81`](https://github.com/ROCm/rocm-systems/blob/961428c34c7f48517c0b622dd410009c9f2338fc/shared/kpack/tests/elf/test_types.py#L5-L81)

The existing surgery/zero-page tests also remain tied to 4 KiB page assumptions
and do not validate that a configured non-default page size flows through
`map_section_to_load()`, `ProgramHeaderManager.allocate_vaddr()`,
`check_phdr_alignment()`, or `conservative_zero_page()`.

**Recommendation:** add focused synthetic tests for:

1. `RelaEntry.get_target_address()` and `targets_range()` with a non-default
   `r_relative`.
2. `update_relocation_addend()` preserving the architecture-specific relative
   relocation type.
3. `page_align_offset()`, `calculate_aligned_range()`, and at least one
   surgery-level path using a non-4 KiB `page_size`.

## CI Evidence

`gh pr checks` on 2026-06-08 showed:

* Python tests passed on Ubuntu and Windows for Python 3.10 and 3.12.
* C++ runtime tests passed on Ubuntu and Windows.
* `pre-commit` passed.
* TheRock CI summary failed because `hip-tests` shard 3 timed out after 120
  minutes. The job log shows the timeout while running HIP tests, with
  `MultiThreadTest` still active during cleanup. This does not directly cover
  the changed kpack Python path and does not disprove the relocation issue
  above.

I did not run local tests against the PR head; the local `rocm-systems`
submodule worktree is readable, but fetching the PR ref into its `.git`
directory was blocked by filesystem permissions.

## Conclusion

**Approval Status: CHANGES REQUESTED**

Fix the remaining x86_64 relocation write before merging. The architecture
configuration plumbing is the right shape, but the current transform path can
still produce invalid non-x86 ELF relocations and the tests do not exercise the
new non-default configuration paths.

---

AI-assisted-by: OpenAI Codex
