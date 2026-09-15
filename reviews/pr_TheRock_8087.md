# Review: TheRock PR 8087

Reviewed 2026-09-15 at `75e0014a3435e1ed04d761f0f2c5aaccb7a3ca31`.

## Overall assessment

**CHANGES REQUESTED.** Two source-selection correctness problems warrant fixing before merge. The broader recommendation is to centralize repository initialization and evaluate reference-backed full checkouts before expanding sparse build checkouts.

## Findings

### BLOCKING: Shared build sources are missing or reconstructed incorrectly

[detect_external_repo_config.py, lines 348–358](https://github.com/ROCm/TheRock/blob/75e0014a3435e1ed04d761f0f2c5aaccb7a3ca31/build_tools/github_actions/detect_external_repo_config.py#L348) defaults every unchanged sibling/dependency to `projects/`. For `changed_projects=projects/rocblas`, the BLAS artifact includes `origami` and `rocroller`, so the result contains `projects/origami` and `projects/rocroller`. Their actual CMake source locations are `shared/origami` and `shared/rocroller`. Additionally, the same CMake file passes `shared/tensile` as `Tensile_TEST_LOCAL_PATH`, but this source is absent from the BLAS topology source list altogether.

[BLAS CMake](https://github.com/ROCm/TheRock/blob/75e0014a3435e1ed04d761f0f2c5aaccb7a3ca31/math-libs/BLAS/CMakeLists.txt) and [topology](https://github.com/ROCm/TheRock/blob/75e0014a3435e1ed04d761f0f2c5aaccb7a3ca31/BUILD_TOPOLOGY.toml) establish the mismatch. Builds enabling these components cannot use the required source directories. This demonstrates why artifact dependencies and source dependencies are different: expanding artifact siblings cannot recover a source directory absent from the metadata.

**Required action:** Preserve full repository checkouts until source selection covers the complete build input set. If sparse build checkouts remain, derive actual paths from authoritative build metadata and validate shared inputs with a BLAS build; adding a few hard-coded prefixes does not solve the missing-input problem.

### BLOCKING: The advertised full-checkout fallback is never consumed

[action.yml, lines 26–59](https://github.com/ROCm/TheRock/blob/75e0014a3435e1ed04d761f0f2c5aaccb7a3ca31/.github/actions/checkout-external-repo/action.yml#L26) selects branches solely from stage paths and `changed_projects`. Python emits `sparse_checkout_fallback_full=true` for unmapped inputs, but the action never reads it.

For an unknown project alone, stage paths are empty and changed_projects is nonempty, so the action skips checkout. For a mixture such as `projects/rocprim,projects/totally_unknown`, math-libs receives a partial checkout and other stages skip checkout. Neither case performs the promised full fallback. The new tests assert that the producer sets the flag, without checking the consumer's decision.

**Required action:** Make fallback override both sparse and skip branches, and test the end-to-end selection for unknown-only and mixed inputs.

### IMPORTANT: Source initialization gains another external-CI-specific implementation

[The new helper suite](https://github.com/ROCm/TheRock/blob/75e0014a3435e1ed04d761f0f2c5aaccb7a3ca31/build_tools/github_actions/detect_external_repo_config.py#L47) adds stage/source inference and a new checkout action rather than extending the common source-fetching interface. This makes source completeness depend on the CI entry point and adds maintenance obligations for nested paths, shared inputs, artifact siblings, and stage boundaries.

**Recommendation:** Normalize the external repository/ref into the source state TheRock expects, then use common source fetching and build/test workflows. Keep external event interpretation at the boundary. This does not require completing a wholesale CI rewrite in this PR; retaining the current full checkout is a viable smaller change.

## Relationship to the linked design discussions

- [Issue 4559](https://github.com/ROCm/TheRock/issues/4559) specifically proposes sparse support in `fetch_sources.py` for test-script fetching. This PR instead changes external-repository build checkouts. It is a different scope and does not implement that proposal. The issue itself supports sparse checkout in a narrower use case, so it should not be cited as rejecting sparse checkout categorically.
- [The 7243 discussion](https://github.com/ROCm/TheRock/pull/7243#discussion_r3875507239) and [issue 7782](https://github.com/ROCm/TheRock/issues/7782) support deriving source/artifact relationships from the build system. The wrong shared paths above are a concrete consequence of inferring physical source layout from separate metadata.
- [PR 3867](https://github.com/ROCm/TheRock/pull/3867) introduced reference repositories; [fetch_sources.py at this PR's head](https://github.com/ROCm/TheRock/blob/75e0014a3435e1ed04d761f0f2c5aaccb7a3ca31/build_tools/fetch_sources.py) already supports `--reference-dir` and its environment variable. Wiring mirrors into runner/test infrastructure is a useful general alternative, but requires measuring mirror availability, maintenance, cold/warm behavior, and full working-tree materialization. No evidence here establishes that it matches sparse checkout timing.

## CI and validation evidence

- All 183 reported PR checks inspected: 141 passed, 37 skipped, 5 failed (four component tests plus CI Summary). Unit tests passed on Linux and Windows.
- Downloaded logs for failed rocsparse, rocfft, hipkernelprovider, and rocjpeg jobs. They report component test failures; no causal link to the external checkout changes was established. These failures are not additional findings against this PR.
- [Author-linked external math-libs job](https://github.com/ROCm/rocm-libraries/actions/runs/34289638298/job/102275817020) succeeded, with checkout taking six seconds. Its log selects `projects/rocprim` plus hipcub, rocthrust, rocrand, and hiprand. It contains an earlier inline decision implementation and lacks the current fallback field. The overall external run failed. This establishes a successful narrow example, not coverage of the reviewed head or shared dependencies.
- No comparable baseline timing was collected; the claimed five-minute saving remains unverified. No local full build or checkout experiment was run. Correctness findings above follow directly from the changed selection logic and head-version CMake/topology.
- Raw CI logs are saved under `D:/scratch/codex/pr8087/`. Retrieval used `gh api repos/ROCm/TheRock/actions/jobs/<JOB_ID>/logs` for IDs `103038297652`, `103038296767`, `103038297193`, and `103015100655`; the external job used `gh api repos/ROCm/rocm-libraries/actions/jobs/102275817020/logs`.

## Suggested review comment

I would prefer to keep full external-repository checkouts and move checkout optimization into the common source-fetching layer. External CI should initialize the repository/ref state TheRock expects, then reuse the same build and test code.

There are already concrete source-completeness problems here: a rocblas change reconstructs unchanged origami/rocroller dependencies under `projects/`, although CMake uses `shared/`, and `shared/tensile` is not represented in the selection. The full-checkout fallback flag is also emitted but never used by the action.

The test-script optimization proposed in issue 4559 is narrower than sparse build checkouts. Before adding more path inference to external CI, I suggest evaluating the existing git mirror/reference support on our runners. If sparse checkout is still needed afterward, it should live in `fetch_sources.py`, with source inputs derived from the build system and external-repository validation completed before merge.

Generated with Codex
