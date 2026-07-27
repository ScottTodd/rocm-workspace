# PR Review: ROCm/TheRock #6813

* **PR:** [ROCm/TheRock#6813](https://github.com/ROCm/TheRock/pull/6813)
* **Title:** `fix(py_packaging): eliminate code injection via exec() on user-controlled input (SEC-00224)`
* **Head:** `users/arravikum/sec-00224-exec-injection` at `4faef7ab4ea973137d15ceaab71d2e2a2dd8b324`
* **Base:** `main` at `d689194358429dc65fdb70fcbcf2e422892898cd`
* **Reviewed:** 2026-07-27
* **Commits:** 4

---

## Summary

The underlying source-generation bug is real: the base revision can execute a
newline payload supplied as `version_suffix`, while the PR head stores that
payload as data. `repr()` (or the equivalent `!r` conversion) is the correct
context-specific encoding when emitting a Python string literal.

The PR should not merge as written. It also changes the meaning of
`version_suffix`, adds tests that pass unchanged against the vulnerable base
implementation, and does not close the `workflow_dispatch` path claimed in the
description because those inputs are first interpolated directly into a Bash
script.

**Net changes:** +96 / -11 lines across 2 files.

---

## Overall Assessment

**CHANGES REQUESTED** - The Python-literal quoting is sound, but the patch
introduces a package-version regression and does not test the production code.
The stated workflow-input threat path also remains injectable at an earlier
shell boundary.

### Strengths

- The PR correctly identifies that values embedded in generated Python source
  must be encoded as Python literals.
- Directly assigning attributes on the in-memory module prevents those values
  from being interpreted as source in that particular execution path.
- Linux and Windows unit-test jobs pass, and the Linux multi-arch Python
  package build completed successfully.

### Blocking issues

1. `version_suffix` is incorrectly appended to `__version__`.
2. The four regression tests do not exercise `Parameters` or generated package
   output and pass against the vulnerable base source.
3. The claimed `workflow_dispatch` attack path remains shell-injectable before
   `repr()` is reached, and the described input provenance does not match the
   repository.

### Important issue

4. The PR introduces two independent implementations of dist-info
   initialization that can drift.

---

## Detailed Review

### 1. BLOCKING: Preserve `version_suffix` as a module-name nonce

[`Parameters.__init__`](https://github.com/ROCm/TheRock/blob/4faef7ab4ea973137d15ceaab71d2e2a2dd8b324/build_tools/_therock_utils/py_packaging.py#L128-L178)
changes both the generated and in-memory `__version__` values from `version` to
`version + version_suffix`.

That is not a quoting-only change. The CLI describes
[`--version-suffix`](https://github.com/ROCm/TheRock/blob/4faef7ab4ea973137d15ceaab71d2e2a2dd8b324/build_tools/build_python_packages.py#L619-L627)
as a suffix for package names on disk, and
[`PackageEntry.get_py_package_name`](https://github.com/ROCm/TheRock/blob/4faef7ab4ea973137d15ceaab71d2e2a2dd8b324/build_tools/packaging/python/templates/rocm/src/rocm_sdk/_dist_info.py#L102-L107)
uses `PY_PACKAGE_SUFFIX_NONCE` for exactly that purpose. It is intentionally
separate from the distribution version.

Reproduction against the exact base and head sources:

```text
BASE_SOURCE
'7.0.0' '_nonce'
__version__ = '7.0.0'

PR_HEAD
'7.0.0_nonce' '_nonce'
__version__ = '7.0.0_nonce'
```

`7.0.0_nonce` is also rejected by `packaging.version.Version`. Current CI does
not expose the regression because the Python-package workflows do not pass
`--version-suffix`.

**Required action:** Emit and assign `__version__ = version`, encoded with
`repr()`/`!r`, and keep `version_suffix` only in
`PY_PACKAGE_SUFFIX_NONCE`. Add a production-path test using a non-empty nonce
that asserts both values independently.

### 2. BLOCKING: Replace tests of `repr()` with tests of production behavior

[`DistInfoInjectionTest`](https://github.com/ROCm/TheRock/blob/4faef7ab4ea973137d15ceaab71d2e2a2dd8b324/build_tools/tests/py_packaging_test.py#L1563-L1624)
constructs isolated source lines inside the tests and executes those lines. It
never calls `Parameters`, `PopulatedDistPackage`, or the code changed by this
PR. The tests therefore verify Python's `repr()` and `exec()` behavior, not
TheRock's source generation.

This is demonstrated by replacing only `py_packaging.py` with the exact base
revision while retaining the PR's test file:

```powershell
D:\projects\TheRock\.venv\Scripts\python.exe -m pytest tests\py_packaging_test.py::DistInfoInjectionTest -q
```

```text
....                                                                     [100%]
4 passed in 0.07s
```

The entire file also passes with the vulnerable base implementation:

```powershell
D:\projects\TheRock\.venv\Scripts\python.exe -m pytest tests\py_packaging_test.py -q
```

```text
..............................................................           [100%]
62 passed in 0.70s
```

The malicious test strings also call `os.system("id")` if a regression makes
them executable. A regression test should use a harmless namespace or
`builtins` sentinel, not launch a process.

The existing
[`_exec_dist_info`](https://github.com/ROCm/TheRock/blob/4faef7ab4ea973137d15ceaab71d2e2a2dd8b324/build_tools/tests/py_packaging_test.py#L1133-L1136)
helper already provides the right seam.

**Required action:** Instantiate real `Parameters` objects with malicious
values, execute/import `params.dist_info_contents`, and assert that a harmless
sentinel was not set and that the original value round-trips as data. Exercise
the actual sources separately: `version`, `version_suffix`, artifact-derived
families, and cross-platform family inputs. At least one test should populate a
package and import the `_dist_info.py` that would be shipped.

### 3. BLOCKING: Close or retract the claimed workflow-input attack path

The description says `version_suffix` is controllable through
`artifact_manifest.json` or `workflow_dispatch`. That does not match the
current call graph:

- There is no `artifact_manifest.json` in the relevant code. `ArtifactCatalog`
  derives `target_family` from the artifact directory/archive name using a
  permissive regular expression, then reads
  [`artifact_manifest.txt`](https://github.com/ROCm/TheRock/blob/4faef7ab4ea973137d15ceaab71d2e2a2dd8b324/build_tools/_therock_utils/artifacts.py#L43-L60).
- The Python-package workflows pass `package_version` as `--version`; they do
  not pass `--version-suffix`.
- The Linux and Windows workflows interpolate `package_version` and both
  family lists directly into Bash source:
  [`build_portable_linux_python_packages.yml`](https://github.com/ROCm/TheRock/blob/4faef7ab4ea973137d15ceaab71d2e2a2dd8b324/.github/workflows/build_portable_linux_python_packages.yml#L153-L160)
  and
  [`build_windows_python_packages.yml`](https://github.com/ROCm/TheRock/blob/4faef7ab4ea973137d15ceaab71d2e2a2dd8b324/.github/workflows/build_windows_python_packages.yml#L154-L161).

Because GitHub expressions are substituted before Bash parses the script, an
input containing a closing quote and shell syntax executes before
`build_python_packages.py` starts. Python-side `repr()` cannot mitigate that
boundary. The family allowlist in
[`expand_families`](https://github.com/ROCm/TheRock/blob/4faef7ab4ea973137d15ceaab71d2e2a2dd8b324/build_tools/_therock_utils/cmake_amdgpu_targets.py#L109-L136)
also runs too late to prevent shell injection.

Artifact-derived families have a different path: the permissive
[`ArtifactName`](https://github.com/ROCm/TheRock/blob/4faef7ab4ea973137d15ceaab71d2e2a2dd8b324/build_tools/_therock_utils/artifacts.py#L36-L60)
parser accepts quotes and other Python-significant characters. That is a real
reason to encode the value at the generated-Python sink and a reasonable place
to add domain validation.

**Required action:** Define the actual trust boundaries. If
`workflow_dispatch` inputs are in scope, move expressions into step `env:`
entries and reference the environment variables from quoted shell arguments
instead of substituting expressions into `run:`. Validate versions and target
families at their ingress points. If dispatch users are explicitly trusted,
narrow the security claim accordingly and document the artifact-name path that
is actually being fixed.

Validation and output encoding solve different problems. A shared
`validate_package_version()` / `validate_target_family()` helper is useful;
validation is not a replacement for `repr()`/`!r` when a string is rendered as
Python source.

### 4. IMPORTANT: Keep one source of truth for generated and in-memory state

The PR first renders configuration into `dist_info_contents`, then
[`exec()`s only the template and manually repeats every mutation](https://github.com/ROCm/TheRock/blob/4faef7ab4ea973137d15ceaab71d2e2a2dd8b324/build_tools/_therock_utils/py_packaging.py#L171-L190).
Every future dist-info field must now be added in two places with identical
semantics. The unrelated `version_suffix` regression already demonstrates how
easy it is for this area to acquire behavior beyond quoting.

Once values are rendered with Python-literal encoding, executing the one
generated source string is safe for this injection class and guarantees that
the build-time view matches the file shipped to `setup.py`. If policy requires
the in-memory path never to execute generated values, model the configuration
once (for example, a small dataclass) and use dedicated render/apply helpers
from that object. In either design, add a parity test comparing all configured
fields in `params.dist_info` with a module loaded from
`params.dist_info_contents`.

**Recommendation:** Remove the duplicated initialization or centralize it
behind a single configuration object plus renderer/applier. A generic helper
named `sanitize` would obscure the context; the helper should make clear
whether it validates a domain value or renders a Python literal.

---

## Security Reproduction

I used a harmless `builtins.PR6813_INJECTED` sentinel with this suffix:

```python
"'\n__import__('builtins').PR6813_INJECTED = True\n#"
```

Commands:

```powershell
D:\projects\TheRock\.venv\Scripts\python.exe D:\scratch\codex\pr6813_experiment.py D:\scratch\codex\pr6813-test-quality\build_tools
D:\projects\TheRock\.venv\Scripts\python.exe D:\scratch\codex\pr6813_experiment.py D:\scratch\codex\pr6813-4faef7a-review\build_tools
```

Output:

```text
BASE
injected=True
stored=False

PR_HEAD
injected=False
stored=True
```

This confirms both points: the original Python injection is real, and
`repr()`-based literal encoding neutralizes it.

---

## CI and Verification Evidence

### Local verification

Exact PR head:

```powershell
D:\projects\TheRock\.venv\Scripts\python.exe -m pytest tests\py_packaging_test.py -q
```

```text
..............................................................           [100%]
62 passed in 0.88s
```

As shown above, the same 62 tests pass when the production source is reverted
to the vulnerable base revision, so this result does not validate the fix.

### GitHub Actions

At head `4faef7ab...`, the check-run snapshot contained 84 successful, 14
skipped, and 2 failed checks.

- Ubuntu and Windows unit-test jobs passed.
- The Linux multi-arch Python package build, upload, and related steps passed.
- The Windows Python package job was skipped after an earlier Windows
  gfx110X math-libs stage failed.
- The two failures are that math-libs job and the aggregate CI Summary. They do
  not exercise either changed Python file and appear unrelated, but the failed
  stage still needs retry or triage before merge.

GitHub currently reports `mergeable: false` and `mergeable_state: dirty`, so
the branch also needs conflict resolution before re-review.

---

## Required Before Re-review

1. Preserve `__version__ = version`; quote it without appending the nonce.
2. Replace the four isolated `repr()` tests with production-path regression
   tests that fail against the base source.
3. Correct the threat model and either secure the earlier workflow shell
   boundary or explicitly remove it from the claimed attack path.
4. Eliminate or centralize the duplicate dist-info initialization and add a
   generated/runtime parity test.
5. Resolve the merge conflict and rerun the skipped/failed Windows portion.

---

## Conclusion

**Approval Status: CHANGES REQUESTED**

The right conclusion is not that `repr()` is security theater: it is the
appropriate Python-literal encoder here, and it demonstrably blocks the
original injection. The security framing, regression coverage, and duplicated
implementation around it are not yet credible enough to merge.

*Review generated with Codex (OpenAI).*
