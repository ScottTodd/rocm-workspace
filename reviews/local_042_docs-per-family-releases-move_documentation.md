# Documentation Review: docs-per-family-releases-move

**Branch:** `docs-per-family-releases-move`
**Base:** `main`
**Reviewed:** 2026-07-01
**Commits:** 8
**Review Type:** Documentation

---

## Summary

This branch moves legacy per-family release instructions out of `RELEASES.md`,
refocuses the main release page on multi-arch releases, and updates README
release/status text for JAX and the production HUD URL.

**Net changes:** +1002, -925 across 3 files.

---

## Overall Assessment

**Status:** APPROVED with important documentation fixes recommended.

The high-level outline is logical: overview/status first, installation by
artifact type next, verification last. I did not find blocking documentation
problems, but there are a few navigation and clarity issues that should be
fixed before relying on this as the main install guide.

---

## Detailed Findings

### IMPORTANT: The moved legacy page has a broken relative link

[`docs/packaging/legacy_per_family_releases.md:565`](https://github.com/ROCm/TheRock/blob/27d19ec12c86ea556c451c6ee38fdf3b5acd6756/docs/packaging/legacy_per_family_releases.md#L565)
links to `docs/development/artifacts.md`. After moving this text under
`docs/packaging/`, that relative path resolves as
`docs/packaging/docs/development/artifacts.md`, which does not exist.

**Recommendation:** Change the target to `../development/artifacts.md` or the
repo-root form `/docs/development/artifacts.md`.

### IMPORTANT: Several self-links drifted from their rendered heading anchors

[`RELEASES.md:30`](https://github.com/ROCm/TheRock/blob/27d19ec12c86ea556c451c6ee38fdf3b5acd6756/RELEASES.md#L30)
still links to `#multi-arch-releases`, but the heading is now
`## About multi-arch releases`, whose rendered anchor is
`#about-multi-arch-releases`.

The new legacy index table also keeps mixed-case fragments such as
`#rocm-for-gfx94X-dcgpu`,
`#torch-for-gfx110X-all`, and `#jax-for-gfx120X-all` at
[`docs/packaging/legacy_per_family_releases.md:44`](https://github.com/ROCm/TheRock/blob/27d19ec12c86ea556c451c6ee38fdf3b5acd6756/docs/packaging/legacy_per_family_releases.md#L44),
[`docs/packaging/legacy_per_family_releases.md:46`](https://github.com/ROCm/TheRock/blob/27d19ec12c86ea556c451c6ee38fdf3b5acd6756/docs/packaging/legacy_per_family_releases.md#L46),
and
[`docs/packaging/legacy_per_family_releases.md:51`](https://github.com/ROCm/TheRock/blob/27d19ec12c86ea556c451c6ee38fdf3b5acd6756/docs/packaging/legacy_per_family_releases.md#L51).
GitHub heading IDs are lowercased, so these should use `gfx94x`, `gfx110x`,
and `gfx120x` in the fragment.

**Recommendation:** Update the manual TOC/index fragments after the heading
renames and move.

### IMPORTANT: The legacy page says to use `--find-links`, but examples use `--index-url`

[`docs/packaging/legacy_per_family_releases.md:38`](https://github.com/ROCm/TheRock/blob/27d19ec12c86ea556c451c6ee38fdf3b5acd6756/docs/packaging/legacy_per_family_releases.md#L38)
to
[`docs/packaging/legacy_per_family_releases.md:40`](https://github.com/ROCm/TheRock/blob/27d19ec12c86ea556c451c6ee38fdf3b5acd6756/docs/packaging/legacy_per_family_releases.md#L40)
says packages "must be installed using" `--find-links`, but every install
command in that legacy section uses `--index-url`. That interrupts the flow
because the overview tells readers to expect one pip option and the actionable
commands use another.

**Recommendation:** If the examples are correct, change the overview to
`--index-url`. If `--find-links` is still required for some legacy channel,
add a short note explaining when to use each option.

### SUGGESTION: Clean up small typos and wording issues

These are minor, but worth fixing while the release docs are being reorganized:

- [`RELEASES.md:66`](https://github.com/ROCm/TheRock/blob/27d19ec12c86ea556c451c6ee38fdf3b5acd6756/RELEASES.md#L66):
  "kernels downloads" should be "kernel downloads".
- [`RELEASES.md:120`](https://github.com/ROCm/TheRock/blob/27d19ec12c86ea556c451c6ee38fdf3b5acd6756/RELEASES.md#L120)
  and
  [`docs/packaging/legacy_per_family_releases.md:34`](https://github.com/ROCm/TheRock/blob/27d19ec12c86ea556c451c6ee38fdf3b5acd6756/docs/packaging/legacy_per_family_releases.md#L34):
  "commandline" should be "command-line".
- [`docs/packaging/legacy_per_family_releases.md:59`](https://github.com/ROCm/TheRock/blob/27d19ec12c86ea556c451c6ee38fdf3b5acd6756/docs/packaging/legacy_per_family_releases.md#L59):
  "about the each package" should be "about each package".
- [`RELEASES.md:582`](https://github.com/ROCm/TheRock/blob/27d19ec12c86ea556c451c6ee38fdf3b5acd6756/RELEASES.md#L582)
  and
  [`RELEASES.md:596`](https://github.com/ROCm/TheRock/blob/27d19ec12c86ea556c451c6ee38fdf3b5acd6756/RELEASES.md#L596):
  "Multiarch" is inconsistent with the rest of the page's "multi-arch" term.
- [`docs/packaging/legacy_per_family_releases.md:7`](https://github.com/ROCm/TheRock/blob/27d19ec12c86ea556c451c6ee38fdf3b5acd6756/docs/packaging/legacy_per_family_releases.md#L7)
  to
  [`docs/packaging/legacy_per_family_releases.md:9`](https://github.com/ROCm/TheRock/blob/27d19ec12c86ea556c451c6ee38fdf3b5acd6756/docs/packaging/legacy_per_family_releases.md#L9):
  the caution sentence would read more naturally if split into two sentences:
  one saying the page documents historical artifacts while they remain
  available, and one saying no new per-family releases will be generated.

---

## Verification

- Reviewed `README.md`, `RELEASES.md`, and
  `docs/packaging/legacy_per_family_releases.md`.
- Ran `git diff --check main..HEAD`; no whitespace errors were reported.
- Ran targeted same-file anchor and local-path checks against the changed docs.
- No dedicated typo checker (`typos`, `codespell`, `cspell`) was available on
  PATH, so typo review was manual plus targeted text searches.

---

## Conclusion

The branch is directionally sound and the main outline is easier to follow than
the previous combined release page. I would fix the broken link, stale anchors,
and `--find-links`/`--index-url` mismatch before merging or publishing the
reorganized release docs.
