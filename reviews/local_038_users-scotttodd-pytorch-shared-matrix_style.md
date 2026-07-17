# Style Review: users/scotttodd/pytorch-shared-matrix

**Branch:** `users/scotttodd/pytorch-shared-matrix`  
**Base:** `main`  
**Reviewed:** 2026-06-22  
**Commits:** 1

---

## Summary

This branch moves PyTorch build matrix policy into
`configure_pytorch_release_matrix.py`, threads that matrix through the
multi-arch CI build config, reports it in the CI summary, and has Linux/Windows
CI workflows consume the generated PyTorch matrix instead of hard-coded
`py3.12` / `release/2.10` values.

**Net changes:** 434 insertions, 71 deletions across 11 files.

---

## Overall Assessment

**Status:** APPROVED WITH RECOMMENDATIONS

No correctness blockers showed up in this pass. The workflow plumbing is
straightforward, and the focused tests pass. The main issue is style and API
shape in `configure_pytorch_release_matrix.py`: the script now has more
abstraction than the current callers need, which makes the policy harder to
read and update than it needs to be.

---

## Detailed Findings

### IMPORTANT: Trim the extra public matrix entry point

`build_tools/github_actions/configure_pytorch_release_matrix.py:127`

`generate_pytorch_matrix()` is now only a wrapper around
`generate_pytorch_matrix_for_release_type()` with an implicit
`release_type="dev"`. A repository-wide search found no callers of this wrapper
on the branch; the CLI and `configure_multi_arch_ci.py` both call
`generate_pytorch_matrix_for_release_type()` directly.

That leaves the script with two importable APIs for the same behavior, one of
which silently chooses `dev` semantics. Since this is internal code and the
branch is already updating callers, this looks like compatibility surface we do
not need.

**Recommendation:** Remove `generate_pytorch_matrix()` and keep one importable
function. While doing that, make the optional override arguments actual
defaults:

```python
def generate_pytorch_matrix_for_release_type(
    *,
    release_type: str,
    amdgpu_families: str,
    platform: str,
    python_versions: list[str] | None = None,
    pytorch_git_refs: list[str] | None = None,
) -> list[dict[str, str]]:
```

Then `configure_multi_arch_ci.py` can omit the explicit
`python_versions=None` and `pytorch_git_refs=None` arguments at lines 970-971.
That makes the "use policy defaults" path more obvious.

### IMPORTANT: The ref policy representation is heavier than the policy

`build_tools/github_actions/configure_pytorch_release_matrix.py:29`

The current policy is implemented as lists of `dict[str, object]`, plus helper
functions to select config dictionaries, look up explicit refs, extract
`pytorch_git_ref`, cast values back to strings/sets, and carry optional
`exclude_amdgpu_families` data.

That shape is flexible, but for the current behavior the policy is simpler:

- full release refs per platform
- reduced CI refs per platform
- unsupported AMDGPU families for selected refs

The dict-of-object approach makes simple policy updates harder to scan. It also
pushes the script into style-guide territory where a structured dict with
multiple fields should either be simplified or promoted to a named type.

**Recommendation:** Prefer a smaller policy model unless we need richer per-ref
metadata now. For example:

```python
PYTORCH_REFS = {
    "linux": ["release/2.9", "release/2.10", "release/2.11", "release/2.12", "nightly"],
    "windows": ["release/2.9", "release/2.10", "release/2.11", "release/2.12", "nightly"],
}

CI_PYTORCH_REFS = {
    "linux": ["release/2.10", "release/2.11", "release/2.12"],
    "windows": ["release/2.10"],
}

UNSUPPORTED_FAMILIES = {
    "linux": {
        "release/2.9": {"gfx125X-dcgpu"},
        "release/2.10": {"gfx125X-dcgpu"},
        "release/2.11": {"gfx125X-dcgpu"},
        "release/2.12": {"gfx125X-dcgpu"},
        "nightly": {"gfx125X-dcgpu"},
    },
}
```

Then `generate_pytorch_matrix_for_release_type()` can choose refs, look up
exclusions, and build rows directly. If we later need more per-ref metadata,
use a small `NamedTuple` or frozen dataclass instead of `dict[str, object]`.

### SUGGESTION: Let `build_pytorch` be the single workflow gate

`.github/workflows/multi_arch_ci_linux.yml:293` and
`.github/workflows/multi_arch_ci_windows.yml:210`

`configure_multi_arch_ci.py` now sets `build_pytorch = bool(pytorch_build_matrix)`
after generating the matrix. The workflow jobs then check both
`build_pytorch == true` and `pytorch_build_matrix != '[]'`.

This is harmless, but it duplicates the same condition in two places. Since the
matrix emptiness is already collapsed into `build_pytorch` in the build config,
the workflow expression could stay shorter and use only
`fromJSON(inputs.build_config).build_pytorch == true`.

If you prefer to keep the explicit matrix guard for GitHub Actions readability,
that is reasonable; it is just a bit more noise in already dense expressions.

---

## Test Evidence

Ran:

```powershell
D:/projects/TheRock/.venv/Scripts/python.exe -m pytest github_actions/tests/configure_pytorch_release_matrix_test.py github_actions/tests/configure_multi_arch_ci_test.py
```

Result: 83 passed, 1 skipped. Pytest reported a cache permission warning for
`build_tools/.pytest_cache`, but the tests completed successfully.

---

## Conclusion

The branch is functionally on track. Before opening this for review, I would
simplify `configure_pytorch_release_matrix.py` so the matrix policy reads like a
small table of refs and exclusions rather than a generic config framework. That
should reduce the diff, make future PyTorch version updates easier, and avoid
locking in an API shape before the manifest work needs it.
