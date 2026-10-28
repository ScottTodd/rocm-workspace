# Review: TheRock #9057

- PR: https://github.com/ROCm/TheRock/pull/9057
- Title: Defer subproject CMake includes until project initialization
- Reviewed: 2026-10-28
- Head: `fbbc695d66d64127d4fdac27a3683591d7ef2efb`
- Base: `d3cb9f169eb8526bc7def08149f6eadb781361ed`
- Scope: comprehensive, emphasizing motivation, alternatives, side effects, and maintenance.

## Explanation of the changes

The missing dependency lookup was a subproject build-system bug. CMake does not necessarily report it as a configuration error, however. There are two distinct failure modes here: a consumer failing to load its dependency's package definition, and TheRock's injected workaround loading that definition too early.

### Standalone subproject builds

The benchmarks linked to AMD SMI using code equivalent to:

```cmake
target_link_libraries(benchmark PRIVATE amd_smi)
```

If a visible CMake target named `amd_smi` exists, this uses its library location and propagates usage requirements such as include directories. If no such target exists, CMake accepts `amd_smi` as a plain library name, normally emitting `-lamd_smi` on Linux. Consequently, configuration can succeed without loading the package. Compilation can then fail to find `<amd_smi/amdsmi.h>`, or linking can fail to find the library. The build can also happen to succeed if other configuration or compiler defaults supply those paths. This ambiguity is documented in [target_link_libraries](https://cmake.org/cmake/help/latest/command/target_link_libraries.html). A namespaced target name containing `::` would instead cause an error if the target were undefined.

The proper consumer configuration, after `project()`, is:

```cmake
find_package(amd_smi REQUIRED)
target_link_libraries(benchmark PRIVATE amd_smi)
```

The lookup loads the package definition and its imported target. If the package is unavailable, `REQUIRED` produces an explicit configuration failure. The caller can supply the installation location through normal mechanisms such as `CMAKE_PREFIX_PATH` or `amd_smi_DIR`. The upstream fix adds this lookup under the same platform/compiler conditions that require AMD SMI monitoring; Windows and applicable NVIDIA configurations do not require it.

### Builds under TheRock

TheRock runs each subproject in a separate CMake configuration. Building AMD SMI does not automatically define its imported target inside rocRAND's configuration. Three responsibilities remain distinct:

| Responsibility | Mechanism |
| --- | --- |
| Build/stage a dependency before configuring its consumer, and compose its runtime distribution where needed | TheRock's `BUILD_DEPS` / `RUNTIME_DEPS` declarations |
| Load the dependency's package definition into the consumer's CMake configuration | The consumer's `find_package()` call |
| Apply library and include-directory requirements to a consuming target | `target_link_libraries()` referencing the imported target |

The [dependency setup code](https://github.com/ROCm/TheRock/blob/fbbc695d66d64127d4fdac27a3683591d7ef2efb/cmake/therock_subproject.cmake#L1505) exposes declared dependencies' package locations. The [dependency provider](https://github.com/ROCm/TheRock/blob/fbbc695d66d64127d4fdac27a3683591d7ef2efb/cmake/therock_subproject_dep_provider.cmake) redirects a consumer's lookup to the staged package. When enabled, it can also reject a lookup for a known superproject package lacking the appropriate dependency declaration. It cannot detect an omitted lookup: there is no call to intercept. This follows the [build-system manual's model](https://github.com/ROCm/TheRock/blob/fbbc695d66d64127d4fdac27a3683591d7ef2efb/docs/development/build_system.md): independently configurable subprojects discover packages, while TheRock controls build ordering and package resolution.

### The old workaround versus this PR

The old `therock_primlibs_benchmark_deps.cmake` workaround injected `find_package(amd_smi REQUIRED CONFIG)` into the consumer, compensating for the missing subproject lookup. That workaround could make a TheRock build succeed while the corresponding standalone build remained broken.

The injected lookup ran through `CMAKE_PROJECT_TOP_LEVEL_INCLUDES`, before language initialization. It found the package, but loading its exported shared target could fail under CMP0164 NEW because shared-library support had not yet been initialized. This was an initialization-order failure, not evidence that AMD SMI was unavailable or that CMake had detected the missing consumer lookup.

**PR #9057 enables such an injected workaround to execute at a suitable point; it does not itself introduce the workaround or start silently accepting missing dependencies.** An injected `find_package(... REQUIRED)` still fails if the package cannot be found. If we choose to compensate for a subproject omission with an injected lookup, this PR makes that choice work correctly. It does not diagnose the omission or repair standalone builds. The upstream benchmark fix and subsequent removal of the injection address those concerns directly.

The review's objection is therefore about whether this general capability justifies changing existing include timing after the known callers have been fixed, rather than about the PR weakening dependency validation.

## Assessment

**REJECTED as currently motivated.** I recommend closing this version and retaining the narrower fixes already merged. This is a design/cost-benefit judgment, not a claim that the dispatcher is demonstrably broken. I found no confirmed correctness or security defect in the implementation reviewed.

The original failure is real, and the proposed later execution point fixes a minimal reproduction. However, the reviewed base already removes both reported causes. The PR changes the contract of a shared extension point and adds hook-composition machinery without identifying a remaining production caller that needs it.

## Findings

### IMPORTANT: The motivating callers have already been fixed without this abstraction

Location: [therock_subproject.cmake, lines 890–936](https://github.com/ROCm/TheRock/blob/fbbc695d66d64127d4fdac27a3683591d7ef2efb/cmake/therock_subproject.cmake#L890-L936).

The original [issue #8847](https://github.com/ROCm/TheRock/issues/8847) identifies premature imports of AMD SMI and LibElf. These were genuine failures, rather than hypothetical CMake incompatibilities. But:

- [ROCm/rocm-libraries #13767](https://github.com/ROCm/rocm-libraries/pull/13767) merged October 16 and puts AMD SMI discovery in the four benchmark directories, after project initialization.
- [TheRock #9369](https://github.com/ROCm/TheRock/pull/9369) merged October 19 and removes the injected AMD SMI lookup after the upstream fix propagated through the submodule pin. This removal is already in the reviewed head/base. The [benchmark include variable is empty](https://github.com/ROCm/TheRock/blob/fbbc695d66d64127d4fdac27a3683591d7ef2efb/math-libs/CMakeLists.txt#L4-L17).
- [TheRock #9033](https://github.com/ROCm/TheRock/pull/9033) merged October 15 and removes the redundant ROCR LibElf pre-hook. This is also already in the reviewed tree.

Every remaining nonempty in-tree `CMAKE_INCLUDES` declaration I found supplies `therock_explicit_finders.cmake`: 25 occurrences across seven declaration files. That module defines finder overrides; it does not create imported shared targets. I found no production `CMAKE_PROJECT_INCLUDE` consumer in the superproject source requiring the new chaining behavior either. External/user hooks are possible, but do not establish the need for this timing change.

**Recommendation:** close this PR, or identify a surviving failing caller and evaluate a fix at that caller. Update the motivation to acknowledge that the two known triggers are already gone. Generic future support for imports is a feature proposal with a broader compatibility contract, rather than a necessary fix for the reported failure today.

### SUGGESTION: Preserve the early finder override unless a later execution point is required

Locations: [dispatcher installation](https://github.com/ROCm/TheRock/blob/fbbc695d66d64127d4fdac27a3683591d7ef2efb/cmake/therock_subproject.cmake#L932-L935), [explicit-finder purpose](https://github.com/ROCm/TheRock/blob/fbbc695d66d64127d4fdac27a3683591d7ef2efb/cmake/therock_explicit_finders.cmake#L4-L22).

Moving all additional includes also moves this existing shim from before language initialization to afterward. It will consequently no longer intercept matching finder calls made during that intervening phase, for example by a subsequently read toolchain/platform module. This is a compatibility exposure inferred from the execution order, not a reproduced failure in a current ROCm component. Ordinary finder calls after `project()` still receive the overrides.

The module's own documentation describes it as usable in pre-hooks. Moving it later brings no identified benefit to its current job. If a future package import needs a later point, keep that distinct from early configuration/lookup customization rather than changing every existing include's timing.

## Answers to the requested questions

### 1. Is the motivation sound, and is the problem real?

Historically yes; currently insufficient to justify this PR. `CMAKE_PROJECT_TOP_LEVEL_INCLUDES` runs before languages are enabled, whereas `CMAKE_PROJECT_INCLUDE` runs afterward. An imported shared target created at the former point can fail under CMP0164 NEW. CMake's [project execution order](https://cmake.org/cmake/help/latest/command/project.html#code-injection) and [CMP0164 documentation](https://cmake.org/cmake/help/latest/policy/CMP0164.html) support the diagnosis. A local CMake 3.31.5 reproduction also confirmed it, so the underlying issue is not exclusive to CMake 4.

The PR description understates the current state: the upstream benchmark fix is no longer merely something that might land; it and the TheRock workaround removal have both landed. A synthetic regression test establishes that the new mechanism works, but does not establish that the mechanism is still needed by this tree.

### 2. Would simpler alternatives work better?

| Alternative | Assessment |
| --- | --- |
| Retain the existing narrow upstream fixes and remove obsolete injection | Preferred. Already done for both reported triggers. Packages are found where they are consumed, and standalone builds benefit too. |
| Add a targeted post-project hook for a genuinely unmodifiable component | Reasonable only if a surviving caller requires it. Limit the timing change to that component and validate its ordering needs. |
| Keep only include dependency/fingerprint tracking | Potentially useful independently if stale configurations are reproducible. It does not require changing execution timing. |
| Set `TARGET_SUPPORTS_SHARED_LIBS` TRUE before importing | Avoid as a general fix. It asserts platform capability before normal initialization and assumes that capability is valid for every affected target/toolchain. |
| Force CMP0164 OLD | Avoid. It masks premature initialization and may turn an imported shared target into a static one; policy choices in package exports also complicate this workaround. |
| Move imports to the existing end-of-directory post hook | Usually too late: project configuration may already consume those targets. |

If a general late-include API becomes justified, a named CMake dispatcher file would be easier to read and debug than many generated string fragments. Preserve early initialization hooks separately. CMake already supplies [post-project injection](https://cmake.org/cmake/help/latest/variable/CMAKE_PROJECT_INCLUDE.html); composing it with existing hooks and a once-only guard is the extra contract this implementation chooses to own. List-valued native hook composition requires CMake 3.29, so do not suggest simply prepending a list without checking the supported minimum.

### 3. What side effects will this have?

- **Execution order changes across 25 declarations.** Additional includes see initialized project/compiler state, but can no longer prepare state for initial language detection. They also move after the flag-initialization content generated below them. The pre-hook and deferred end-of-directory post-hook keep their existing execution points.
- **TheRock takes ownership of `CMAKE_PROJECT_INCLUDE`.** The normal variable points to its generated dispatcher. The previous value is captured separately and invoked afterward on each project call, including nested projects. TheRock's own includes run once per configure process. This is tested, but is additional state and ordering for developers to understand when inspecting their build trees.
- **Include edits gain stronger invalidation.** The original include files and generated dispatcher become configure prerequisites and fingerprint inputs. That is a useful correctness improvement, but an edit to the common finder shim can invalidate many configured projects and their dependent fingerprints. Existing artifact reuse may also change when fingerprints change. This is build/cache churn, not an intended ABI or packaging change.
- **An additional generated file appears per affected subproject.** Runtime overhead is small: configure-time file inclusion and hook dispatch. There is no new library or deployment dependency and no intended change to compilation or linking commands.
- **This is not a universal cure for premature imports.** A package import in a retained pre-hook would still execute early; the PR only relocates `CMAKE_INCLUDES`.

No current build failure caused by these ordering changes was established. They are reasons to demand a concrete benefit before accepting a broader extension-point contract.

### 4. How much maintenance burden?

**Modest in code volume, disproportionate to the remaining demonstrated need.** The production file grows by 48 net lines. The PR adds a 206-line behavioral test file and a 37-line shared helper while reducing the older test. The tests use real CMake configurations and validate useful behavior; they are not mock-only call-sequence tests.

The lasting cost is the hook lifecycle: generated quoting, preserved user hooks, once-per-configure versus per-project execution, nested scope/target visibility, and incremental/fingerprint invalidation. A future change in any of these areas must consider all the others. The shared helper extraction is reasonable and is not itself a concern.

CI reports about 8.9 seconds for the two new tests on Linux and 15.8 seconds on Windows. That cost is reasonable if this feature is needed. It does not justify retaining an otherwise unnecessary abstraction.

## Validation and limits

Reviewed all five changed files, the remaining include declarations, finder shim, generated initialization order, dependency/fingerprint wiring, PR discussion, related issue/fixes, and CI checks. The change is host-side build infrastructure; representative Linux/Windows configurations and targeted incremental tests are appropriate. A GPU architecture sweep is not necessary to validate this dispatcher itself. No additional feature flag is needed for a narrowly validated build fix.

Both new tests passed in [Linux unit CI](https://github.com/ROCm/TheRock/actions/runs/40592690989/job/122500691607) and [Windows unit CI](https://github.com/ROCm/TheRock/actions/runs/40592690989/job/122500691042). Their meaningful failure modes are early/repeated execution, lost/reordered caller hooks, missing nested target visibility, and stale output after an include edit. The Linux suite reported 3341 passed; Windows reported 3259 passed. Required checks were green when inspected.

Full CI is not green. I inspected the four nonsummary failed jobs: [rocFFT](https://github.com/ROCm/TheRock/actions/runs/40592691656/job/122603916977) timed out at 600 seconds; [rocSPARSE](https://github.com/ROCm/TheRock/actions/runs/40592691656/job/122603917075) timed out at 300 seconds; [MSI](https://github.com/ROCm/TheRock/actions/runs/40592691656/job/122548913457) and [JAX](https://github.com/ROCm/TheRock/actions/runs/40592691656/job/122545177648) failed uploading to S3. Two Python wheel tests were cancelled. These logs do not establish a dispatcher regression; the GPU timeouts were not root-caused or compared against a matched baseline, so they should not be called proven pre-existing failures.

Local source archive and complete downloaded job logs are under `D:/scratch/codex/pr9057/`. Main checkout and submodules were left unchanged. No GitHub comments were posted.

Locally, both dispatcher tests passed in 6.704 seconds and both prebuilt tests passed in 2.842 seconds using CMake 3.31.5, Ninja, and the Visual Studio x64 developer environment. The initial pytest attempts stalled before producing test output and were stopped; direct unittest execution with Python `-S` avoided local site initialization. The first sandboxed direct attempt hit temporary-directory access restrictions; the approved unsandboxed rerun passed. No tests or assertions were modified.

Full command and output are saved in `D:/scratch/codex/pr9057/run-direct-tests.cmd` and `D:/scratch/codex/pr9057/local-direct-tests.log`. From the extracted PR root, the runner executes:

```text
call "C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvars64.bat"
D:/projects/TheRock/.venv/Scripts/python.exe -S cmake/tests/therock_subproject_project_include_test.py
Ran 2 tests in 6.704s
OK
D:/projects/TheRock/.venv/Scripts/python.exe -S cmake/tests/therock_subproject_prebuilt_test.py
Ran 2 tests in 2.842s
OK
```

### Local minimal reproduction

Using CMake 3.31.5, `minimal/CMakeLists.txt` contained:

```cmake
cmake_minimum_required(VERSION 3.30)
project(repro LANGUAGES NONE)
```

`minimal/hook.cmake` contained:

```cmake
cmake_policy(SET CMP0164 NEW)
get_property(shared GLOBAL PROPERTY TARGET_SUPPORTS_SHARED_LIBS)
message(STATUS "supports_shared=${shared}")
add_library(dep SHARED IMPORTED)
```

Commands, with full outputs saved as `minimal/early.log` and `minimal/late.log`:

```text
cmake -S D:/scratch/codex/pr9057/minimal -B D:/scratch/codex/pr9057/minimal/early -GNinja -DCMAKE_PROJECT_TOP_LEVEL_INCLUDES=D:/scratch/codex/pr9057/minimal/hook.cmake
-- supports_shared=
ADD_LIBRARY called with SHARED option but the target platform does not support dynamic linking.
-- Configuring incomplete, errors occurred!

cmake -S D:/scratch/codex/pr9057/minimal -B D:/scratch/codex/pr9057/minimal/late -GNinja -DCMAKE_PROJECT_INCLUDE=D:/scratch/codex/pr9057/minimal/hook.cmake
-- supports_shared=TRUE
-- Configuring done (0.0s)
-- Generating done (0.0s)
```

Generated with Codex
