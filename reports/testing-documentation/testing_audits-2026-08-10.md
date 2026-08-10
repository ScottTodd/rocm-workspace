# TheRock TESTING.md policy and implementation coverage audits

Audit date: 2026-08-10  
TheRock branch: `testing-documentation`  
TheRock commit: `cd8139386`

## Executive summary

`TESTING.md` has a sound high-level structure for the initial documentation PR.
The feature-area template (scope, design for testing, validation methods, and
limitations) is useful for humans and can support the planned follow-up work.
The document does not need a major rewrite before landing.

Two additions would make the policy substantially easier to audit and to use
from a future coding-agent skill:

1. Add a short, general **coverage model** that distinguishes whether a test is
   merely defined, locally runnable, selected by CI, scheduled at an intentional
   cadence, blocking, and monitored for health.
2. Add a **subproject coverage contract** requiring each shipped artifact or
   component to declare its supported surface, test entry points, CI selection
   keys, test tiers/cadence, blocking status, and explicit limitations.

The most urgent implementation finding is not a missing component suite. The
current branch already has a generated consumer graph, a committed test-policy
file, and an RFC describing dependency-based selection. The remaining problem
is that targeted subproject CI crosses three identifier spaces without an
implemented authoritative mapping:

- subtree names from the external repository configurations;
- generated consumer-graph keys and test-policy entries;
- keys in `build_tools/github_actions/fetch_test_configurations.py`.

Several names currently select no matching component job even when a suitable
test job exists under another spelling. Nightly and other run-all jobs mask
this problem. RFC0013 already identifies this as an open question. The first
feature sprint should complete that normalization layer and fail closed when a
changed project selects no meaningful tests.

The component inventory otherwise shows strong direct installed-test coverage
for most math, ML, communication, media, and profiler components. The largest
direct behavioral gaps are concentrated in base/compiler utilities, OpenCL and
some core tools, composable kernel/support libraries, RDC, and emulation tools.
Several of these have indirect or structural coverage, so they should not all
be treated as equally untested.

## Scope and terminology

This audit covers the current TheRock checkout. It does not attempt to inventory
all component-specific CI in the upstream standalone repositories. “No direct
test” below means no direct behavioral test executed by TheRock's build-test or
installed-component test paths.

The coverage classifications used below are:

| Class | Meaning |
| --- | --- |
| Direct behavioral | A test invokes the component or its public behavior directly. |
| Indirect behavioral | A dependent or product-level test exercises the component, but does not isolate it. |
| Structural | CMake/CTest checks files, libraries, symbols, SONAMEs, or package structure. |
| Build-only | CI proves that the configured build and artifact production complete. |
| Non-blocking | A test runs, but failure does not fail the workflow. |

These classes are deliberately not a ranking from “bad” to “good.” A component
usually needs a combination. The important distinction is what confidence each
layer actually provides.

# Audit 1: policy gaps not already documented

The following existing limitations are already documented in `TESTING.md` and
are not counted as new findings:

- the full platform/GPU/configuration matrix cannot run for every change;
- some Python tests are not yet included in CI;
- Python coverage is not continuously tracked or enforced;
- some API tests are skipped without credentials;
- packaging tests do not yet reuse all component suites across package types;
- build tests are serialized and not all are blocking;
- cross-repository workflow pins and release workflow parity are difficult;
- CI infrastructure, framework testing, and diagrams are planned follow-ups.

## A1. No minimum coverage contract for shipped components

The document explains available mechanisms but does not say what minimum set of
properties should be validated for each artifact or component. As a result,
“the project builds” can be the only automated signal for some shipped payloads
without that being visible in documentation or CI configuration.

A useful policy would require every shipped component to have, or explicitly
document the absence of:

- artifact/package structure validation;
- an installed consumer or behavioral smoke test;
- deeper component correctness tests at an intentional cadence;
- coverage for each supported operating system and any materially different
  runtime/backend;
- a local entry point matching the CI test as closely as practical.

Test-only support components can use a lighter contract, but should still be
classified explicitly instead of disappearing from the inventory.

## A2. “Test exists” is not the same as “test protects the product”

The policy does not yet distinguish these states:

1. test code exists;
2. the test is packaged or otherwise locally runnable;
3. CI can discover and select it;
4. it runs at a documented cadence and on a documented surface;
5. zero selected tests is an error;
6. its failure is blocking before the affected output is released;
7. skips, flakes, duration, and pass rate are monitored.

This gap is visible in the implementation audit: Mirage and rocJitsu build tests
run non-blocking on Linux; Windows sanity currently skips every test; and the
extended benchmark matrix is opt-in and expected-failure. A future audit or
agent skill needs these properties to avoid reporting false confidence.

## A3. Change-to-test selection is not part of the testing methodology

The document describes test filters and tiers but does not summarize or link how
the system determines which component tests are affected by a source change.
This is a critical part of correctness when presubmit testing is intentionally
selective. The current implementation and draft RFC0013 already introduce a
generated consumer graph, per-component policy levels, include/exclude
overrides, a drift check, and an `--explain` mode. `TESTING.md` should point to
that design and state the higher-level contract it serves.

The policy should state that selection logic is itself product logic and must:

- use a canonical mapping from changed paths/subprojects to test jobs;
- account for consumers and cross-component dependencies;
- fail closed, or deliberately run a broader suite, for unknown projects;
- have consistency tests proving every included source project maps to at least
  one intended validation path;
- make exclusions and reduced tiers visible in CI output.

## A4. Supported-surface coverage is described globally, not per component

The introduction correctly explains why every combination cannot run on every
change. It does not yet require each component to record which slices of its own
surface run in presubmit, postsubmit, nightly, or on-demand testing.

Without that record, it is difficult to distinguish intentional sampling from
accidental omission. The needed axes include, where relevant:

- Linux, Windows, WSL, and supported distro/container variants;
- GPU architecture/family and single- versus multi-GPU topology;
- build variant and feature flags;
- package format and install mode;
- test tier and cadence;
- blocking versus informational status.

The policy should not demand every cross product. It should demand an explicit,
reviewable sampling strategy and an accessible opt-in route for the remaining
supported configurations.

## A5. Product quality properties need explicit homes

The current page focuses primarily on correctness, installability, and workflow
behavior. It mentions build duration and artifact size, but only as metrics that
are currently observed after merge. It does not establish where the following
properties are validated:

- runtime performance and performance regressions;
- API/ABI compatibility between components and releases;
- binary/package size budgets;
- build time and test time regressions;
- numerical accuracy/tolerance policies for math libraries.

These do not all need detailed policies in the initial document. A short
statement that they are testable product properties, plus links to future
specialized policies, would keep the coverage model from equating “returns the
right answer once” with “works as expected.”

## A6. Test health and quarantine policy is missing

The planned infrastructure section covers runner and service health, but the
test suites themselves also need observability. The document does not yet cover:

- flaky-test detection and retry policy;
- criteria for disabling, excluding, or marking a test expected-failure;
- an owner and deadline for re-enabling quarantined tests;
- trends in skip counts, test counts, duration, and pass rate;
- detection of suites that silently collect zero tests;
- coverage erosion when quick/standard filters change.

This should become part of the proposed top-level “monitoring the health of the
testing system” section, without turning `TESTING.md` into an operations manual.

## A7. Release and packaging failure paths are under-specified

The GitHub Actions section covers isolated dev environments, manual dispatch,
and workflow reuse. The packaging section covers construction, installation,
and use. The policy does not yet call out transaction and lifecycle behavior:

- retry/idempotency after partial uploads or interrupted releases;
- prevention of cross-channel publication (dev/nightly/stable);
- upgrade, uninstall, reinstall, and coexistence behavior;
- rollback or safe recovery after a failed promotion;
- provenance/signing and verification of published payloads.

These are expensive integration scenarios, but release automation can fail in
ways that unit tests and a clean installation test will not detect. They are a
good later sprint rather than a blocker for the initial documentation PR.

## A8. User-facing examples and documentation are not treated as test inputs

The package guidance says installation tests should resemble user instructions,
which is good. The policy does not generalize this to executable examples,
sample projects, README commands, and public CMake package-consumption examples.
These are often the cheapest way to validate that an installed SDK works as a
user expects and that documentation does not drift.

## A9. Workflow orchestration contracts need explicit validation targets

The GitHub Actions guidance correctly recommends thin workflows, actionlint,
unit-tested scripts, and isolated dev runs. Those layers still do not fully
validate GitHub's event and orchestration semantics. The policy should identify
the workflow properties that need either static contract tests or real workflow
runs:

- `pull_request`, `push`, schedule, and manual trigger behavior;
- reusable-workflow input/output compatibility across repositories;
- permissions, secrets, and environment protections;
- conditional job selection and the risk of an unexpectedly empty matrix;
- concurrency, cancellation, retries, and summary-job propagation;
- whether an expected-failure or `continue-on-error` result is visible and
  intentionally non-blocking.

This is not a call to test every workflow edit with a multi-hour run. It defines
the contracts that thin scripts and unit tests should model, and the residual
GitHub-hosted behavior that still needs a focused dispatch or staged rollout.

# Audit 2: TESTING.md against the current TheRock implementation

## 2.1 Direct component coverage that is already present

The installed-component matrix has direct entries for most major product
libraries and tools. This is important context for the gap list.

| Area | Direct matrix coverage |
| --- | --- |
| Core/runtime | HIP tests, AMD SMI, `rocrtst`, hipFile, sanity checks |
| BLAS/solver/sparse | rocBLAS, hipBLAS, hipBLASLt, rocRoller, Origami, rocSOLVER, hipSOLVER, rocSPARSE, hipSPARSE, hipSPARSELt |
| PRIM/RAND/FFT | rocPRIM, hipCUB, rocThrust, rocRAND, hipRAND, rocFFT, hipFFT |
| Other math | rocWMMA, rocALUTION, hipTensor, libc++/libhipcxx modes, hipThreads and examples |
| ML | MIOpen, hipDNN, integration tests, samples, and all three providers |
| Communication/media/CV | RCCL, rocSHMEM, rocDecode, rocJPEG, RPP |
| Profiling/debug | AQLProfile, rocprofiler SDK/Compute/Systems, ROCgdb, ROCr Debug Agent |

The matrix definition is
`build_tools/github_actions/fetch_test_configurations.py`. The generic component
runner also explicitly fails if it discovers zero CTest tests, which is a good
pattern to preserve.

## 2.2 Included components without a direct TheRock behavioral test

The following table lists the clearest gaps. “Current confidence” records
indirect or structural coverage so these are not misrepresented as entirely
untested.

| Area/components | Current confidence | Missing TheRock coverage |
| --- | --- | --- |
| Base: `therock-aux-overlay`, `rocm-cmake`, `rocm-core`, `rocm_smi_lib`, `rocprofiler-register`, `rocm-half` | Builds, packaging, and downstream consumers | No direct installed or component-level behavioral entry; no declared coverage contract distinguishing infrastructure/header-only/runtime payloads. |
| Compiler: `amd-llvm`, `hipcc` | Sanity compiles/runs one HIP program; nearly all source builds consume the compiler; AMD COMGR has blocking build tests | No dedicated LLVM/device-libs/hipcc installed suite in TheRock. `THEROCK_BUILD_LLVM_TESTS` defaults off. |
| `hipify` | Builds and is a dependency of RCCL artifacts | No TheRock test that invokes the installed tool on representative input. |
| `rocm-kpack` | Indirectly exercised by GPU payload production/use | Its build-test registration is commented out in `core/CMakeLists.txt`; no direct component entry. |
| OpenCL: `ocl-icd`, `ocl-clr` | Linux CMake validates `libamdocl64.so`; artifacts and packages are built | No installed OpenCL compile/run workload in the component matrix. Windows does not get the Linux shared-library validation. |
| `hipInfo` | Built as a Windows runtime artifact | No direct invocation test. The Windows sanity suite currently skips all three of its test methods. |
| `therock-wsl-rocdxg` | WSL artifact build/upload workflow | No runtime or installed consumer test was found in that workflow. |
| Experimental `hrx` | Optional build integration | No direct test; acceptable only if recorded as an experimental exemption. |
| `hipBLAS-common` | Used by multiple BLAS-family builds/tests | No isolated contract/header/consumer test; coverage is entirely through consumers. |
| `composable_kernel` | Built with `BUILD_TESTING`, consumed by MIOpen and hipTensor tests | No component-matrix or build-test entry runs its own installed test suite. |
| `mxDataGenerator` support artifact | Built/packaged and may be used by other test clients | No direct test entry. It should be classified as test infrastructure if it is not a user component. |
| `rocprof-trace-decoder` | Shared-library structural validation and possible indirect rocprofiler SDK paths | No direct test of trace decoding/ATT behavior. |
| Deprecated `roctracer` | Bundled with and indirectly consumed by rocprofiler SDK | No direct compatibility/smoke test for existing roctracer clients. |
| `amd-dbgapi` | Linux shared-library validation; exercised by ROCgdb and Debug Agent tests | No isolated test; the Windows static-library build has no equivalent structural or behavioral validation. |
| RDC | Blocking CMake checks for libraries, symbols, binaries, and SONAMEs | No installed/GPU component job. This is a wiring gap: RDC already contains `tests/ci`, functional tests, and an installed `rdctst` payload. |
| `rocjitsu-hotswap` | Repackages a library built and structurally checked as part of rocJitsu | No test that loads the separately packaged hotswap artifact through its intended runtime path. |
| rocJitsu and Mirage | CTest build tests exist | On Linux both are included in the “other, non-blocking” build-test step, so failures do not gate CI. No installed artifact smoke test. |

Recommended interpretation:

- Start with RDC, OpenCL, WSL, hipify, and hotswap because they have clear
  user-visible runtime behavior not covered by a direct installed test.
- Treat base/header/support components separately. Many need a small consumer
  compile/package test rather than a large GPU suite.
- Treat amd-llvm, hip-clr, ROCR Runtime, and kpack as integration-heavy
  foundations. They have substantial indirect coverage, but should document
  which product tests are their intended contract and add focused tests for
  failure modes those consumers cannot isolate.

## 2.3 Targeted CI can select no matching component test

`test_tools/determine_rocm_test_dependencies.py` walks the committed consumer
graph according to `test_tools/test_policies.toml`. Unknown names only emit a
warning and remain self-only. `fetch_test_configurations.py` then includes a job
only when its key exactly matches one of the selected graph/policy names. The
graph has a drift check and the selector has 49 unit tests, but there is no
end-to-end consistency check across external paths, graph keys, policy values,
and matrix keys.

The following configured external-repository values currently have no exact
matrix hit in a targeted run. `configure_external_repo_ci.py` emits names with
their category prefix, such as `shared/origami`. The dependency script removes
only the literal `projects/` prefix, so `shared/` and `dnn-providers/` names
cannot match the unprefixed matrix keys.

| Repository | External changed-project names with no exact matrix hit |
| --- | --- |
| rocm-libraries | `shared/tensile`, `shared/origami`, `shared/mxdatagenerator`, `shared/rocroller`, `shared/stinkytofu`, `composablekernel`, `dnn-providers/miopen-provider`, `dnn-providers/hipblaslt-provider`, `dnn-providers/hip-kernel-provider`, `dnn-providers/integration-tests` |
| rocm-systems | `clr`, `hip`, `hipother`, `rdc`, `rocminfo`, `rocm-smi-lib`, `rocprofiler`, `rccl-tests`, `rocdbgapi` |

Not every entry should map one-to-one. Examples of the intended aliases or
consumer mappings are likely:

- `shared/tensile` -> `tensilelite` and relevant BLAS tests;
- `shared/origami` -> `origami`;
- `shared/rocroller` -> `rocroller` and hipBLASLt consumers;
- `dnn-providers/miopen-provider` -> `miopenprovider`;
- `dnn-providers/hipblaslt-provider` -> `hipblasltprovider`;
- `dnn-providers/hip-kernel-provider` -> `hipkernelprovider`;
- `dnn-providers/integration-tests` -> `hipdnn-integration-tests`;
- `clr`, `hip`, and `hipother` -> HIP/OpenCL/runtime tests;
- `rocr-runtime` -> `rocrtst` and HIP tests;
- `rocdbgapi` -> ROCgdb and Debug Agent tests;
- `rccl-tests` -> RCCL tests;
- `roctracer` -> rocprofiler SDK compatibility coverage.

There is also an underscore/hyphen mismatch inside the current selection
mapping: the consumer graph and policies select `hipdnn_integration_tests`,
while the matrix key is
`hipdnn-integration-tests`.

Several included source directories are absent from the external repository
configuration altogether. Shipped examples include
`rocm-libraries/projects/hipthreads`, `projects/rocalution`, `projects/rpp`,
`rocm-systems/emulation/rocjitsu`, `emulation/mirage`,
`projects/rocprof-trace-decoder`, and `shared/kpack`. Changes confined to an
unconfigured path currently leave `changed_projects` empty and therefore broaden
to all tests. In a mixed PR containing both configured and unconfigured paths,
only the configured paths narrow the matrix and the other components can be
omitted.

If no external project is matched at all, an empty `changed_projects` value
currently broadens to `*`, which runs all tests. The dangerous case is a PR that
contains both a recognized project and an unrecognized/aliased project: the
recognized project narrows the matrix while the other change can be silently
omitted.

The 49 existing tests for `determine_rocm_test_dependencies.py` live under
`test_tools/tests`, while `.github/workflows/unit_tests.yml` runs pytest only in
`build_tools` and `build_tools/scan_tools`. The consumer-graph drift workflow
regenerates and compares the graph, but does not run the selector unit tests or
`--validate-policies`. Therefore the selection tests and policy validation are
not part of the documented unit-test workflow.

## 2.4 Defined tests that are non-blocking or not automatically scheduled

| Test area | Current behavior | Risk |
| --- | --- | --- |
| rocJitsu/Mirage build tests on Linux | `therock-build-tests` uses `continue-on-error: true`; only AMD COMGR is split into a blocking step | Regressions are visible in logs but do not fail CI. |
| Extended benchmarks | All benchmark entries use `expect_failure: true` | Performance failures cannot gate changes or releases. |
| Extended functional/benchmark matrix | `test_artifacts.yml` defaults `run_extended_tests` to false, and no checked-in caller passes it as true | The README describes nightly execution, but the current workflow graph makes these manual/opt-in only. |
| Windows HIP ROCR backend | Optional entry is expected-failure; PAL is blocking | ROCR-on-Windows regressions remain informational until parity is achieved. |
| Manifest diff on automatic events | Workflow uses `continue-on-error` outside manual dispatch | Product-composition drift may not gate a PR; evaluate whether this is intentional observability or a missing release check. |

The policy should say that a non-blocking test supplies observability, not
release confidence, unless another blocking layer covers the same property.

## 2.5 Platform and configuration gaps

### Confirmed or strongly indicated gaps

- **rocFFT builds on Linux and Windows, but its correctness matrix entry is
  Linux-only.** The matrix contains an explicit Windows TODO. A Windows benchmark
  entry exists, but it is opt-in and expected-failure.
- **rocSOLVER builds on Linux and Windows, but its direct correctness job is
  Linux-only.** The matrix contains an explicit issue for Windows enablement.
  hipSOLVER does run on both platforms, which is useful indirect coverage but
  does not replace the rocSOLVER suite.
- **Windows sanity is currently a zero-effective-test job.** `rocminfo`, the HIP
  compile/run check, and `rocm_agent_enumerator` are all skipped on Windows.
- **RPP is opt-in and experimental on Windows, but its test job is Linux-only.**
  This is acceptable as a documented experimental limitation, not as implied
  Windows validation.
- **amd-dbgapi builds a Windows static library but its structural shared-library
  check is Linux-only, and its downstream direct tests are Linux-only.**
- **The libhipcxx HIPRTC mode is Linux-only in the matrix**, while its amdclang
  mode runs on Linux and Windows. Confirm whether HIPRTC use on Windows is a
  supported surface before classifying this as a defect.
- **WSL artifacts are built and uploaded but no WSL runtime test was found.**
- **Top-level CMake packaging/structural CTest execution is disabled in the
  Windows build workflow** with a TODO, so Windows relies more heavily on later
  artifact/component tests.

### Intentional Linux-only cases that should not be reported as parity bugs

- hipSPARSELt and rocRoller are currently gated out of Windows builds.
- RCCL, rocSHMEM, hipFile, rocDecode, rocJPEG, profiler tools, ROCgdb, Debug
  Agent, RDC, rocJitsu, and Mirage are disabled on Windows in topology or build
  logic.

An automated topology-to-test-matrix consistency audit could distinguish these
cases mechanically instead of relying on reviewer memory.

## 2.6 Dependency selection has a strong foundation but an incomplete boundary

RFC0013 and the current implementation define the dependency-selection depth
explicitly: level 4 walks direct consumers, level 3 walks the transitive closure,
and policy overrides add or remove non-derivable test targets. Foundational
components such as `amd-llvm`, `hip-clr`, and `rocr-runtime` are assigned level 3.
This resolves the earlier ambiguity around one-hop versus transitive selection.

The remaining risk is at the boundaries of that graph:

- external subtree paths are not authoritatively mapped to graph keys;
- graph keys and test-only policy values are not authoritatively mapped to
  matrix keys;
- `validate_policies()` intentionally permits non-graph test-only values, but no
  check proves those values resolve to real matrix jobs;
- the selector unit tests and policy validation are not run by the current unit
  or graph-drift workflows;
- `TESTING.md` does not yet explain what each gating level means for the builds
  and tests run by “TheRock CI” in rocm-libraries and rocm-systems.

That last item is well suited to a follow-up documentation section: changed
subtree -> normalized graph component -> gating-level consumer selection ->
matrix jobs, followed by the broader TheRock bump and nightly/release stages.

# Recommended feature sprints

## Sprint 1: Make test selection fail closed

- Complete RFC0013's normalization layer from external subtree names to consumer
  graph keys and from graph/test-policy values to matrix jobs.
- Add a consistency test asserting that every external project and every
  shipped first-party artifact has a declared validation disposition.
- Fail or broaden to all tests when a changed project has no valid mapping.
- Move/include `test_tools/tests` in the required unit-test workflow.
- Run `--validate-policies` in CI and validate test-only values against real
  matrix jobs.
- Document how gating levels change the builds/tests selected in rocm-libraries
  and rocm-systems “TheRock CI.”

This is the highest priority because it determines whether existing tests run
when they are needed.

## Sprint 2: Add a generated component coverage inventory

- Build on the consumer graph and test-policy metadata to record supported
  platforms/configurations, direct/indirect test jobs, cadence, and blocking
  status in machine-readable metadata.
- Generate a human-readable coverage report from that metadata.
- Compare supported platforms from `BUILD_TOPOLOGY.toml` with matrix platforms.
- Make missing mappings, zero tests, and undocumented exemptions CI failures.

This turns future audits into a routine check instead of a repository-wide
search exercise.

## Sprint 3: Wire existing but unused component tests

Suggested order:

1. RDC `tests/ci` and installed `rdctst` on appropriate GPU runners.
2. Composable Kernel's configured tests.
3. OpenCL installed compile/run smoke tests on supported platforms.
4. rocJitsu/Mirage promotion from non-blocking, then an installed smoke test.
5. WSL runtime smoke test.
6. hipify and rocJitsu hotswap user-path tests.

## Sprint 4: Close supported-platform holes

- Enable rocFFT and rocSOLVER correctness tests on Windows.
- Replace the all-skipped Windows sanity suite with small Windows-native checks,
  including `hipInfo` and a HIP compile/run test.
- Decide/document RPP Windows and libhipcxx HIPRTC Windows expectations.
- Add Windows structural/package CTest coverage or equivalent checks.

## Sprint 5: Establish product-quality and test-health signals

- Make selected performance checks scheduled and meaningful before considering
  gating thresholds.
- Track test counts, skips, flakes, retries, duration, and disabled tests.
- Define quarantine and promotion-to-blocking criteria.
- Add API/ABI, size, and build-time policies where their owning feature areas
  can act on the results.

Framework, packaging-lifecycle, release-transaction, and infrastructure-health
work can then proceed as the already planned parallel follow-ups.

# Document changes that enable recurring audits and an agent skill

## Recommended small structural additions to TESTING.md

### 1. General principle: coverage is multidimensional

Add a compact table or paragraph defining these independent axes:

| Axis | Example values |
| --- | --- |
| Validation method | static, unit, structural, installed integration, system |
| Execution location | local, CI |
| Surface | OS, GPU, build variant, feature flags, package format |
| Cadence | presubmit, postsubmit, nightly, on-demand |
| Enforcement | informational, expected-failure, blocking |
| Health | test count, skips, flakes, duration, owner/issue |

This preserves the document's high-level framing without defining unit and
integration tests at length.

### 2. Subproject coverage contract/template

Under “Testing subprojects through TheRock,” add a standard table for component
testing-strategy documents:

| Field | Required content |
| --- | --- |
| Source and artifact | Canonical source subtree/subproject and shipped artifact names |
| Supported surface | OS, GPU/topology, relevant flags and package types |
| Validation layers | Structural, direct behavioral, consumer/integration, performance |
| Local entry points | Commands/scripts that run without GitHub Actions |
| CI selection | Canonical job key and change/dependency aliases |
| Tiers and cadence | quick/standard/comprehensive/full and when each runs |
| Enforcement | blocking or informational |
| Limitations | Unsupported slices, skips, issue links, or explicit exemption |

Do not put an exhaustive hand-maintained table for all 40+ components directly
in `TESTING.md`; it will drift. Generate the inventory by combining the existing
consumer graph/test policies with topology and test-matrix metadata, or add a
small adjacent coverage registry, then link it from the policy.

### 3. Normative requirements needed by an agent

The current prose mostly describes practices. A skill will produce more
consistent reviews if the document includes a few explicit requirements:

- Each shipped component must have a declared validation disposition.
- Every CI test must have a local or otherwise accessible invocation.
- Every supported platform must have direct or explicitly documented indirect
  coverage at an intentional cadence.
- Unknown change-to-test mappings and zero selected tests must fail closed.
- A non-blocking test must not be presented as gating confidence.
- New behavior and bug fixes should add or update the cheapest representative
  test layer, plus deeper integration coverage when unit coverage is insufficient.

## Future skill inputs and output

The skill should not infer all coverage by grepping prose. It should combine:

1. policy from `TESTING.md`;
2. changed paths and CMake/topology dependencies;
3. the consumer graph/test policies plus a machine-readable alias/cadence/
   enforcement registry;
4. current CI matrix and workflow enforcement;
5. component-specific testing-strategy documents where present.

For a PR or feature area it should report:

- affected artifacts/components and supported surface;
- existing direct and indirect tests that should run;
- whether the PR adds/updates representative tests;
- platform, cadence, selection, blocking, and zero-test gaps;
- the closest existing project pattern to follow;
- whether a new testing pattern is truly needed;
- explicit limitations suitable for a follow-up issue.

With the two small policy sections above, RFC0013's graph foundation, and
machine-readable coverage/enforcement metadata, the current document is a good
foundation for this skill. Without the final mapping, the skill can still
provide a heuristic review, but it will reproduce the same name and scheduling
ambiguity found in this audit.

# Alternatives considered for coverage metadata

## Continue inferring coverage from the graph, topology, and Python dictionaries

This avoids a new file and benefits from the committed consumer graph, but still
preserves multiple identifier spaces and makes cadence, blocking status,
aliases, and intentional exemptions difficult to express. It is not recommended
as the complete long-term agent/audit interface.

## Add all metadata to BUILD_TOPOLOGY.toml

This keeps artifact support and test coverage together and makes platform
comparisons natural. It may overload a build-topology file with workflow policy,
especially for tests spanning multiple artifacts.

## Extend test_policies.toml or add a separate TEST_TOPOLOGY.toml

This gives selection aliases, test jobs, tiers, cadence, and enforcement a clear
schema while referencing artifacts from `BUILD_TOPOLOGY.toml` and graph keys
from `therock_consumer_graph.json`. Extending `test_policies.toml` reduces file
count but mixes graph-walk policy with coverage inventory; a separate file keeps
those concerns distinct but adds another registry. Either can work if CI
validates referential integrity end to end.

The key architectural requirement is not the filename. It is one validated
source of truth instead of three loosely coupled name lists.

# Verification performed

- Enumerated first-party `therock_cmake_subproject_declare()` calls outside
  `third-party/`.
- Compared those declarations and `BUILD_TOPOLOGY.toml` artifacts with the
  component matrix in `fetch_test_configurations.py`.
- Inspected CMake build-test and structural-test registrations.
- Compared rocm-libraries and rocm-systems external repository configuration
  names against consumer-graph selections and component-matrix keys.
- Inspected Linux and Windows artifact workflows for blocking status and CTest
  execution.
- Inspected sanity, extended functional/benchmark, RDC, emulation, OpenCL, and
  representative component test code.
- Ran `build_tools/github_actions/tests/fetch_test_configurations_test.py`: 28
  tests passed. The existing tests validate matrix mechanics but do not validate
  end-to-end external-path/graph/policy/matrix consistency.
- Ran `test_tools/tests/determine_rocm_test_dependencies_test.py`: 49 tests
  passed. These cover graph walks and policy mechanics, including tests that
  explicitly capture the unresolved identifier-space skew.
