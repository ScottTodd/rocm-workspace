# `TESTING.md` documentation task state dump

Date: 2026-08-10  
TheRock branch: `users/scotttodd/testingmd`  
TheRock commit reviewed: `cd8139386` (`Add TESTING.md to TheRock`)  
Primary document: `D:/projects/TheRock/TESTING.md`  
Companion audit: [`testing_audits-2026-08-10.md`](./testing_audits-2026-08-10.md)

This is a durable handoff for the conversation that produced the first version
of `TESTING.md`. It records the intent behind the document, ideas intentionally
deferred from the initial pull request, present-day gaps identified while
comparing the policy to the repository, and likely follow-up work. It is not
intended to be published as-is.

## Short version

The current `TESTING.md` has the right basic structure for the initial pull
request and should not need a major rewrite before landing. It explains why
testing matters to TheRock, describes how changes to major TheRock feature
areas are validated, and introduces how ROCm subprojects are built and tested
through TheRock.

The next documentation work should make coverage easier to reason about, not
just add more prose. In particular, it should distinguish:

- a test being defined from it actually being selected, scheduled, blocking,
  and monitored;
- unit versus integration scope from local versus CI execution;
- representative presubmit coverage from broader postsubmit, nightly,
  on-demand, and downstream coverage;
- component-local confidence from confidence in the assembled ROCm product;
- test failures from build, runner, service, or orchestration failures.

The largest strategic gaps are performance regression testing, binary/package
size protection, explicit component coverage contracts, test-selection
correctness, runner and test-suite health management, documentation/example
validation, and a complete downstream-framework feedback loop.

## Purpose and intended audience of `TESTING.md`

The page is a project-wide testing overview, not a comprehensive command
reference and not an operations runbook. It should help contributors and
maintainers answer three questions:

1. Why does TheRock need layered automated testing?
2. How is code in each major TheRock feature area structured and validated?
3. How are ROCm subprojects integrated, selected, built, tested, packaged, and
   carried from a source change into a release?

The intended outcome is a project structure in which following existing
conventions naturally leads to reasonable coverage. The document should not
place excessive personal responsibility on authors or reviewers. Contributors
still need to reason carefully when adding new functionality, platforms, or
support surfaces that fall outside existing coverage, but good testing should
usually be the path of least resistance.

The introduction establishes the main motivation:

- TheRock underpins the CMake builds and CI build/test workflows used for ROCm
  Core contributions.
- TheRock and rockrel underpin nightly and stable releases.
- ROCm should be ready to release continuously, rather than becoming stable
  only after a separate manual QA phase.
- ROCm Core contains 40+ subprojects, supports 25+ GPU targets and multiple
  operating systems and package formats, and is consumed by frameworks such as
  PyTorch and JAX.
- The full cross-product cannot run on every change. Coverage must expand by
  frequency and cost: fast representative presubmit checks, broader scheduled
  and nightly testing, and opt-in paths for scarce hardware or unusual
  configurations.
- Important tests should be accessible during development. Local execution is
  usually the fastest feedback path; CI adds consistent environments,
  cross-component validation, and representative project-wide checks.
- ROCm Core is released as one product, so it should be assembled and tested as
  one as often as practical even when individual subprojects also have their
  own focused CI.

## Established writing and policy positions

These preferences emerged repeatedly during drafting and should be preserved
in future edits.

### Testing is broader than regression detection

Avoid framing testing only as finding bugs. Tests should demonstrate that the
software behaves as intended. Depending on the area, that includes:

- producing correct results;
- building successfully in supported configurations;
- installing and importing successfully through supported package formats;
- working through the same public APIs and instructions users follow;
- meeting numerical-accuracy, runtime-performance, binary-size, and build-time
  expectations;
- composing correctly with other ROCm components and downstream frameworks.

Package installation and consumer smoke tests provide affirmative evidence
that a release works for users; they are not merely regression tests.

### Test scope and execution location are separate axes

Do not imply that unit tests are local while integration tests belong to CI.
Both unit and integration tests should be runnable during development where
practical, and both may also run in CI. The high-level document does not need a
textbook definition of unit and integration tests. It needs to explain that
there are multiple layers with different costs and frequencies, and that those
layers remain accessible to contributors.

Similarly, do not present CI as a replacement for local development. Local
testing is usually faster; CI checks work in consistent environments and finds
unintended effects outside the contributor's immediate area. The tone should
remain welcoming to contributors whose local setups or hardware access are
limited.

### Favor technical structure over individual heroics

The project should make good testing easy by convention:

- static checks belong in pre-commit when they are repository-wide formatting
  or mechanically enforceable style rules;
- deterministic policy and transformation logic belongs in scripts that can be
  unit tested on CPU machines;
- GitHub Actions workflows should be thin orchestration layers over scripts
  that can also run locally;
- installed-component and package tests should use standard entry points;
- CI selection metadata should connect source projects to their expected
  validation automatically;
- unusual support surfaces should have documented, opt-in testing paths.

Contributors must reason more explicitly when a change creates a new feature,
configuration, backend, package type, or hardware requirement outside those
patterns.

### Defense in depth is expected

No single layer is enough for central infrastructure or GPU software. A typical
feature may need a combination of:

1. formatting and static checks;
2. CPU-only unit tests for deterministic logic;
3. integration tests around filesystem, subprocess, packaging, or API
   boundaries;
4. representative CI builds and real-hardware tests;
5. broader scheduled, nightly, and on-demand configurations;
6. post-release/downstream validation where behavior cannot be exercised before
   merge.

The GitHub Actions section is a particularly clear example: `actionlint`
catches YAML and expression problems, custom unit tests catch repository policy
and interface problems that `actionlint` cannot see, dev/manual workflow runs
exercise GitHub's orchestration semantics, and nightly monitoring covers
post-merge paths that cannot be fully reproduced in a pull request.

### Scannability matters

The current feature-area sections use H4 headings for:

- Scope
- Design for testing
- Validation methods
- Limitations and known gaps

Retain that visible structure even though H4 headings are somewhat verbose.
Each H3 feature area is longer than one screen, and the headings make it clear
what is being designed for testing when scanning the rendered page. Horizontal
rules and GitHub tip/warning/important callouts are also intentional ways to
break up long walls of text.

Specific examples should be sprinkled throughout the document. Avoid turning a
single component such as hipBLASLt into the canonical example for an entire
section.

## Current document structure and assessment

The current page contains:

- an introduction explaining why testing matters and how coverage scales;
- `Testing changes to TheRock`;
  - test categories;
  - CMake and super-project build logic;
  - GitHub Actions workflows;
  - Python scripts and tools;
  - packaging;
- `Testing changes to ROCm subprojects with TheRock`;
  - building subprojects through TheRock;
  - testing subprojects through TheRock;
  - build tests and the installed-component test runner.

That is enough structure and substantive content for an initial review. The
feature-area template is useful both for the current document and as an example
for subprojects writing their own testing-strategy pages.

The initial document is strongest when it stays an overview and links to
specialized references such as the Python style guide, GitHub Actions debugging
guide, packaging documentation, and test filtering guide. Detailed commands,
component-by-component inventories, operational response procedures, and
dashboard definitions can live in linked documents or generated reports.

Two small conceptual additions would make later audits and automation easier:

1. A coverage model distinguishing whether a test is defined, locally
   runnable, discoverable/selectable by CI, scheduled at an intentional
   cadence, blocking, and monitored for health.
2. A standard coverage contract/template for every shipped component or
   artifact.

These do not have to block the initial PR. They are good first follow-ups.

## Ideas intentionally deferred from the initial document

### More helpful diagrams

Several diagrams were considered, but text was prioritized first so the
visuals would explain stable concepts rather than decorate an unfinished
outline.

#### Coverage expansion by cadence

A compact diagram should show coverage expanding through something like:

`presubmit -> postsubmit -> nightly -> downstream/continuous observation`

The intended meaning is:

- presubmit runs fast, high-signal suites and configurations with enough runner
  capacity for every change;
- postsubmit can spend more time and detect interactions after changes are
  combined;
- nightly runs longer suites and uses scarce or specialized hardware;
- downstream testing exercises framework and application behavior against
  published packages and reports the result back.

This is not a strict sequence in which developers only use early stages. Longer
or hardware-specific configurations should remain available on demand during
development.

Earlier Mermaid attempts became noisy because too much prose was placed inside
nodes and the horizontal direction was obscured by whitespace. A future diagram
should use short labels, keep explanatory text in the surrounding prose, and
probably use a sequence diagram, a compact table, or a custom static image
rather than a dense Mermaid flowchart.

#### Change validation flow

Another useful visual would show the normal progression for a change:

`local script/unit/integration tests -> pull-request or workflow_dispatch run ->
post-merge/nightly observation -> downstream feedback`

The flow needs branches:

- some changes receive automatic pull-request workflow runs;
- some workflows require manual `workflow_dispatch` testing;
- release changes should use dev release jobs that exercise nearly the same
  path as nightly jobs while using dev versions and dev buckets;
- some schedule, secret, promotion, and downstream behaviors cannot be proven
  until after merge and therefore require monitored rollout.

#### Cross-repository source-to-release lifecycle

A diagram is needed for how source code in `rocm-libraries` and `rocm-systems`
reaches TheRock and then a release:

1. component commits land in the source monorepository;
2. that repository's own CI and "TheRock CI" build/test a selected set of
   projects;
3. TheRock updates its pinned submodule reference, typically through automated
   daily bumps;
4. TheRock CI builds and tests the assembled product;
5. rockrel invokes TheRock release workflows to publish dev, nightly, and stable
   channels;
6. framework/downstream validation consumes the published packages;
7. Quartz records status and can notify downstream subscribers.

A GitGraph experiment did not express repository ownership, submodule pins,
testing, and release inclusion clearly enough. Git commits do not literally
merge between these repositories in the way GitGraph suggests. A sequence
diagram or a two-lane timeline is more accurate. A second, more detailed visual
may separately show the reverse "TheRock commit ref" synchronization used so
`rocm-libraries` and `rocm-systems` can run TheRock CI against a pinned TheRock
revision.

#### Workflow validation layers

A compact layered visual could show:

- `actionlint` and pre-commit;
- unit/contract tests for workflow inputs and supporting scripts;
- local execution of those scripts;
- manual or automatic workflow runs in CI/dev environments;
- post-merge observation of schedules, releases, and downstream consumers.

This is a good candidate for a small table rather than a diagram because the
important comparison axes are purpose, environment, cost, and limitations.

### Framework and downstream test coverage

PyTorch, JAX, vLLM, and other frameworks are part of the support surface but are
not yet explained in a dedicated section. Follow-up documentation should
answer:

- Which framework wheels or source revisions are built against TheRock/ROCm
  packages?
- Which tests run in pull requests, nightly releases, or separate downstream
  repositories?
- Which operating systems, Python versions, GPU families, single/multi-GPU
  arrangements, and package channels are covered?
- Are failures blocking release publication/promotion, informational, or owned
  by the downstream project?
- How can a developer reproduce a framework test using a CI or nightly package
  index without rebuilding all of ROCm?
- How are failures attributed to ROCm packages, framework changes, runner
  health, or external dependencies?
- How are compatibility windows handled when ROCm and framework main branches
  change independently?

The desired end-to-end story is not only "ROCm's own tests passed." A nightly
release should be published to an appropriate staging/nightly channel, tested
as a user would install it, exercised by important downstream frameworks, and
have those results visible to the release and component teams.

### Quartz and the post-publication feedback loop

TheRock now contains concrete Quartz integration work:

- `docs/rfcs/RFC0011-Quartz-CICD-Datahub.md` describes central ingestion,
  dashboards, downstream notification, and results reported back by downstream
  projects;
- `.github/workflows/notify_quartz.yml` and
  `build_tools/github_actions/notify_quartz.py` provide TheRock-side reporting;
- `build_tools/github_actions/tests/notify_quartz_test.py` tests some reporting
  behavior.

Do not infer from those files that the complete desired operational loop is
already deployed. The testing documentation should eventually describe the
contract at a policy level:

1. nightly ROCm artifacts/packages are initially published;
2. TheRock's package and hardware tests establish a release status;
3. Quartz stores the component/job results and publishes a stable status model;
4. once the relevant ROCm checks have completed, subscribed downstream projects
   are notified or poll status data;
5. downstream projects test the release and report results back;
6. dashboards and alerts expose failures, missing reports, and duration/pass
   trends.

Open questions include:

- What is the exact threshold for a "good" nightly: all jobs, a required subset,
  or product/platform-specific definitions?
- Is downstream validation part of release promotion, or post-publication
  observation only?
- What happens when ROCm passes but a framework fails, or when a downstream
  project never reports?
- Which results must be public and accessible to all contributors?
- How are retries, late/out-of-order reports, and stale nightlies represented?
- Which project owns triage when a downstream failure crosses repository
  boundaries?

RFC0011 already covers many implementation details. `TESTING.md` should state
the testing principle and link to Quartz documentation instead of duplicating
the protocol.

### More detailed subproject testing policies

The current page introduces subproject builds, installed test artifacts, test
runners, and filter levels. Follow-up work should explain the full integration
contract:

1. add the source code to `rocm-libraries`, `rocm-systems`, or another pinned
   source location;
2. declare the subproject and its build dependencies in TheRock;
3. identify build outputs and package composition;
4. add the tests TheRock should run, using standard installed-test entry points;
5. map changed source paths to the build and test configurations that should be
   selected in the external repository's TheRock CI;
6. test the submodule bump and the assembled TheRock product;
7. include the component in release packages and downstream/product tests.

In particular, document the projects/configurations built and tested when
"TheRock CI" runs in `rocm-libraries` and `rocm-systems`. Current source for
that behavior includes:

- `rocm-libraries/.github/scripts/therock_matrix.py`;
- `rocm-systems/.github/scripts/therock_matrix.py`;
- the associated `therock_configure_ci.py` scripts and workflows;
- TheRock's `build_tools/github_actions/fetch_test_configurations.py`;
- `test_tools/therock_consumer_graph.json` and `test_tools/test_policies.toml`.

This is not merely a reference-table problem. These locations use multiple
identifier spaces, and the audit found cases where a changed-project name can
select no matching component test even though a related test exists under a
different name. The documentation should explain the lifecycle after the
mapping is made authoritative; it should not normalize current accidental
complexity as the desired design.

### Infrastructure changes and operational testing

A top-level section tentatively called `Monitoring the health of the testing
system` was considered. This is appropriate because TheRock is an integration
point for builds, tests, packaging, and releases, and therefore needs high
availability, reliability, and observability. The scope needs to stay at the
testing-policy level rather than becoming a complete SRE manual.

Infrastructure in scope includes:

- self-hosted CPU build runners;
- self-hosted GPU test runners, including single- and multi-GPU systems;
- Windows, Linux, and WSL runner images and host configuration;
- manylinux/build containers;
- ccache and other cache services;
- dependency mirrors;
- S3/cloud buckets, package indices, and artifact publishing services;
- credentials, GitHub Apps, and cross-repository workflow integrations;
- Quartz and dashboards/notification services.

The policy-level recommendations are:

- Put decision-making and orchestration logic in versioned, unit-testable
  scripts.
- Validate changes in dev/test environments that cannot affect nightly or
  stable release channels.
- Use progressive rollout: a test instance or canary runner, a small fraction of
  the pool, then the full fleet.
- Pin images and external automation by immutable revision where practical, and
  roll the pin forward deliberately.
- Preserve detailed logs and make them accessible to contributors.
- Run independent health checks so infrastructure failures can be distinguished
  from code failures.
- Automatically stop scheduling work on an unhealthy runner, or quarantine it
  quickly through an external controller, and require a positive health check
  before rejoining the pool.
- Monitor capacity and service quality, not just pass/fail: queue time, runner
  availability, disk pressure, network/object-store errors, cache hit rate,
  build/test duration, and retry rate.
- Define rollback and recovery before a fleet-wide or production-channel
  change.

#### Current runner-health behavior versus the goal

The repository currently runs `build_tools/health_status.py` in several build
and test workflows and `build_tools/print_driver_gpu_info.py` before component
tests. Those scripts provide useful diagnostics in job logs.

They should not yet be described as a complete runner admission or quarantine
system:

- `health_status.py` explicitly says it does not raise/return warnings or
  errors;
- at commit `cd8139386`, `print_driver_gpu_info.py` invokes commands with
  `check=False`, prints their output, and returns success even when the GPU
  command fails;
- ROCm/TheRock PR 6604 proposes checking the GPU sanity-command return value so
  a runner with a broken GPU state fails before producing misleading component
  failures. It was still open when this handoff was written;
- a failed workflow step alone does not remove the machine from the shared
  runner pool. Pool quarantine/repair needs runner-manager or infrastructure
  integration outside the individual test job.

Useful health checks for a GPU runner may include device enumeration, expected
architecture and device count, driver/runtime compatibility, a minimal HIP
allocation/kernel/synchronization path, required multi-GPU topology, disk
space, network/object-store access, and container/runtime state. The final
policy does not need to prescribe one universal script, but it should require
that checks fail clearly and act on scheduling state rather than only printing
diagnostics.

#### Infrastructure test examples to develop later

Build-container changes:

- build and publish a canary image by immutable digest;
- run representative configure/build/unit/package tasks against it;
- compare toolchain versions and dependency manifests;
- move a small runner/workflow cohort to the digest before fleet-wide rollout;
- retain the prior digest for rollback.

Runner-image or host changes:

- validate a newly provisioned runner outside the main pool;
- check host tools, driver and GPU state, filesystem permissions, long-path or
  symlink behavior, network access, and artifact upload/download;
- run a small build and installed GPU smoke test;
- canary on low-risk or dev workflows before nightly/stable workloads.

Bucket, package-index, or cache changes:

- use dev namespaces/buckets and synthetic payloads;
- validate read, write, list/index generation, checksum, retention, and access
  controls;
- test interrupted/retried uploads for idempotence;
- prove dev/nightly/stable channels cannot be crossed accidentally;
- monitor latency, error rate, missing objects, and stale indices after rollout.

### Testing-system observability

Observability applies to both infrastructure health and the tests themselves.
The future section should mention:

- follow consistent logging practices in build and CI/CD code;
- preserve build/test logs and artifact manifests for later diagnosis;
- expose logs to all contributors where credentials and licensing permit;
- distinguish setup/runner/service failures from component failures in job
  summaries and dashboards;
- track pass rate, flake/retry rate, skip/xfail counts, zero-test collection,
  duration, and test-count changes;
- track runner availability, utilization, queue time, and failure clustering by
  machine/image/driver;
- track build duration, test duration, artifact/package size, and release
  completion time;
- alert when a scheduled workflow stops running or results stop reaching the
  reporting system;
- assign ownership and a deadline when tests are quarantined or made
  non-blocking.

Quartz can provide part of the cross-workflow data plane, but a system cannot
self-observe all failure modes. For example, a disabled GitHub workflow or a
broken notification credential may require an external watchdog.

## Other areas that could be documented

### Documentation and user-facing examples

The current policy does not yet treat documentation and examples as test
inputs. This is a meaningful omission because README commands, package-install
instructions, sample CMake consumers, and API examples often provide the
closest approximation of a user's first experience with a release.

Current repository checks include:

- `mdformat` via `.pre-commit-config.yaml`, with GFM, Black, and frontmatter
  plugins;
- trailing-whitespace and end-of-file normalization;
- checks for YAML/JSON syntax, merge markers, large files, line endings, and
  tabs where applicable.

Those checks establish consistent structure but do not prove that prose is
accurate, links resolve, documentation renders, or commands/examples work. No
dedicated TheRock documentation build, link checker, or executable-snippet
workflow was identified during this audit; verify that conclusion again before
turning it into a normative claim because the repository changes rapidly.

A future documentation-testing subsection could distinguish:

| Layer | Examples | Confidence provided |
| --- | --- | --- |
| Formatting and structure | `mdformat`, whitespace, YAML/frontmatter parsing | Files are mechanically well formed and consistently formatted. |
| Render/build validation | docs-site build or preview | Markup, directives, anchors, and generated navigation render successfully. |
| Link/reference validation | internal anchors, local paths, selected external links | Readers can reach referenced files and pages. |
| Executable examples | README commands, sample CMake projects, code snippets | Instructions still work against current build outputs/packages. |
| Product integration | install packages and follow the public quick-start path | Documentation matches what a user can do with a released product. |

Not every prose-only edit needs GPU CI. The relevant distinction is whether the
change only affects wording/format or changes a command, API example, package
name, build option, supported configuration, or expected behavior. Expensive
tests should be selected by the behavior being documented, not simply by the
`.md` extension.

Possible follow-ups:

- add link and internal-anchor validation;
- build documentation or previews for pull requests;
- turn important snippets into source files that are compiled/run and included
  into docs rather than copied manually;
- add installed SDK sample projects that follow documented CMake/package usage;
- validate generated tables and command output for drift;
- define how docs-only changes interact with CI path filtering without allowing
  behavior-changing documentation updates to bypass relevant checks.

### What should and should not be mocked in Python tests

This topic should mostly stay in
`docs/development/style_guides/python_style_guide.md`, but `TESTING.md` may link
to it and summarize the architectural principle.

Good candidates for direct unit tests are deterministic selection,
transformation, validation, naming, and policy logic. Separate those functions
from GitHub, S3, subprocess, clock, environment, and filesystem boundaries.

Mock the expensive or nondeterministic boundary when necessary, not the logic
whose outcome the test is meant to prove. Prefer real temporary files and
directories over mocking every filesystem call. Prefer a real subprocess when
it is small, portable, and deterministic. For GitHub/S3 integrations, a unit
test can fake the HTTP/client seam while contract tests validate payloads and a
dev-environment integration run validates authentication, permissions, and
service semantics. Avoid tests that only assert that one mocked internal helper
called another mocked internal helper.

The important limitation is that unit tests cannot prove GitHub event
semantics, secret/environment protections, runner labels, cloud permissions,
package installation on a clean machine, or GPU behavior. Those boundaries need
representative integration tests.

### Release and packaging lifecycle failures

The current packaging section covers construction, installation, and basic use,
but future policy should cover failure/recovery behavior:

- interrupted and retried uploads;
- idempotent reruns;
- dev/nightly/stable channel isolation;
- partial releases and atomic promotion;
- upgrade, uninstall, reinstall, and co-installation behavior;
- provenance, signing, checksum, and manifest verification;
- rollback or safe recovery after a bad promotion;
- retention and garbage collection without breaking published indices.

These tests are expensive and may run in dev environments or on a schedule, but
the release system is central enough that success-path-only testing is
insufficient.

### API/ABI, numerical quality, and security properties

Possible future specialist sections or linked policies include:

- ABI/API compatibility across ROCm components and releases;
- numerical tolerances and accuracy modes for math libraries;
- sanitizer/debug configurations;
- supply-chain and provenance checks;
- secrets and least-privilege validation for workflows;
- vulnerability scanning for containers and published packages.

These should be acknowledged as testable product properties even if their
detailed policies live elsewhere.

## Major gaps in the current testing strategy

This section records strategic gaps, not just omissions from the prose. The
companion audit contains the implementation evidence and should be consulted
before opening specific issues.

### Performance and benchmark coverage

Runtime performance is a first-class part of "works as expected," especially
for GPU libraries, but it is not currently protected by a consistent public,
automated, blocking path in TheRock.

There is benchmark plumbing:

- `tests/extended_tests/` defines functional and benchmark matrices;
- `fetch_test_configurations.py` can merge benchmark jobs when
  `RUN_EXTENDED_TESTS` is enabled;
- GPU-family metadata can specify dedicated benchmark runners;
- `test_component.yml` exposes benchmark database credentials for nightly
  result submission;
- some component runners invoke performance-oriented suites.

However, the audit found no checked-in workflow caller enabling
`run_extended_tests`, and extended benchmark entries are treated as opt-in and
expected-failure. Some internal CI systems collect performance data, but that
coverage is not a transparent, consistently enforced part of TheRock's public
release confidence model.

A performance-testing sprint needs to address more than "run benchmarks":

- stable and characterized hardware;
- warmup, repetition, noise estimation, and outlier policy;
- comparable software/driver/compiler baselines;
- thresholds that distinguish real regressions from variance;
- per-architecture and per-workload ownership;
- storage and visualization of trends;
- a policy for blocking versus alerting;
- local/on-demand reproduction using the same benchmark definitions;
- handling intentional tradeoffs and updating baselines through review.

Presubmit gating may initially cover a small, stable set of high-signal
benchmarks while nightly runs broaden the surface. Internal results can be
useful, but failures and baselines that protect the open-source product should
be visible enough for open-source contributors to diagnose them.

### Binary, package, and artifact size

Binary/artifact growth is currently best-effort monitoring after merge. The
document acknowledges that build artifacts should not grow unexpectedly, but
there is no discovered automated budget or pull-request comparison that fails
or clearly annotates regressions. Meaningful regressions have occurred.

A size sprint could add:

- per-artifact and per-package size manifests;
- normalized comparisons against the target branch or prior nightly;
- attribution by file/component/GPU target where possible;
- warning and blocking thresholds with an intentional override path;
- trend dashboards and alerts;
- special handling for multi-architecture kernel packages, debug symbols,
  compression, and file deduplication so comparisons remain meaningful.

The goal is not a universal hard cap. It is to make unexpected growth visible
before merge and force intentional growth to be reviewed with evidence.

### Component coverage contracts are implicit

Some shipped components have only build or structural confidence; others have
deep installed correctness suites. The absence of a standard declaration makes
it hard to know whether that difference is intentional.

Every shipped artifact/component should eventually declare, or explicitly mark
as not applicable:

- artifact/package structure validation;
- installed consumer or behavioral smoke test;
- deeper correctness tests and their cadence;
- supported operating systems/backends/hardware slices;
- local entry point;
- CI selection key;
- blocking versus informational status;
- known exclusions or expected failures.

### Test definition, selection, enforcement, and health are conflated

A test file existing does not mean it protects the release. The current policy
needs vocabulary for these separate states:

1. defined;
2. packaged/runnable locally;
3. discoverable by CI;
4. selected for the relevant source change;
5. scheduled at an intentional cadence;
6. fails closed if no tests are collected;
7. blocking before the relevant release/promotion;
8. monitored for flakes, skips, duration, and test-count drift.

This distinction explains several current gaps:

- Mirage and rocJitsu build tests run with `continue-on-error` on Linux, so a
  failure is visible but does not protect the workflow result;
- the extended benchmark matrix exists but is not normally scheduled;
- Windows sanity can collect only skipped tests and still report success;
- source/test names can fail to map, producing no targeted component job;
- a diagnostic runner-health command can print a GPU failure and still return
  success.

### Change-to-test selection is incomplete

TheRock has a strong foundation in the generated consumer graph,
`test_policies.toml`, dependency-based selection, a drift check, and explanation
tools. The unresolved boundary is the authoritative mapping among:

- source paths and project groups in `rocm-libraries`/`rocm-systems`;
- keys in the generated consumer graph and test policies;
- keys in `fetch_test_configurations.py` and installed test runners.

Nightly run-all jobs can hide presubmit selection holes. Unknown or unmapped
projects should fail closed or deliberately expand to a safe broader suite.
Consistency tests should prove that every included source project and every
declared test key has an intended mapping.

### Platform and hardware holes

The support matrix is intentionally sampled, but some holes are accidental or
not clearly declared. Confirmed examples from the audit include:

- rocFFT correctness tests selected only on Linux despite a Windows build and a
  TODO for Windows testing;
- a similar Windows coverage issue for rocSOLVER;
- Windows sanity tests that can all be skipped;
- WSL build/upload coverage without a corresponding runtime validation path;
- OpenCL structural validation without a direct installed compile/run smoke
  test;
- scarce older GPU families receiving nightly/on-demand rather than presubmit
  coverage.

Hardware availability must influence cadence without silently redefining the
supported surface. The practical context discussed during drafting was that
gfx942 has 50+ runners while older Radeon/Instinct families may have only 0-5,
and some component suites take more than two hours while current CI budgets may
allow roughly 30 minutes. The policy should make the resulting sampling and
opt-in routes visible.

### Direct behavioral component gaps

The implementation audit found the largest direct gaps around base/compiler
utilities, OpenCL and some core tools, composable-kernel/support libraries, RDC,
and emulation tools. These are not all equally untested: some have structural or
indirect coverage.

Concrete examples to retain for follow-up audits:

- `dctools/CMakeLists.txt` includes RDC and performs structural checks; upstream
  RDC sources include tests, but there is no direct `test_rdc.py` matrix entry
  in `build_tools/github_actions/test_executable_scripts`;
- OpenCL has structural checks but lacks an installed compile/run consumer
  smoke test in the identified TheRock path;
- WSL artifacts are built/uploaded without a direct runtime test;
- hipify, composable kernel, and some support tools lack direct TheRock
  behavioral runners;
- Mirage and rocJitsu have non-blocking Linux build tests.

Use the dated audit for the complete inventory. Re-run it before filing issues
because these areas are actively changing.

### Test-suite health and quarantine

The project does not yet have a clearly documented policy for:

- detecting and measuring flakes;
- deciding when retries are appropriate;
- marking expected failures or using `continue-on-error`;
- preventing a quarantined test from disappearing indefinitely;
- identifying owners and deadlines for re-enablement;
- detecting unexpected skip growth or zero-test collection;
- monitoring whether quick/standard/comprehensive filters erode over time.

Without this, a nominally present suite can gradually stop providing
confidence.

### Downstream and release-product validation

Framework testing exists in several workflows, but the policy and feedback loop
are not yet described end to end. Missing clarity includes what runs before
publication, what runs after publication, which failures block promotion, and
how results from PyTorch/JAX/vLLM or other consumers feed back into ROCm release
health.

Quartz is the intended mechanism for centralized status, notification, and
reported downstream results. The exact release-quality contract still needs to
be written.

### Documentation and examples

Formatting is automated, but documentation correctness and executable examples
are not systematically protected. A stale installation command or sample may
be one of the first user-visible release failures even when component tests
pass.

### Release failure paths and infrastructure reliability

The successful path is better exercised than partial failure, retry,
idempotency, channel isolation, rollback, and infrastructure degradation.
Runner diagnostics exist, but automatic runner quarantine and fleet-level
health policy are incomplete.

## Proposed standard testing-strategy template

The hipDNN testing-strategy page in `rocm-libraries` was discussed as a useful
inspiration because it describes environments, locations, purposes, and test
speed in a table. A project-wide template should remain flexible enough for
components with different needs.

Suggested structure:

### Scope and supported surface

- source directory/repository;
- artifacts and packages shipped;
- public entry points or consumer scenarios;
- supported operating systems, backends, GPU families/topologies, and package
  formats that materially affect testing.

### Design for testing

- how deterministic logic is isolated;
- installed-test layout and environment assumptions;
- standard local entry points;
- how user-facing samples or package consumers are exercised;
- how expensive/specialized tests are filtered without creating a different
  local and CI implementation.

### Validation inventory

| Environment or layer | Location/entry point | Purpose | Expected speed | Cadence | Blocking? |
| --- | --- | --- | --- | --- | --- |
| Static/unit | Path or command | Policy and deterministic behavior | Seconds/minutes | Local + every PR | Yes |
| Build | TheRock subproject/target | Integration into selected build configurations | Minutes/hours | PR/nightly | Usually |
| Installed smoke | Test runner key | Public API/package usability | Minutes | PR/nightly | Yes |
| Correctness | Test runner and filter | Component behavior | Minutes/hours | PR/nightly/on demand | State explicitly |
| Specialized | Multi-GPU/performance/sanitizer/etc. | Expensive support surface | Hours | Nightly/on demand | State explicitly |
| Downstream | Framework/application workflow | Product-level compatibility | Hours | Nightly/release | State explicitly |

### Selection and coverage

- canonical CI test key;
- source paths that select it;
- direct and transitive consumers that should also be tested;
- test filter levels and their target runtimes;
- platform/hardware sampling by presubmit, postsubmit, nightly, and on demand;
- fail-closed behavior when no tests are selected or collected.

### Limitations and known gaps

- unsupported or untested surfaces;
- non-blocking/expected-failure tests;
- scarce-runner constraints;
- manual/internal coverage not visible in TheRock;
- linked issues and intended remediation.

The template should be a contract and a discoverability aid, not a demand that
all components run an identical suite or duplicate implementation details from
their own repositories.

## Future coding-agent skill

The planned skill would evaluate a change or feature area against `TESTING.md`
and answer:

- Which feature areas, subprojects, artifacts, packages, platforms, and
  downstream consumers are affected?
- Which existing tests provide direct, indirect, structural, build-only, or
  downstream confidence?
- Are those tests locally runnable, selected for this change, scheduled at the
  right cadence, blocking, and healthy?
- Does the change follow an existing test pattern that should be reused?
- Are new tests needed, or is a new testing pattern/support surface being
  introduced?
- What can be run locally, what CI should run automatically, and what should be
  triggered on demand or monitored after merge?
- What limitations remain and should they be documented in the PR or project
  policy?

`TESTING.md` is a good policy foundation for that skill, but prose alone is not
enough for reliable answers. The skill will need machine-readable or at least
canonical inputs:

- `BUILD_TOPOLOGY.toml` and generated consumer graph;
- `test_policies.toml` or a future test-topology registry;
- external repository project groups and changed-path mappings;
- `fetch_test_configurations.py` test keys;
- workflow trigger/cadence and blocking metadata;
- supported platform/hardware/package declarations;
- component testing-strategy pages and explicit limitations.

Recommended skill output format:

1. affected surface;
2. existing coverage by layer;
3. expected automatic CI selection;
4. suggested local/on-demand commands;
5. gaps or non-blocking coverage;
6. existing pattern to follow, or justification for a new pattern;
7. confidence assessment with evidence and file references.

The skill should not infer confidence merely because a test file exists. It
should distinguish definition, selection, cadence, enforcement, and health. It
should also avoid insisting that every PR paste routine formatter output into
its description. Exceptional evidence—such as a reproduced bug and verified
fix, reliance on CI because hardware is unavailable, or a dev release workflow
run—is useful when it changes the reviewer's understanding.

## Candidate documentation architecture after the initial PR

One possible evolution is:

1. Keep the existing introduction and feature-area sections in `TESTING.md`.
2. Add a concise `General principles` section only if the ideas cannot be
   integrated cleanly into the introduction/feature sections. Candidate topics:
   coverage dimensions, cadence, blocking status, local accessibility, static
   analysis, scarce hardware, and fail-closed selection.
3. Add documentation/example testing and CI infrastructure as additional
   TheRock feature areas, or link focused pages if they become too operational.
4. Expand `Testing changes to ROCm subprojects with TheRock` with the inclusion
   lifecycle, cross-repository TheRock CI selection, and a standard component
   coverage template.
5. Add a short top-level `Monitoring the health of the testing system` section
   covering test health, runner/service health, logging, retention,
   observability, progressive rollout, and rollback.
6. Add or link a downstream/framework validation page explaining published
   package consumption and Quartz feedback.
7. Generate detailed coverage inventories from metadata instead of maintaining
   large hand-written tables in `TESTING.md`.

The initial document should not attempt to become all of those pages at once.

## Suggested follow-up audits and feature sprints

The companion audit recommends these implementation-oriented sprints:

1. **Make test selection fail closed.** Normalize project/test identifiers and
   prevent targeted changes from silently selecting no relevant test.
2. **Generate a component coverage inventory.** Show direct/indirect/structural
   tests, platforms, cadence, and blocking status from authoritative metadata.
3. **Wire existing but unused tests.** Prioritize components that already have
   test code but no TheRock matrix entry, and make accidental non-blocking jobs
   visible.
4. **Close supported-platform holes.** Start with Windows tests for projects
   that build on Windows and ensure sanity suites cannot succeed with zero
   executed tests.
5. **Establish product-quality and test-health signals.** Performance, size,
   build/test duration, flake/skip/test-count monitoring, and quarantine policy.

Additional sprints from this handoff:

6. **Documentation and executable examples.** Add render/link/example checks and
   an installed SDK sample path.
7. **Runner health and quarantine.** Turn diagnostics into failing admission
   checks, integrate with pool management, and add health dashboards.
8. **Release failure/recovery testing.** Exercise retries, partial publication,
   channel isolation, promotion, and rollback in dev environments.
9. **Framework/Quartz feedback loop.** Define release status, notify downstream
   projects after initial nightly validation, receive results, and expose
   ownership/alerts.
10. **Cross-repository TheRock CI documentation.** Document and then simplify
    the project/build/test mappings used by `rocm-libraries` and `rocm-systems`.

## Approaches considered and not selected yet

### A large hand-maintained per-component table in `TESTING.md`

This would make the first page immediately concrete, but it would drift quickly
across 40+ projects and multiple matrices. Prefer a small standard template and
a generated inventory backed by authoritative metadata.

### Treat each subproject's own CI as sufficient

Component CI remains valuable for focused coverage and unusual configurations,
but ROCm Core is shipped as one product. TheRock must regularly assemble and
test components together to catch API, package, dependency, and configuration
interactions.

### Put all logic in GitHub Actions and test by repeated workflow runs

Workflow runs are slow and GitHub-specific. Keep workflows thin and test
deterministic behavior in reusable scripts, while retaining real dev/manual
workflow runs for orchestration semantics that unit tests cannot prove.

### Use GitGraph for the submodule lifecycle

GitGraph visually implies merges and a single repository history, which is
misleading for independent source repositories, TheRock submodule pins, and
rockrel workflows. Prefer a sequence/timeline diagram with repository lanes.

### Put detailed infrastructure operations in `TESTING.md`

The page should explain progressive rollout, health checks, observability, and
recovery as testing principles. Concrete pool-management procedures, alerts,
and incident response belong in focused infrastructure documentation.

## Open questions for the next editing session

- Should the general coverage model be added before the initial PR lands, or as
  the first follow-up?
- Should component coverage metadata extend `test_policies.toml`, live in
  `BUILD_TOPOLOGY.toml`, or use a separate `TEST_TOPOLOGY.toml`/registry?
- What is the minimum coverage contract for a shipped runtime/library versus a
  build-time utility or test-only support component?
- Which project identifiers become canonical across source repositories,
  consumer graph, build artifacts, packages, and test runners?
- Which current `continue-on-error` and expected-failure tests are intentional,
  and who owns converting them to blocking coverage?
- What small benchmark set is stable enough for presubmit gating, and which
  broader performance suites belong in nightly/on-demand runs?
- What size thresholds and comparison baseline would have caught past binary
  regressions without creating excessive noise?
- What exact states should Quartz expose between initial publication, ROCm
  validation, downstream notification, downstream result, and promotion?
- Which runner-health failures should automatically quarantine a machine, and
  what system owns that action?
- Which documentation examples are important enough to become executable tests?

## How to resume this work

1. Re-read the current `D:/projects/TheRock/TESTING.md`; the branch is active and
   may have changed since this snapshot.
2. Read the companion
   [`testing_audits-2026-08-10.md`](./testing_audits-2026-08-10.md) for file-level
   evidence and the full component inventory.
3. Re-run targeted repository searches before converting any dated observation
   into documentation or an issue.
4. Decide whether the next unit of work is policy/documentation or an
   implementation sprint. Do not hide implementation gaps by wording them as
   intentional strategy.
5. For a documentation follow-up, the highest-leverage sequence is likely:
   - add the coverage-state vocabulary;
   - add the component testing-strategy template;
   - explain cross-repository TheRock CI selection and the PR-to-release
     lifecycle;
   - then add testing-system health and framework/Quartz sections.
6. Add diagrams only after the corresponding prose is stable. Keep node labels
   short and use sequence/timeline formats for cross-repository behavior.

Prepared with OpenAI Codex from the TESTING.md drafting conversation, the
2026-08-10 repository audit, and the current local TheRock checkout.
