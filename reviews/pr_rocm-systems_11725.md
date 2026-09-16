# PR review: Preserve gfx1250-strict identity in kpack artifacts

- PR: https://github.com/ROCm/rocm-systems/pull/11725
- Reviewed: 2026-09-16
- Head: `f0b4097353f18e8862820009c438c79df36c539c`
- Base: `develop`
- Scope: correctness, tests, architecture, style, documentation, security, performance.

## Overall assessment

**CHANGES REQUESTED** — one reproduced correctness regression in architecture verification.

The parser changes preserve strict identity and the new tests cover strict/base separation, MIOpen CU suffixes, xnack normalization, and component-prefixed archives. However, scanning target directories also exposes AOTriton's directory aliases, which are not canonical artifact keys.

## Findings

### BLOCKING: Canonicalize AOTriton directory aliases before comparing architectures

Location: [verify_artifacts.py, lines 314–325](https://github.com/ROCm/rocm-systems/blob/f0b4097353f18e8862820009c438c79df36c539c/shared/kpack/python/rocm_kpack/tools/verify_artifacts.py#L314-L325).

The newly added directory scan rejects valid artifacts produced by `ArtifactSplitter` with `AotritonHandler`. The [handler maps](https://github.com/ROCm/rocm-systems/blob/f0b4097353f18e8862820009c438c79df36c539c/shared/kpack/python/rocm_kpack/database_handlers.py#L194-L197) `amd-gfx11xx` to bundle key `gfx11` and `amd-gfx120x` to `gfx12_0`; splitting preserves those original directories. The verifier instead compares raw directory matches `gfx11xx` and `gfx120x` against artifact-name matches `gfx11` and `gfx12` (the regex also truncates `gfx12_0`). `base_arch()` strips target features but does not perform these alias mappings.

Consequently, correctly split AOTriton artifacts are reported as cross-contaminated and verification fails. Previously their architecture-neutral filenames were not checked, so this is introduced by the directory scan.

**Required action:** Preserve complete artifact bundle keys and normalize directory identities using the relevant handler's canonical mapping. Add the focused verifier regression below, covering `amd-gfx11xx` and `amd-gfx120x` alongside a specific-target control. Retain the PR's strict/base rejection tests.

### Existing coverage and the missing regression test

The existing [AOTriton handler tests](https://github.com/ROCm/rocm-systems/blob/f0b4097353f18e8862820009c438c79df36c539c/shared/kpack/tests/test_database_handlers.py#L472-L510), `test_detect_family_arch` and `test_detect_various_architectures`, explicitly cover `gfx11xx -> gfx11` and `gfx120x -> gfx12_0`. They assert the result of `handler.detect()` and never invoke the verifier. The handler remains correct, so these tests cannot catch the verifier interpreting the same paths differently.

The existing [split-then-verify integration test](https://github.com/ROCm/rocm-systems/blob/f0b4097353f18e8862820009c438c79df36c539c/shared/kpack/tests/test_artifact_splitter_integration.py#L183-L267) exercises gfx1100/gfx1101 fat binaries without AOTriton payloads. The PR's new verifier tests exercise strict/base identities and MIOpen filenames, without AOTriton aliases.

Add this unit test beside the existing verifier tests in `tests/test_artifact_splitter_integration.py` (the imports below are already available there). It constructs the supported on-disk artifact layout and checks the verifier's acceptance contract. The payload contents are irrelevant to architecture separation; this check only examines paths. No mocks, GPU, or compiler invocation are needed.

```python
import pytest

from rocm_kpack.binutils import Toolchain
from rocm_kpack.tools.verify_artifacts import ArtifactVerifier


@pytest.mark.parametrize(
    "bundle_key,image_arch",
    [("gfx11", "gfx11xx"), ("gfx12_0", "gfx120x"), ("gfx942", "gfx942")],
)
def test_verifier_accepts_aotriton_bundle_layout(tmp_path, bundle_key, image_arch):
    artifact = tmp_path / f"aotriton_lib_{bundle_key}"
    kernel = (
        artifact
        / "ml-libs/aotriton/stage/lib/aotriton.images"
        / f"amd-{image_arch}/flash/attn_fwd/kernel.aks2"
    )
    kernel.parent.mkdir(parents=True)
    kernel.write_bytes(b"kernel payload")

    verifier = ArtifactVerifier(tmp_path, Toolchain())
    verifier._check_architecture_separation([artifact])

    result = verifier.results[-1]
    assert result.passed, result.details
```

This test checks valid layouts rather than duplicating the parser implementation or merely retesting the handler mapping. Its expected result is identical before and after the PR: valid artifacts must be accepted. The separate real-splitter reproduction below confirms these fixtures represent actual output layouts.

**Verified before/after results using this exact test:**

| Verifier revision | Result |
| --- | --- |
| PR parent `d378a17c534e578842474541f0a836b4e980d105` | **3 passed in 0.01s** |
| PR head `f0b4097353f18e8862820009c438c79df36c539c` | **2 failed, 1 passed in 0.03s** |

Only the two alias cases fail on the PR; the gfx942 control passes on both. The parent verifier accepts these layouts because it does not inspect architecture-neutral filenames beneath target directories. Expanding that inspection must preserve acceptance of valid layouts.

The [test file](D:/scratch/codex/pr11725/test_aotriton_verification.py) and [runner](D:/scratch/codex/pr11725/run_regression.py) are saved in scratch. The runner loads the database handler and verifier from each exact revision, uses the PR-head splitter module for its normalization helper, and uses the existing local checkout for other dependencies. These are focused unit runs, not full checkouts of both revisions.

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD = '1'
$env:PYTHONIOENCODING = 'utf-8'
D:/projects/TheRock/.venv/Scripts/python.exe D:/scratch/codex/pr11725/run_regression.py parent > D:/scratch/codex/pr11725/regression-parent.log
D:/projects/TheRock/.venv/Scripts/python.exe D:/scratch/codex/pr11725/run_regression.py head > D:/scratch/codex/pr11725/regression-head.log
```

Full output: [parent log](D:/scratch/codex/pr11725/regression-parent.log), [PR-head log](D:/scratch/codex/pr11725/regression-head.log). Both runs disable pytest's cache provider and specify a scratch cache override and scratch temporary directory.

## Validation and CI evidence

- [Kpack CI](https://github.com/ROCm/rocm-systems/actions/runs/35146795718) ran against the reviewed head. All four Python matrix jobs and both C++ runtime jobs passed. The [Ubuntu Python 3.10 log](https://github.com/ROCm/rocm-systems/actions/runs/35146795718/job/104964820046) reports **578 passed, 4 skipped in 3.09s**, including the strict-identity tests.
- Locally, all **30 new tests passed in 0.08s**. The harness loaded the PR-head versions of the database handlers, splitter, and verifier, with remaining dependencies from the existing local checkout (`1091c91191a7c0b475f178354e9b650739726bf8`). This is a targeted check, not a complete PR-head suite run.
- The same harness constructed AOTriton inputs, ran the real splitter, and passed its output to the PR verifier. Both family-alias artifacts failed; `gfx942` passed. No LLVM or GPU execution was needed for these database-only inputs.
- The [failed TheRock summary](https://github.com/ROCm/rocm-systems/actions/runs/35146870500/job/104968242101) reports cancelled Linux and MI455 builds. The [replacement build run](https://github.com/ROCm/rocm-systems/actions/runs/35147813520) remained queued at review time. These statuses do not establish a code failure.
- The [PR bot](https://github.com/ROCm/rocm-systems/actions/runs/35146793550/job/104964812882) failed because the description contains no accepted JIRA/issue reference. Resolve this metadata check separately.
- Test duration is absent from the PR description; the CI duration above supplies review evidence. Adding it to the description would satisfy the workspace's testing-metrics guidance.

No additional actionable style, documentation, security, or performance findings were identified in this diff. Full artifact builds and the author's RAND ELF-flag inspection were not reproduced locally.

## Local reproduction record

Harness: [reproduce.py](D:/scratch/codex/pr11725/reproduce.py). Full output: [result.log](D:/scratch/codex/pr11725/result.log).

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD = '1'
$env:PYTHONIOENCODING = 'utf-8'
D:/projects/TheRock/.venv/Scripts/python.exe D:/scratch/codex/pr11725/reproduce.py > D:/scratch/codex/pr11725/result.log
```

The harness invokes pytest with `-p no:cacheprovider`, an explicit scratch cache override, and scratch temporary files. Earlier attempts stalled creating pytest cache support files; disabling the cache provider allowed the checks to complete.

Relevant output:

```text
CHECK: Architecture Separation
✗ Found architecture cross-contamination
  ✗ aotriton_lib_gfx11: 1 files from other architectures
      - ml-libs\aotriton\stage\lib\aotriton.images\amd-gfx11xx\flash\kernel.aks2 contains gfx11xx
  ✗ aotriton_lib_gfx12_0: 1 files from other architectures
      - ml-libs\aotriton\stage\lib\aotriton.images\amd-gfx120x\flash\kernel.aks2 contains gfx120x
  ✓ aotriton_lib_gfx942: All files are gfx942 (checked 2 files)
30 passed in 0.08s
```

Generated with Codex
