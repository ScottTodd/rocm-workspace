# Separate test selection from runner availability

Status: proposed design, with implementation sketches; no workflow changes yet.

Delivery decision: two independently reviewable commits/PRs. The first introduces
the data contract and plumbing while preserving existing scheduling behavior.
The second changes eligibility so hardware restrictions affect GPU tests only.
The contract and algorithm below describe the destination; the migration section
specifies which parts belong in each PR.

Context: [TheRock PR 8465](https://github.com/ROCm/TheRock/pull/8465).
Inspected local TheRock revision `e323b0e8b` and the PR diff on 2026-09-24.

## Background - conversation prompts

```
› I'd like some help proposing an alternate design for https://github.com/ROCm/TheRock/pull/8465. My desired
  architecture is:
  * build_tools/github_actions/configure_multi_arch_ci.py _expand_build_config_for_platform() function stops treating
  `test_runs_on = ""` as meaning "disable tests" but rather "no available runner for GPU tests, CPU tests may still be
  enabled"
  * possibly the `family_info` dictionary should be generalized to carry `test-runs-on-gpu`, `test-runs-on-multigpu`,
  `test-runs-on-cpu`, etc.
  * .github/workflows/multi_arch_ci_linux.yml test_artifacts_per_family expands the `matrix: family_info:
  ${{ fromJSON(inputs.build_config).per_family_info }}` then test_artifacts.yml uses the data there together with
  test_tools/determine_rocm_test_dependencies.py and build_tools/github_actions/fetch_test_configurations.py. Any code
  in there that assumes "no gpu test runner" means "no tests" should be updated, including `if:
  ${{ inputs.test_runs_on != '' }}` in test_artifacts.yml
  * fetch_test_configurations.py can decide which tests to run based on provided labels (CPU only, GPU, subproject tests
  included/excluded based on files modified, labels set, etc.)

  Does that sound plausible? Let's work through the design a bit with the goal of providing a markdown plan that could
  be implemented or (ideally) a prototype branch showing the shape of the changes

...

› test_sanity_check is interesting, we could split the matrix into CPU (which doesn't wait for test_sanity_check) and
  GPU (which does), or we could merge test_sanity_check (as test_sanity_check_gpu maybe?) into the test_component
  matrix. The current design aims to skip running subproject tests if sanity checks fail, but I think in practice we see
  very few PRs where that is the case (pretty much only changes to the compiler and core runtimes can affect the sanity
  check tests - library tests like hipblaslt can't possibly affect them)

  we could also redesign the "Route to the appropriate runner" comment code conditions under test_components. Always
  pass the specific runner as computed by the script, without needing to pass so many fields and choose in the yml
```

## Objective

An empty GPU runner means GPU tests cannot run. CPU tests remain eligible when
CPU capacity and test policy permit them. Test selection and execution resources
must have separate representations; neither should be inferred from the other.

Replace the proposed `allow_cpu_only_tests` / `opt_in_when_no_gpu_runner`
exception mechanism with an effective per-family runner contract. CPU components
use the same family, tier, label, dependency, and artifact filters whether GPU
hardware is available or not.

## Current flow and its constraints

1. `configure_multi_arch_ci.py::_expand_build_config_for_platform()` writes
   `test-runs-on`, clearing it for several unrelated reasons: hardware opt-in,
   kernel mismatch, ASAN restrictions, nightly-only, submodule-only, and quick-tier
   exclusions. Its TODO also notes that `test_rocm.action` is not yet plumbed.
2. `multi_arch_ci_linux.yml` already expands `per_family_info`, but passes only
   selected scalar fields to `test_artifacts.yml`. Windows uses the same workflow.
3. `test_artifacts.yml` skips matrix configuration if that scalar is empty.
   It derives the platform from the GPU runner name.
4. `determine_rocm_test_dependencies.py` maps changed projects through the
   committed consumer graph and test policy into CI component selectors. Empty
   changed-project input means unrestricted selection (`*`).
5. `fetch_test_configurations.py` filters components, then independently reloads
   static family runner configuration and draws weighted runners per component.
   This second lookup does not know which pools the earlier step disabled.
6. YAML applies another routing decision: dispatch override, multi-GPU runner,
   hard-coded CPU runner, then component runner. Pinned component runners and
   ASAN sandboxes are additional paths that must respect effective eligibility.

The PR's narrower behavior intentionally excludes other CPU components when GPU
hardware is unavailable. The alternative changes that policy: eligible CPU tests
can run generally. If a component is not qualified on a family, express that in
its ordinary `include_family` / `exclude_family` configuration.

## Proposed contract

Keep the existing flat naming for a small first implementation. Use
`multi-gpu`, matching existing configuration, rather than introducing `multigpu`.
Example effective `family_info` for a CPU-capable family without authorized GPU
capacity:

```json
{
  "amdgpu_family": "gfx950-dcgpu",
  "amdgpu_targets": "gfx950",
  "platform": "linux",
  "tests_enabled": true,
  "test-runs-on-cpu": "aws-linux-scale-rocm-prod",
  "test-runs-on-gpu": "",
  "test-runs-on-gpu-labels": {},
  "test-runs-on-multi-gpu": "",
  "test-runs-on-multi-gpu-labels": {},
  "sanity_check_only_for_family": false
}
```

`tests_enabled` is an explicit policy veto, not a synonym for GPU availability.
It is false for an intentional family-wide test skip. An unavailable resource
has an empty default runner and empty weighted pool. The weighted-pool values
retain the existing CI configuration schema; the empty objects above illustrate
absence only. A nonempty weighted pool is sufficient even without a default.

* Resolve policy and available pools once in build configuration.
* Perform weighted draws later, independently per selected component.
* Effective input is authoritative: never fill its empty pools from static data.
* Emit platform explicitly; a CPU-only Windows request must not become Linux.
* Keep GPU-only `test-runs-on` and `test-runs-on-labels` compatibility aliases
  temporarily for Python-package tests and other existing consumers. Never put
  the CPU runner into these aliases.
* Resolve kernel and ASAN substitutions before serializing the effective pools.
  A selected kernel/sandbox must replace incompatible weighted candidates too.
* Do not infer ASAN-compatible multi-GPU capacity from ordinary multi-GPU pools.
  Preserve the restriction unless a compatible pool is explicitly configured.

## Policy classification

These are the target semantics for PR 2. PR 1 preserves the current interpretation
of every gate, including suppression of CPU tests when the legacy GPU runner is
empty. Hardware-related restrictions become GPU-only in PR 2; an intentional
all-tests policy must be represented explicitly instead of inferred from a runner.

| Condition | Target meaning (PR 2) | CPU outcome |
| --- | --- | --- |
| Global test decision is SKIP | Set `tests_enabled=false` | Disabled |
| Family GPU opt-in label absent | Clear all GPU pools, including special routes | Eligible |
| No GPU hardware configured | Empty GPU pools | Eligible |
| Requested kernel unavailable | Clear GPU pools lacking that kernel | Eligible |
| Family nightly-only/submodule-only gate used to conserve GPU capacity fails | Clear affected GPU pools | Eligible |
| `run-full-tests-only` used to conserve GPU capacity with quick tier | Clear affected GPU pools | Eligible, subject to component tier |
| ASAN GPU trigger gate fails or GPU sandbox unavailable | Clear affected GPU pools | Eligible if component and CPU environment support the variant |
| Explicit policy disables all tests, independent of hardware | Set `tests_enabled=false` | Disabled |
| Component family/tier/artifact restriction fails | Exclude that component | Disabled for that component |

Compute vetoes independently of runner substitutions so a later substitution
cannot undo a previous denial. Log the reason for exclusions. Audit the motivation
of each existing family gate during PR 2: ambiguous names alone do not prove a
hardware restriction. Document any genuine all-tests restriction explicitly.
In PR 1, preserve `test_type_for_family` precedence and GPU-dependent activation.
In PR 2, a family tier override intended to conserve GPU capacity applies only to
GPU components; CPU components retain the requested tier and their own `test_types`
filter. Resolve effective tiers per resource before component tier filtering.

## Workflow interface

Pass the whole effective object through a JSON string input:

```yaml
# multi_arch_ci_linux.yml and multi_arch_ci_windows.yml
with:
  family_info: ${{ toJSON(matrix.family_info) }}
```

The existing family matrix remains unchanged. In `test_artifacts.yml`, normalize
input once and then run dependency determination and component selection when
test policy permits, regardless of the single-GPU pool. Pass JSON through an
environment variable, not interpolation into shell source. Matrix configuration
runs on its existing CPU host; that host's OS is not the target platform.

`fetch_test_configurations.py` should return executable components with a single
resolved `test_runner`. YAML then uses only that value for `runs-on`. Retain
`linux_cpu_runner` temporarily for container/driver behavior in `test_component.yml`,
but eliminate the separate YAML CPU runner literal and competing routing rules.
No selected component may leave the selector without a concrete runner.

The destination workflow routing is simply:

```yaml
test_components:
  needs: configure_test_matrix
  strategy:
    fail-fast: false
    matrix:
      components: ${{ fromJSON(needs.configure_test_matrix.outputs.components || '[]') }}
  uses: ./.github/workflows/test_component.yml
  with:
    test_runs_on: ${{ matrix.components.test_runner }}
    component: ${{ toJSON(matrix.components) }}
```

This sketch omits the nonempty-matrix guard and unchanged workflow inputs.
CPU flags and resource requirements remain script inputs or execution metadata
where needed, not alternative runner choices in YAML. Once assignment is complete,
omit routing-only fields such as `multi_gpu_runner` from the emitted component.
Pass explicit manual override context to the script rather than making it infer
the reusable-workflow call chain. In PR 1, extracting existing routing precedence
into the script is acceptable only with equivalence coverage; correcting that
precedence remains PR 2 work.

Manual runner overrides must be normalized by resource class before selection.
A single-GPU override must not replace a required multi-GPU runner or a CPU
assignment. This intentionally corrects the current override precedence.

## Selection algorithm

Keep graph traversal and project normalization in
`determine_rocm_test_dependencies.py`; do not duplicate file-diff or dependency
logic in the matrix selector.

```python
if not family_info.tests_enabled:
    return empty_matrix()

for component in components:
    if not matches_platform_family_tier_and_artifacts(component):
        continue
    if not matches_project_and_label_selection(component):
        continue
    resource = required_resource(component)  # cpu, gpu, multi-gpu
    runner = select_effective_runner(component, resource, family_info)
    if not runner:
        record_skip(component, "required runner unavailable")
        continue
    emit(component, test_runner=runner)
```

Initially derive requirements from `linux_cpu_runner` and `multi_gpu`; ordinary
components require GPU. Validate conflicting requirements. Pinned runners such
as `rocgdb-corefile` cannot bypass GPU denial; allow a pin only when the effective
policy permits it and it satisfies kernel/variant constraints. Treat specialized
pins as explicit compatible candidates, never an unconditional escape hatch.

Preserve existing component-label groups and the current intersection with
dependency selection initially. Define CPU/GPU labels as resource filters, in a
separate parsed category from component names: a CPU filter intersects selected
components rather than looking for a component literally named `cpu`. Multiple
resource selectors form a union; unrelated filters intersect. Labels cannot
manufacture hardware or bypass platform/family/artifact compatibility.

If explicit component labels should override changed-project filtering, make that
a separate documented change. Today the selector requires both to match.
Preserve the existing per-family label override precedence during migration.
Represent unrestricted selection separately from an explicitly empty selection;
do not let an empty intersection become 'run everything'.

For MIOpen dbsync specifically, add gfx950 to its ordinary family allowlist and
keep its standard/comprehensive/full tier restriction. Also wire `miopen-dbsync`
into dependency/policy selection: the current selector does exact component-key
matching, and `miopen` alone does not select `miopen-dbsync`. Choose an alias/group
or policy edge based on the intended MIOpen/rocjitsu coupling and test it. Any
temporary expected-failure policy belongs in a separate qualification change.

## Sanity checks and empty matrices

PR 1 preserves the separate sanity job and all existing dependencies. For PR 2,
the recommended design is to put GPU sanity into the ordinary component matrix
and remove the prerequisite. This recommendation is proposed, not yet a settled
user decision.

| Option | CPU behavior | GPU behavior | Tradeoff |
| --- | --- | --- | --- |
| Separate CPU and GPU matrices | Starts after configuration | Waits for separate GPU sanity | Preserves early suppression of GPU work, but adds another matrix job and conditional dependency handling |
| One matrix, including GPU sanity | Starts after configuration | Starts alongside GPU sanity | Simpler workflow and no serial sanity delay; broad failures can consume more runner time |

The user reports that sanity failures are rare and primarily associated with
compiler/core runtime changes. That supports reconsidering a universal gate;
this proposal has not measured failure frequency or saved GPU time. A library-only
source change normally cannot alter these base tests, although shared CI,
packaging, artifact, and runner changes can still cause failures. Furthermore,
sanity on one independently selected runner does not certify every component's
runner environment.

Under the recommended single-matrix design:

* Keep the existing `sanity` selector key for compatibility, with a display name
  such as `sanity-gpu`. A selector-key rename is unnecessary churn.
* Include sanity whenever compatible GPU capacity exists, independently of
  subproject selection, preserving current coverage. An explicit CPU-only resource
  filter excludes it. Do not route it to CPU by default.
* Allow a compatible multi-GPU pool to supply its runner when single-GPU capacity
  is absent. This is an explicit sanity capability, not a general fallback for
  components with stricter hardware requirements.
* CPU and GPU components depend only on successful matrix configuration. Keep
  `fail-fast: false` so a sanity failure does not cancel sibling tests.
* Sanity failure still fails the test workflow; it only stops suppressing sibling
  execution. Do not use `continue-on-error` for sanity.
* Move `sanity_check_only_for_family` handling into selection: emit only sanity,
  or an empty matrix when no compatible GPU exists. A workflow-wide component
  guard would incorrectly suppress sanity once it shares that matrix.
* Emit all jobs through `components`, removing the special `sanity_component`
  output and `test_sanity_check` job. No `has_sanity` output is needed.
* Emit `components=[]` for no eligible tests, with explicit workflow guards for
  successful configuration, nonempty selection, and cancellation. Guard JSON
  parsing when configuration was skipped.
* Update completion reporting and audit required check names before renaming or
  removing the separate job. Branch protection may refer to the old check name.

If retaining the GPU gate is preferred, emit `cpu_components`, `gpu_components`,
and optional sanity separately. CPU jobs depend only on configuration; GPU jobs
require successful sanity. Explicitly distinguish intentional absence from failed
configuration. Do not put CPU jobs behind the skipped/failed sanity dependency.
A conditional gate only for compiler/runtime changes adds policy and dependency
complexity and is deferred unless observed failure costs justify it.

## Migration and implementation sequence

### PR 1: Carry runner configuration through the existing test pipeline

Goal: identical scheduling decisions with an explicit producer-to-consumer data
path. This PR should be safe to merge without committing to the eligibility change.

1. Extract normalization of static runner configuration into a shared helper.
   Construct family metadata in `configure_multi_arch_ci.py` with CPU, default
   GPU, weighted GPU, multi-GPU, sandbox, and platform information. Preserve the
   distinction between the legacy gate runner and the pools the selector currently
   reads: kernel/sandbox handling can make these disagree today.
2. Pass that metadata as JSON through Linux and Windows `test_artifacts.yml`
   callers. On the new path, the selector consumes transported pools instead of
   loading static pools again. Keep weighted selection per component.
3. Retain `test_runs_on != ''` as the scheduling gate, existing tier and label
   precedence, pinned-runner behavior, dispatch override precedence, and YAML CPU
   routing. CPU metadata is descriptive in this PR; it does not enable new jobs.
   Do not yet require final concrete runners from every selector entry, since
   current YAML completes some assignments.
4. Keep old inputs and GPU aliases for existing callers. A single compatibility
   adapter handles absent JSON using the legacy path. Supplied JSON is
   authoritative, even if its pools are empty; malformed JSON fails explicitly.
5. Inventory manual, release, compiler-bump, Python-package, and rockrel consumers.
   Migrate compatible callers or cover their legacy adapter behavior. Leave their
   scheduling guards unchanged.

Do not silently fix existing routing discrepancies in this refactor. Transport
the data needed to reproduce them, and name those temporary compatibility fields
clearly (for example, `legacy_test_runs_on`). PR 2 converts the transported runner
configuration into effective policy-filtered availability. This prevents claiming
behavior preservation while actually changing kernel, ASAN, or dispatch routing.

Acceptance: equivalent selected components, effective execution runners/pools,
tiers, shards, and workflow skips for existing inputs. Stub weighted draws or
compare candidate pools and weights; random runner choices are not stable golden
outputs. Include CPU components with and without a legacy GPU gate, pinned GPU
components, ASAN, kernel labels, Windows PAL/ROCR, and manual overrides. Do not
test only the selector: final YAML routing is part of current behavior.

The producer and consumer currently check out mutable CI configuration separately.
Transporting a single snapshot intentionally removes that source of inconsistency;
behavior equivalence is defined for the same configuration snapshot. Also cover
external family overrides, whose propagation can otherwise change scheduling.
If those overrides differ from the selector's old inputs, preserve the old path
for that case in PR 1 and migrate it explicitly in PR 2.

### PR 2: Make hardware restrictions GPU-only

Goal: CPU eligibility no longer depends on GPU availability.

1. Apply the policy classification above to the transported configuration, emitting
   effective pools and explicit all-tests vetoes. Clear default, weighted, sandbox,
   and special GPU candidates consistently. Make resource-specific tier decisions
   before filtering components.
2. Replace legacy GPU-only workflow guards with explicit test-policy handling.
   Use the explicit platform, including for CPU-only Windows requests. Update
   release/manual paths so they can reach selection without a GPU runner.
3. Centralize final runner assignment in the selector, including CPU components,
   special pins, and resource-scoped dispatch overrides. Remove competing YAML
   routing. Exclude components lacking a compatible effective runner.
4. Implement the chosen sanity design and empty-matrix guards described above.
   Recommended: ordinary GPU sanity component, no sibling dependencies on it,
   and one matrix with resolved runners. Cover multi-GPU-only capacity, failed
   configuration, sanity failure, and sanity-only family selection.
5. Enable gfx950 dbsync through ordinary family/tier/dependency metadata. Document
   the additional CPU components that become eligible and their per-family cost.
   Keep any temporary expected-failure qualification separate from routing policy.
6. Add resource labels if required for the initial use case; otherwise keep them
   as a follow-up using the selection semantics above. Preserve existing component
   label/dependency precedence in either case.

Acceptance: the behavior matrix below, plus unchanged GPU-enabled cases except
for explicitly documented routing corrections. CPU ASAN compatibility must be
validated independently; lack of a GPU sandbox is not evidence that CPU execution
is either compatible or incompatible.

Keep compatibility inputs until external callers migrate; their eventual removal
can be follow-up cleanup. Both PRs must stand alone, with PR 2 based on PR 1.
The prototype should start from current main in an isolated checkout, not from
the original PR's exception flags. No submodule checkout or product build is needed.

## Validation plan

PR 1 uses the behavior-equivalence checks above. For PR 2, unit-test outcomes,
including combined gates rather than only individual flags:

| Scenario | Expected result |
| --- | --- |
| Unlabeled hardware-opt-in family, CPU available | Eligible CPU components only |
| Same family with GPU opt-in | Eligible CPU and GPU components |
| GPU label absent plus family-wide veto | No tests |
| No default GPU runner, weighted GPU pool present | GPU tests can select pool |
| Empty effective GPU pools, nonempty static pools | No GPU fallback |
| CPU-only with pinned GPU component configured | Pinned GPU component excluded |
| Multi-GPU-only capacity | Eligible multi-GPU tests and compatible sanity |
| Empty all pools or empty selection intersection | Valid empty outputs, no jobs |
| CPU resource label plus GPU component label | Empty selection, not all tests |
| Unsupported kernel and overlapping ASAN rules | No incompatible runner restoration |
| CPU-only Windows target | No Linux inference or Linux CPU fallback |
| MIOpen/rocjitsu relevant changes | Dbsync selected by explicit dependency policy |
| Quick tier with dbsync | Dbsync excluded |
| Failed configuration / cancelled workflow | No component execution |
| Failed sanity (recommended single matrix) | Workflow fails; siblings remain eligible to complete |
| Sanity-only family | Only compatible GPU sanity, or empty matrix |

Run focused existing/new configure and fetch suites from TheRock `build_tools`
using its `.venv/Scripts/python.exe`, with
`--override-ini=cache_dir=D:/scratch/codex/pytest-cache/TheRock-build-tools`.
Run dependency-policy tests when that mapping changes and actionlint on changed
workflows. Use CI to validate reusable-workflow skip semantics and actual CPU
execution; Python tests alone cannot prove those behaviors. No such validation
has been run for this proposal, since it contains no implementation yet.

## Alternatives Considered

* **PR-specific CPU bypass flags:** small and intentionally narrow, but encode
  resource eligibility twice and require special permission for CPU tests to run
  without an unrelated GPU. Ordinary compatibility filters are more general.
* **Only remove the workflow guard:** insufficient; static runner lookup, pinned
  runners, and YAML routing can still schedule GPU tests or produce missing runners.
* **Add CPU defaults solely in the matrix selector:** leaves policy distributed
  across producer and consumer and makes disabled versus missing input ambiguous.
* **Nested versioned runner schema now:** cleaner long-term typing, but more churn
  than extending existing keys. Adopt a small validated internal representation
  while keeping the initial serialized contract flat.
* **Separate CPU workflow or one CPU job for all families:** can reduce duplicate
  work, but CPU tests may consume family-specific artifacts (notably dbsync).
  Deduplication requires explicit artifact equivalence and is out of scope.
* **Separate CPU/GPU matrices with a GPU sanity gate:** valid if early suppression
  saves enough GPU time. The proposed single matrix removes universal waiting and
  simplifies dependency handling, at the cost of running siblings after sanity
  fails. Preserve the gate in PR 1; choose this behavior explicitly in PR 2.
* **Rewrite all selection policy at once:** increases migration risk. Retain
  dependency traversal, component metadata, and label precedence while correcting
  the runner contract first.

Generated with Codex.
