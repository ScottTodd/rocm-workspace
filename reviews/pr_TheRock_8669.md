# Review: Windows MSI install tests

- PR: https://github.com/ROCm/TheRock/pull/8669
- Reviewed head: `3843b461f373d35a6f32effabebc05158a59fa4b`
- Reviewed: 2026-10-02
- Scope: correctness, GitHub Actions style/security, local iteration, test design and Linux precedent.
- Overall assessment: **CHANGES REQUESTED**.

## Findings

### 1. BLOCKING: Uninstall selects a product without validating the requested version

[Product lookup](https://github.com/ROCm/TheRock/blob/3843b461f373d35a6f32effabebc05158a59fa4b/build_tools/packaging/windows/native_windows_package_uninstall_test.py#L50) selects the first matching DisplayName; [the caller](https://github.com/ROCm/TheRock/blob/3843b461f373d35a6f32effabebc05158a59fa4b/build_tools/packaging/windows/native_windows_package_uninstall_test.py#L169) does not pass the requested version or install path. The generator uses the same product name across releases.

On a developer machine with runtime 10.1 installed, running uninstall with `--rocm-version 10.2.0` removes 10.1. The subsequent checks inspect only the 10.2 directory and registry key, so they can report success when those never existed. This is both a misleading test and an unintended removal of another installation. Multiple matching registrations are also resolved by enumeration order.

**Required action:** Identify the exact installed MSI ProductCode from the package under test, or validate the installed version and location before removal. Reject missing/mismatched/ambiguous identities before invoking msiexec. Verify removal of that product registration afterward. A focused regression test for version mismatch is substantially more valuable than the existing name-only mock.

### 2. BLOCKING: The payload test does not establish that each selected package installed its payload

[Payload verification](https://github.com/ROCm/TheRock/blob/3843b461f373d35a6f32effabebc05158a59fa4b/build_tools/packaging/windows/native_windows_package_install_test.py#L219) uses the same four runtime DLL globs for every package; `package` only affects messages. [The runner](https://github.com/ROCm/TheRock/blob/3843b461f373d35a6f32effabebc05158a59fa4b/build_tools/packaging/windows/native_windows_package_install_test.py#L338) installs all requested MSIs before checking any of them. Runtime and core use [the same versioned directory](https://github.com/ROCm/TheRock/blob/3843b461f373d35a6f32effabebc05158a59fa4b/build_tools/packaging/windows/generate_msi_wxs.py#L113).

Consequences:

- With `runtime,core`, files installed by runtime can satisfy core's entire payload check. Core-specific omissions (OpenCL, AMDsmi, and the other declared core artifacts) are not checked.
- Recursive globbing accepts the right filename anywhere, including an unusable directory layout.
- It does not require matches to be files. A directory named `amdhip64_7.dll` passes. I reproduced a pass for both package names with four directories and no DLL files.
- Core's artifact selection does not include runtime's explicit amd-llvm/comgr selection; nevertheless the generic verifier requires amd_comgr.dll. Standalone core needs its actual contract established rather than assuming runtime's file list.

**Required action:** Define a small, package-specific set of expected files at their intended installed paths and require regular files. Validate standalone packages independently; test co-installation as a separate scenario, including verification of the surviving package after removing the other. Do not require a broad GPU test suite to fix these basic false positives.

### 3. IMPORTANT: Registry verification accepts a wrong installation location

[InstallDir validation](https://github.com/ROCm/TheRock/blob/3843b461f373d35a6f32effabebc05158a59fa4b/build_tools/packaging/windows/native_windows_package_install_test.py#L249) checks only that the registry value is a nonempty string. An unrelated nonexistent path passes; I reproduced this with `Z:\\nonexistent\\wrong-version`.

Applications using this registry value to discover ROCm would fail while CI stays green. The disk check separately computes its own expected path, so it does not validate the relationship.

**Recommendation:** Compare the registry value with the expected installation directory using Windows path normalization, including trailing separators/case, and verify that target exists. Cover incorrect values, not just missing keys.

### 4. IMPORTANT: Downloading and testing remain coupled, and diagnostics are deleted

[The runner](https://github.com/ROCm/TheRock/blob/3843b461f373d35a6f32effabebc05158a59fa4b/build_tools/packaging/windows/native_windows_package_install_test.py#L329) downloads into a TemporaryDirectory and removes both MSIs and verbose installer logs on exit, including failure. The uninstall runner does the same for logs. Only the last 40 lines are printed for nonzero installer exits; verification failures and timeouts do not preserve a full installer log.

There **is** an offline `--msi-dir` path. Therefore it would be inaccurate to say local reruns always redownload. But the download mode cannot populate a reusable directory, and there is no download-only CLI. Offline use still requires a dummy `--artifact-run-id local`. Each pytest entry performs the entire install or uninstall sequence, so individual verification checks cannot be selected and rerun against an existing installation.

**Recommendation:** Separate acquisition from testing:

1. Download to an explicit persistent directory using a small downloader or suitable shared acquisition utility.
2. Run install tests against that directory without run-ID/release inputs.
3. Make verification independently runnable against the installed prefix.
4. Run explicit uninstall/teardown tests.
5. Retain full logs under a user-selected work directory and upload them on CI failure.

The workflow location is consistent with Linux, and the Windows scripts belong near the Windows packaging code. Moving files is less important than separating these responsibilities. A small common module is clearer than making uninstall import private helpers from the install test; remove uninstall's unused artifact/release CLI options accepted merely for symmetry.

### 5. IMPORTANT: Reusable workflow and CLI defaults disagree with the MSI producer

The [test's workflow_call default](https://github.com/ROCm/TheRock/blob/3843b461f373d35a6f32effabebc05158a59fa4b/.github/workflows/test_native_windows_packages_install.yml#L62) is `nightly`, whereas its dispatch default is `ci`. The [MSI producer](https://github.com/ROCm/TheRock/blob/3843b461f373d35a6f32effabebc05158a59fa4b/.github/workflows/multi_arch_build_native_windows_packages.yml#L57) defaults to `ci` for reusable calls too. The test CLI also defaults to nightly and disables run metadata lookup.

A caller connecting producer and consumer with their defaults will upload to the CI bucket and then attempt to download from the nightly bucket. The successful dispatch explicitly used ci and does not exercise this mismatch.

**Recommendation:** Use matching defaults, or require explicit consistent release-type propagation. Keep a safe ci dispatch default. If “arbitrary build run” includes nightly/BKC packages, document/support those sources deliberately; the dispatch choice currently exposes only ci/dev.

### 6. BLOCKING (test-quality guideline): Trim implementation-mirroring unit tests

The [mocked URL resolver test](https://github.com/ROCm/TheRock/blob/3843b461f373d35a6f32effabebc05158a59fa4b/build_tools/packaging/windows/tests/native_windows_package_install_ut_test.py#L75) replaces the resolver with a fake object, then checks its preset return and exact calls. It cannot establish correct bucket/run-path resolution. The [System32 happy-path test](https://github.com/ROCm/TheRock/blob/3843b461f373d35a6f32effabebc05158a59fa4b/build_tools/packaging/windows/tests/native_windows_package_install_ut_test.py#L190) creates files from the same generator list the verifier reads; clearing that declaration can make both implementation and test silently do nothing.

These are concrete examples of call-contract/change-detector coverage rather than evidence that the MSI installs correctly. Replace the resolver mock with representative actual URL-resolution results where that logic merits testing, and maintain an independent package contract for essential installed content. Remove trivial helper coverage that adds no distinct failure scenario. This does **not** mean all harness unit tests should be deleted: fail-closed identity selection, rejection of malformed payloads, and preservation of preexisting machine state are worthwhile behavior tests.

## Answers to the requested design questions

### Did Linux already add tests for its tests?

**Yes.** The reviewed tree contains both [native_linux_package_install_ut_test.py](https://github.com/ROCm/TheRock/blob/3843b461f373d35a6f32effabebc05158a59fa4b/build_tools/packaging/linux/tests/native_linux_package_install_ut_test.py#L1) and [native_linux_package_uninstall_ut_test.py](https://github.com/ROCm/TheRock/blob/3843b461f373d35a6f32effabebc05158a59fa4b/build_tools/packaging/linux/tests/native_linux_package_uninstall_ut_test.py#L1). They also use imports-by-path, mocked commands, and environment-to-argument glue. The Windows approach is following that precedent.

Testing a substantial installation harness is reasonable when it has consequential selection, parsing, or cleanup logic. Testing every thin assertion wrapper is unnecessary. Linux itself includes weak examples; copying them does not strengthen the Windows design. Linux also has more substantive harness behavior, including package-manager differences and [installed-file security and ELF RPATH checks](https://github.com/ROCm/TheRock/blob/3843b461f373d35a6f32effabebc05158a59fa4b/build_tools/packaging/linux/native_linux_package_install_test.py#L830). Its rocminfo attempt is warning-only on failure, so it should not be described as a strict runtime smoke-test guarantee.

### GitHub Actions style and security

- **SUGGESTION:** Remove `set -euo pipefail` from the two single-command steps. Explicit `shell: bash` already uses `bash --noprofile --norc -eo pipefail {0}`, confirmed in the live log and [GitHub's documentation](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax#jobsjob_idstepsshell). GitHub does not supply `-u`, but these steps have no shell-variable expansions to benefit from it. This is redundant setup, not a security defect.
- Inputs are passed through environment variables rather than interpolated into shell source. Python invokes msiexec with argument lists. Actions are SHA-pinned, checkout does not persist credentials, permissions are contents:read, and execution is on a GitHub-hosted Windows runner without AWS credentials. I found no concrete shell-injection or excessive-token-permission issue in the new workflow.
- Do not add AWS credentials just to download public MSIs. Remote MSI installation is intentional here; retaining the disposable runner boundary matters.
- **SUGGESTION:** Make Python dependencies explicit and minimal. The current broad build requirements do bring pytest transitively through pytest-cmake, so this is not a missing-dependency bug. In the linked run dependency installation took about 64 seconds, versus 15 seconds for install/verification and 1 second for uninstall.
- A failed install/verification step skips the uninstall step because of the implicit success condition. On a disposable hosted runner this is not a persistent runner contamination bug. A local lifecycle needs explicit failure cleanup/retention behavior; blindly adding `always()` does not fix product identity or partial-install handling.

### What do the tests catch, and what is missing?

| Current check | Useful failure detected | Important limit |
|---|---|---|
| Download and msiexec status | Missing MSI, installer error | Every nonzero code is treated as failure; see reboot policy below |
| Nonempty install directory | Completely absent/empty installation | Old files or an empty child directory can satisfy it |
| Runtime DLL globs | Missing named runtime payload on a clean machine | No correct-path, binary, dependency-load, or package ownership guarantee |
| System32 existence | Missing compatibility DLL on a clean machine | Preexisting DLLs can hide failed installation; no version/content check |
| Registry key/value | Missing installation registration marker | Wrong nonempty InstallDir passes |
| Uninstall directory/key checks | Leftover package files/marker | Wrong product can be removed; machine PATH, product registration, and shared state are unverified |

Prioritize package-specific placement, correct registry target, and machine PATH addition/removal. The generator explicitly modifies PATH; the tests never check it. Capture machine state before install and check preservation afterward, including LongPathsEnabled and preexisting/shared System32 content. “Shared files may remain” is a reason to make assertions state-aware, not omit all teardown assertions.

Then cover repair/reinstall, upgrade/downgrade policy, optional `LEGACY_INSTALL`/`ENABLE_LONG_PATHS` features, custom INSTALLFOLDER, and co-install/uninstall interactions as separate scenarios. Full GPU execution can remain follow-up scope. A narrowly chosen driver-independent loader check could add value, provided it verifies which installed DLL was loaded rather than picking up a system copy.

**IMPORTANT:** Define reboot handling: [install status handling](https://github.com/ROCm/TheRock/blob/3843b461f373d35a6f32effabebc05158a59fa4b/build_tools/packaging/windows/native_windows_package_install_test.py#L177) and the uninstall equivalent classify 3010 as an installer failure. [Microsoft documents 3010 as success requiring reboot](https://learn.microsoft.com/en-us/windows/win32/msi/error-codes). Either make “no reboot required” an explicit test contract with an accurate diagnostic, or report reboot-required separately and avoid claiming immediate verification is conclusive.

## Evidence and limitations

- Read all five changed files and the relevant generator, workflow-output resolver, producer workflow, Linux scripts/tests, and workflow.
- Inspected all PR checks. At the recorded snapshot, Linux and Windows unit-test jobs passed; other checks were still queued/running. The Windows unit log confirms the new harness unit tests ran.
- [Linked live Windows run](https://github.com/idass1990/TheRock/actions/runs/36896581592) passed at older head `4cb3e538097dfe5460f7a9658f7325c20ba0667d`: install test 13.87s, uninstall 1.11s, runtime only. It is useful smoke evidence, not coverage of current-head workflow_call, core, or local lifecycle scenarios.
- Inspected the failed [MIOpen job](https://github.com/ROCm/TheRock/actions/runs/37024139631/job/110992641870). It failed StaticFDBSync/8 on a missing gfx110220.HIP.fdb.txt database. That job does not run the new MSI workflow; it is not evidence against this PR's installer checks.
- No native installation/uninstallation was performed on the developer machine. The local probes execute only extracted verification functions, use temporary directories and a mocked registry, and demonstrate the two false positives above.
- Scratch evidence: `D:/scratch/codex/pr8669/`, including exact downloaded sources, checks.json, live.log, unit-windows.log, miopen.log, probe_verifiers.py, and probe-output.txt.

### Local probe command and complete output

Command (working directory `D:/projects/TheRock/build_tools`):

```powershell
D:/projects/TheRock/.venv/Scripts/python.exe D:/scratch/codex/pr8669/probe_verifiers.py
```

```text
[PASS] payload DLLs present under D:\scratch\codex\pr8669\tmpfeyaggt4
[PASS] payload DLLs present under D:\scratch\codex\pr8669\tmpfeyaggt4
CONFIRMED: directories named like DLLs satisfy both package verifiers
[PASS] registry key present: HKLM\Software\AMD\ROCm\runtime\10.2 (InstallDir=Z:\nonexistent\wrong-version)
CONFIRMED: an unrelated nonexistent registry InstallDir passes
```

Generated with Codex.

