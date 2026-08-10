# Branch Review: TheRock Testing Overview

**Branch:** `testing-documentation`  
**Repository base:** `upstream/main` (`1e3975eb5`)  
**Reviewed:** 2026-08-10  
**Commits ahead:** 26  
**Review scope:** Comprehensive review of the four documentation files changed
relative to `upstream/main`

---

## Summary

This branch adds a root-level testing overview describing why TheRock layers
testing across local development and CI, how changes to TheRock's major feature
areas are validated, and how ROCm subprojects are built and tested through
TheRock. It also links the new guide from the contribution and development
indexes and extends the Python testing standards with external references.

**Net changes:** 580 additions and 2 deletions across 4 files.

The proposed scope is appropriate for an initial PR. Framework testing, CI
infrastructure validation, deeper subproject policies, and diagrams can be
added independently without weakening the value of this first version.

---

## Overall Assessment

**CHANGES REQUESTED** - The document's structure and intended scope are ready
for review, but three documentation correctness and maintenance issues should
be fixed before the branch becomes the project's canonical testing guide.

**Strengths:**

- The introduction explains the release-confidence goal and the constraints of
  ROCm's broad support surface without reducing testing to regression detection.
- The repeated scope/design/validation/limitations structure makes the long
  feature-area sections navigable.
- Local development and CI are treated as execution environments, separately
  from unit and integration test categories.
- GitHub Actions guidance correctly emphasizes thin workflows, testable scripts,
  static checks, isolated release environments, and staged rollout.
- The subproject section now explains component CI, TheRock CI, submodule bumps,
  release testing, build-tree tests, and installed component tests at a useful
  introductory level.

**Blocking issues:**

1. The root README still says GPU testing is not documented and does not point
   readers to the new root guide.
2. Two Google Testing Blog references have their labels and destinations
   crossed.
3. A detailed snapshot of CI timings and runner usage will rapidly become stale
   in an otherwise evergreen overview.

---

## Detailed Review

### 1. Root README integration

**BLOCKING: The main testing entry point contradicts the new guide**

The root README's [Running tests section](https://github.com/ROCm/TheRock/blob/main/README.md#L342-L354)
still states that testing on real GPUs is in progress and will be documented
separately. This branch creates that documentation, including current GPU test
integration. The root README's [Development manuals list](https://github.com/ROCm/TheRock/blob/main/README.md#L356-L368)
also omits `TESTING.md`, even though that is the natural discovery point for a
new root-level guide.

Leaving the old sentence in place makes the repository's primary entry point
factually wrong and makes the new canonical document harder to discover.

**Required action:** Replace the stale GPU-testing sentence with a link to
`TESTING.md` and add the guide to the root README's development-manual list.

### 2. Python testing references

**BLOCKING: The 2017 and 2018 article links are swapped**

In the new [testing reference list](https://github.com/ROCm/TheRock/blob/f2740f50dff566b0413712baa5f959b1a74276cf/docs/development/style_guides/python_style_guide.md#L931-L937):

- "Only Verify State-Changing Method Calls" is labeled 2017-12 but points to
  the 2018 article about relevant method arguments.
- "Only Verify Relevant Method Arguments" is labeled 2018-06 but points to the
  2017 article about state-changing method calls.

**Required action:** Associate the state-changing-method title with
`2017/12/testing-on-toilet-only-verify-state.html` and the relevant-arguments
title with `2018/06/testing-on-toilet-only-verify-relevant.html`.

### 3. Volatile CI measurements

**BLOCKING: The CI metrics table will become stale operational documentation**

The [July 2026 metrics table](https://github.com/ROCm/TheRock/blob/f2740f50dff566b0413712baa5f959b1a74276cf/TESTING.md#L208-L218)
records exact wall times, build-runner hours, test-runner hours, GPU-family
counts, and test filters for several workflows. Those values change with runner
capacity, matrix configuration, filtering policy, and CI optimization work.
Dating the table prevents it from becoming historically false, but it will
quickly stop answering the reader's likely question about how the current CI
system behaves.

The strategic point is valuable: presubmit, postsubmit, and nightly validation
have very different cost and coverage. That point can be preserved without
making the overview responsible for maintaining a capacity snapshot.

**Required action:** Replace the exact operational measurements with a
qualitative comparison, or link to a maintained dashboard/configuration source.
If the snapshot is useful as historical evidence, move it to a dated analysis
or tracking issue and link to it as an example.

### 4. Test-category coverage language

**IMPORTANT: The category summary overstates current CI coverage and leaves the runtime scope ambiguous**

The category introduction says [tests in every category are run locally and in CI](https://github.com/ROCm/TheRock/blob/f2740f50dff566b0413712baa5f959b1a74276cf/TESTING.md#L87-L94),
but the Python limitations later acknowledge that [some tests have not been added to CI](https://github.com/ROCm/TheRock/blob/f2740f50dff566b0413712baa5f959b1a74276cf/TESTING.md#L340-L354).
The first statement reads as a description of current completeness, while the
second identifies a known exception.

The same table gives integration tests an unqualified 30-minute target even
though later sections describe deliberately longer scheduled and nightly test
suites. The value makes sense as a presubmit budget, but that scope is not in
the column heading.

**Recommendation:** Make the first statement normative (`should be runnable`
locally and `should be run` in CI), and rename the runtime column to something
like `Typical presubmit budget` or otherwise state which cadence it describes.

### 5. Drafting notes in the canonical document

**SUGGESTION: Move hidden TODOs to tracked follow-up work**

`TESTING.md` still contains several HTML-comment TODOs for examples, diagrams,
CI infrastructure, and expanded subproject guidance. They do not affect the
rendered page, but unowned TODOs in a canonical overview are easy to forget and
make the source look less settled than the rendered document.

Before landing, consider removing them and recording the planned follow-ups in
the PR description or linked issues. Keeping a comment is reasonable when it
points to a concrete tracking issue.

### 6. Repeated contribution pointer

**SUGGESTION: Avoid a heading whose only content duplicates the preceding table**

The new `Testing practices` subsection in `CONTRIBUTING.md` repeats the
`TESTING.md` link already present in the immediately preceding pull-request
standards table. Either the table entry or the subsection is sufficient. If the
subsection is intended to remain as a stable anchor, a sentence explaining how
the testing guide relates to contribution requirements would give it distinct
value.

---

## Recommendations

### REQUIRED (Blocking)

1. Update the root README to replace its stale GPU-testing statement and link
   the new testing guide.
2. Correct the two crossed Google Testing Blog links.
3. Remove or relocate the volatile CI-capacity snapshot.

### Recommended

1. Make local/CI coverage language aspirational where known gaps exist.
2. Scope the test-runtime targets to presubmit or another explicit cadence.

### Consider

1. Remove or track the remaining hidden TODOs.
2. Consolidate or enrich the repeated `CONTRIBUTING.md` testing pointer.

### Future Follow-up

1. Add framework integration coverage for PyTorch, JAX, and other downstreams.
2. Document validation, rollout, health checks, logging, and observability for
   self-hosted runners and cloud infrastructure.
3. Expand subproject test design, filtering, environment, and standard-runner
   policies.
4. Add diagrams after the textual lifecycle and relationships have stabilized.

---

## Verification

- Compared the branch against `upstream/main`; using local `main` would have
  incorrectly included unrelated upstream CI and JAX commits.
- Ran `git diff --check upstream/main...HEAD`; no whitespace errors were found.
- Ran pre-commit on all four changed documentation files; every applicable hook
  passed, including `mdformat` and the secret/file checks.
- Parsed local Markdown links in the changed files and confirmed that every
  local path target exists.
- Verified the Google Testing Blog article titles and dates against the linked
  pages.
- Inspected the referenced TheRock build-test implementation, workflow files,
  test-runner documentation, and test-filter documentation for consistency with
  the overview.
- No code tests or GPU jobs are needed for this documentation-only branch.

---

## Conclusion

**Approval Status: CHANGES REQUESTED**

The document has enough structure and content for the planned initial PR. Once
the three blocking documentation issues are fixed, the remaining suggestions
can be handled during review or deferred without holding the first version.

---

_Review generated by OpenAI Codex._
