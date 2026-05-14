# PR Review: Add release prebuilt artifact reuse mode

* **PR:** [#5095](https://github.com/ROCm/TheRock/pull/5095)
* **Author:** marbre (Marius Brehler)
* **Branch:** `users/marbre/release-prebuilt-artifact-reuse` -> `main`
* **Reviewed:** 2026-05-06
* **Status:** OPEN

---

## Summary

Adds a "prebuilt artifact reuse" mode to the release workflows, allowing
release re-runs to repackage already-built artifacts from a fixed S3 prefix
instead of rebuilding from source. This is useful for rare cases where
release re-runs need to reuse manually patched artifacts or restrict to a
subset of targets.

**Net changes:** +1168 / -52 across 10 files

**Key components:**
1. New reusable workflow `copy_prebuilt_artifacts.yml` - copies from prebuilt prefix
2. New gating script `verify_artifacts_ready.py` - ensures the active producer succeeded
3. `prebuilt_prefix` input threaded through all release workflows
4. `artifact_manager.py copy` extended with `--stage=all`, `--source-prefix-only`, `--require-matches`
5. Tests for both new Python additions

---

## Overall Assessment

**:warning: CHANGES REQUESTED** - One blocking issue (pre-commit failure), otherwise well-designed

**Strengths:**

- Clean architectural pattern: fork between `build_source` and `copy_prebuilt` with a synthetic gate job
- Non-breaking change: `prebuilt_prefix` defaults to empty string, so existing callers are unaffected
- Proper gating via `verify_artifacts_ready.py` prevents silent failures
- Good test coverage for the new Python code
- Excellent inline comments explaining the prebuilt mode behavior
- Correctly skips PyTorch/JAX wheel dispatch in prebuilt mode (these must be built from source)

**Blocking Issues:**

- Pre-commit formatting failure

---

## Detailed Review

### 1. Pre-commit Failure

#### :x: BLOCKING: Pre-commit formatting check fails

The CI pre-commit job fails with formatting issues in two files:

1. `build_tools/artifact_manager.py` ~line 975: `family_map = (...)` multi-line expression should be single-line per black formatting
2. `build_tools/tests/artifact_manager_tool_test.py` ~line 1229: `artifact_manager.main(...)` call should be single-line

**Required action:** Run `pre-commit run --all-files` locally and commit the formatting fixes.

---

### 2. Workflow Design: `copy_prebuilt_artifacts.yml`

Well-structured reusable workflow. The no-op behavior when `prebuilt_prefix` is empty is a good design choice that keeps the downstream `needs:` graph stable without conditional plumbing.

All steps correctly gated with `if: ${{ inputs.prebuilt_prefix != '' }}`.

The `workflow_dispatch` trigger is a nice addition for manual re-staging.

No issues found.

---

### 3. Workflow Design: `multi_arch_release_linux.yml` / `multi_arch_release_windows.yml`

The fork pattern is sound:
- `build_source` (conditional on `prebuilt_prefix == ''`)
- `copy_prebuilt` (always runs, no-ops internally)
- `build_artifacts` (synthetic gate, `if: always()`, runs `verify_artifacts_ready.py`)

#### :bulb: SUGGESTION: Document the `if: always()` intent

The `if: ${{ always() }}` on `build_artifacts` is correct (one producer is always skipped), but this pattern is easy to misread as unsafe. The step comment explains the verify script, but a brief comment on the job-level `if` condition would help future readers:

```yaml
  build_artifacts:
    name: Build Artifacts
    needs: [build_source, copy_prebuilt]
    # always() because exactly one producer is skipped by design.
    if: ${{ always() }}
```

---

### 4. Workflow Design: `release_portable_linux_packages.yml` / `release_windows_packages.yml`

Different pattern from multi-arch (step-level conditionals instead of separate gate job), which makes sense since the build steps here are inline.

The `copy_prebuilt` job correctly waits for `setup_metadata` to resolve the family list, then the main build job depends on both `[setup_metadata, copy_prebuilt]`.

#### :bulb: SUGGESTION: Consider `--platform` on fetch commands

The "Fetch prebuilt artifacts" steps call `artifact_manager.py fetch` without an explicit `--platform` flag. This works because `fetch` derives the platform from environment variables set by the CI runner. Worth a brief comment noting this relies on env-based resolution to prevent confusion during debugging.

---

### 5. `verify_artifacts_ready.py`

Clean, minimal gating script. Good design decisions:
- Separate `decide()` function that's easy to test
- `main()` returns int rather than calling `sys.exit()` directly
- Strips whitespace from inputs (defensive against GitHub Actions whitespace)
- Clear docstring explaining the job graph topology

No issues found.

---

### 6. `artifact_manager.py` Changes

#### 6a. `parse_input_families()` helper

Good extraction. Accepting both `;` and `,` as separators is pragmatic given the mixed conventions across workflow inputs. Returning empty list for `--generic-only` is correct.

#### 6b. `--stage=all` support in `do_copy()`

Mirrors `fetch --stage=all` semantics. The test with the "orphan-artifact" (not produced by any stage) validates this correctly.

#### 6c. `--source-prefix-only` in `_create_source_backend()`

Mirroring dest's bucket/external_repo is the right approach. The error when `dest_output_root` is None is a good guard.

#### 6d. `_families_satisfied_by_matches()`

Parsing logic for extracting target families from filenames is sound. It correctly handles the `{name}_{component}_{target_family}.tar.(zst|xz)` naming convention.

#### 6e. `--require-matches` validation

Two exit paths:
1. Per-family validation (checks each input family against matched filenames)
2. Empty copy_requests fallback (catches the "no matches at all" case)

Both correctly use `sys.exit(1)` consistent with the existing error handling pattern in `do_copy()`.

#### :bulb: SUGGESTION: Consider `raise SystemExit(1)` over `sys.exit(1)` for new code

The existing `do_copy()` function already uses `sys.exit()`, so this is consistent. But for new code being added, `raise SystemExit(1)` (or better, raising a custom exception caught in `main()`) would be more testable. Not blocking since it matches the existing pattern.

---

### 7. Tests

#### `verify_artifacts_ready_test.py`

Tests are well-structured, focused on behavior, and cover all important scenarios:
- Both modes (source vs prebuilt)
- Success and failure paths
- Ignoring the inactive producer's result
- Edge cases (cancelled, skipped, whitespace prefix)

No anti-patterns detected.

#### `artifact_manager_tool_test.py` additions

`TestCopyExtensions` class has good coverage:
- `--stage=all` unions every topology artifact (including orphans)
- `--source-prefix-only` skips API lookup (mocking correctly)
- `--source-prefix-only` mirrors dest bucket (important invariant)
- `--require-matches` success/failure paths
- `--require-matches` with `--expand-family-to-targets` (both satisfied and unsatisfied)
- Empty source (no artifacts at all)

The `test_comma_separated_families_accepted` test for `parse_input_families` is useful.

No anti-patterns detected.

---

### 8. Security

- No secrets in workflow files
- `GITHUB_TOKEN` usage is standard (`${{ github.token }}`)
- No command injection risks (inputs are used in quoted contexts)
- AWS credentials via OIDC (`id-token: write`) following established pattern

No issues found.

---

## Recommendations

### :x: REQUIRED (Blocking):

1. Fix pre-commit formatting failures (black auto-format)

### :bulb: Consider:

1. Add a brief comment on the `if: always()` condition explaining why it's safe
2. Add a comment noting the `artifact_manager.py fetch` calls rely on env-based platform resolution

### :clipboard: Future Follow-up:

1. Consider migrating `do_copy()`'s `sys.exit()` calls to exceptions as part of a broader cleanup (tracks with existing tech debt)

---

## Testing Recommendations

- The `workflow_dispatch` trigger on `copy_prebuilt_artifacts.yml` should be tested manually with a real prebuilt prefix before first production use
- Verify the prebuilt fetch + tarball creation produces correct layouts by running through a dev release with a known prebuilt prefix
- Unit tests pass on both Ubuntu and Windows CI runners (confirmed: passing)

---

## Conclusion

**Approval Status: :warning: CHANGES REQUESTED**

The design is solid and the code is well-tested. The only blocking issue is the
pre-commit formatting failure, which is a trivial fix. Once formatting is fixed
and CI is green, this is ready for merge.
