# PR Review: ROCm/TheRock#4205

* **PR:** https://github.com/ROCm/TheRock/pull/4205
* **Title:** `[Triton][Windows] Enable nightly releases of triton_windows`
* **Author:** `m-gallus`
* **Head:** `ROCm:michal/triton-windows-2` at `9c178364dace8f404a43ebdd06f4ef522b0badf7`
* **Base:** `main`
* **Reviewed:** 2026-05-28
* **Net changes:** +75 / -27 across 8 files
* **CI evidence:** `gh pr checks` reported no checks for the branch; the PR body says test result is awaiting.

---

## Summary

This PR wires Windows nightly PyTorch wheel builds to check out and build `triton_windows`, publish the wheel, and include it in version/output handling. The direction is reasonable, but the diff also changes global ROCm dev package versioning and adds untested behavior to version helper scripts.

## Overall Assessment

**CHANGES REQUESTED** - The global dev-version change should not land as part of a Windows Triton enablement PR, and the new Windows Triton output behavior needs explicit tests and CI evidence.

---

## Findings

### BLOCKING: Global ROCm dev wheel versions are shortened without justification

[`build_tools/compute_rocm_package_version.py#L143-L147`](https://github.com/ROCm/TheRock/blob/9c178364dace8f404a43ebdd06f4ef522b0badf7/build_tools/compute_rocm_package_version.py#L143-L147)

The PR changes every wheel `release_type == "dev"` version from `.dev0+<full git sha>` to `.dev0+<8-char sha>`. That is a repository-wide package coordinate change, not a Windows Triton-specific change. Existing workflow help text and install examples still describe full-SHA dev versions, and downstream consumers may pin exact `rocm` versions from the existing shape.

**Required action:** Revert the `compute_rocm_package_version.py` and test expectation change from this PR. If shortening ROCm dev package versions is desired, make it a separate versioning PR with migration notes and updated docs. If only PyTorch/Triton wheel suffixes need a short SHA, implement that in the PyTorch suffix path instead of changing global ROCm package versions.

### IMPORTANT: PyTorch suffix fallback rewrites installed ROCm local versions

[`external-builds/pytorch/build_prod_wheels.py#L270-L285`](https://github.com/ROCm/TheRock/blob/9c178364dace8f404a43ebdd06f4ef522b0badf7/external-builds/pytorch/build_prod_wheels.py#L270-L285)

When `--version-suffix` is not passed, the fallback now imports `compute_rocm_package_version.get_git_sha()` and truncates the installed `rocm` package local version before deriving the PyTorch suffix. That makes the PyTorch/Triton wheel version no longer encode the exact installed ROCm package coordinate when the installed package has a full SHA. The comment about staging shipping a full SHA "until those wheels are rebuilt" is also misleading: old wheels will not be rebuilt.

**Recommendation:** Keep the fallback aligned with `build_tools/github_actions/determine_version.py::derive_version_suffix()` or factor out a shared helper. If normalization to a short local is intentional, name that behavior directly, test it, and replace the staging comment with accurate wording.

### IMPORTANT: `write_torch_versions.py` relies on hidden workflow env and lacks tests

[`build_tools/github_actions/write_torch_versions.py#L50-L92`](https://github.com/ROCm/TheRock/blob/9c178364dace8f404a43ebdd06f4ef522b0badf7/build_tools/github_actions/write_torch_versions.py#L50-L92) and [`build_windows_pytorch_wheels.yml#L125-L126`](https://github.com/ROCm/TheRock/blob/9c178364dace8f404a43ebdd06f4ef522b0badf7/.github/workflows/build_windows_pytorch_wheels.yml#L125-L126)

The script decides whether missing Windows Triton is fatal by reading `PYTORCH_GIT_REF` from the process environment. That dependency is only set as a job-wide workflow env, far away from the `write_torch_versions.py` call. The docstring says Windows expects `triton_windows`, but the implementation only requires it for `PYTORCH_GIT_REF=nightly`. There are also no unit tests for the new Windows/stable/nightly behavior.

**Recommendation:** Make the behavior explicit with a CLI flag such as `--pytorch-git-ref` or `--require-triton`, and add focused tests for:

1. Windows nightly requires `triton_windows`.
2. Windows stable allows no Triton output.
3. Linux still requires `triton`.
4. `triton_version` is written from a `triton_windows-*` wheel.

### IMPORTANT: Workflow and publishing changes have no CI evidence yet

The PR changes Windows build workflow logic, release upload filtering, and package index generation, but `gh pr checks https://github.com/ROCm/TheRock/pull/4205` reported no checks for the branch and the PR body says "Awaiting".

**Recommendation:** Add links to successful runs covering at least one nightly Windows build that produces `triton_windows`, one stable Windows build that does not require Triton, and the multi-arch release/publish path or an equivalent dry run.

### SUGGESTION: Inline Triton build args at the build command site

[`build_windows_pytorch_wheels.yml#L126`](https://github.com/ROCm/TheRock/blob/9c178364dace8f404a43ebdd06f4ef522b0badf7/.github/workflows/build_windows_pytorch_wheels.yml#L126), [`build_windows_pytorch_wheels.yml#L285`](https://github.com/ROCm/TheRock/blob/9c178364dace8f404a43ebdd06f4ef522b0badf7/.github/workflows/build_windows_pytorch_wheels.yml#L285), [`multi_arch_release_windows_pytorch_wheels.yml#L116`](https://github.com/ROCm/TheRock/blob/9c178364dace8f404a43ebdd06f4ef522b0badf7/.github/workflows/multi_arch_release_windows_pytorch_wheels.yml#L116), and [`multi_arch_release_windows_pytorch_wheels.yml#L254`](https://github.com/ROCm/TheRock/blob/9c178364dace8f404a43ebdd06f4ef522b0badf7/.github/workflows/multi_arch_release_windows_pytorch_wheels.yml#L254)

`TRITON_BUILD_ARGS` is defined at job scope and used much later in a `cmd` invocation. The manifest step already keeps its conditional `--triton-dir` next to the command that needs it.

**Suggestion:** Use a call-site conditional for `--triton-dir ... --build-triton`, or at least make it a step-local environment variable on the build step.

### SUGGESTION: Explain or split the `s3_management/manage.py` changes

[`build_tools/third_party/s3_management/manage.py#L93-L116`](https://github.com/ROCm/TheRock/blob/9c178364dace8f404a43ebdd06f4ef522b0badf7/build_tools/third_party/s3_management/manage.py#L93-L116)

Adding `v4/whl` and `triton_windows` is plausibly related to release index generation, but the PR description does not explain why this third-party fork needs to change for the Windows Triton build path. This file is operationally sensitive because it controls which packages are indexed in S3.

**Suggestion:** Add the rationale and a validation command/result to the PR description, or split this into a separate index-management PR. Also replace the non-ASCII ellipsis in the new comment with plain ASCII.

---

## Testing Recommendations

* Run `build_tools` tests after reverting or justifying the versioning change:
  `D:/projects/TheRock/.venv/Scripts/python.exe -m pytest tests/compute_rocm_package_version_test.py`
* Add and run tests for `write_torch_versions.py` under `build_tools/github_actions/tests`.
* For workflow validation, provide successful GitHub Actions runs for nightly and stable Windows PyTorch wheels, plus the multi-arch release/publish path.

---

## Conclusion

**Approval Status: CHANGES REQUESTED**

The Windows Triton wiring can move forward after the unrelated global versioning change is removed or separately justified, the version-output helper behavior is made explicit and tested, and CI evidence is added for the affected workflow paths.

Generated with OpenAI Codex.
