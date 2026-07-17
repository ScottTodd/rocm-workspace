# Branch Review: fix-ccache-logging

* **Branch:** `fix-ccache-logging`
* **Base:** `main`
* **Reviewed:** 2026-06-23
* **Commits:** 1 commit (`705f4d23d Fix print/log function usage in setup_ccache.py`)
* **Scope:** Tip commit, focused on the fix for https://github.com/ROCm/TheRock/pull/5141#discussion_r3461300823

---

## Summary

The commit replaces several `print(..., file=sys.stderr)` calls in
`build_tools/setup_ccache.py` with `_log(...)` to address the review comment
that `_log` does not accept a `file=` keyword argument.

**Net changes:** +5/-8 across 1 file.

---

## Overall Assessment

**CHANGES REQUESTED** - The commit fixes the original `_log(file=...)` crash in
one location, but introduces two other runtime regressions in the same script.

**Blocking Issues:**

1. `_log(proc_ccache.stdout, end="")` still passes an unsupported keyword.
2. The shell environment command is now emitted to stderr instead of stdout,
   breaking documented `eval "$(./build_tools/setup_ccache.py)"` usage.

---

## Detailed Review

### 1. `build_tools/setup_ccache.py`

**BLOCKING: `_log(..., end="")` still crashes**

At `build_tools/setup_ccache.py:184`, the new code calls:

```python
_log(proc_ccache.stdout, end="")
```

`_log` is still declared as `def _log(msg: str):`, so this raises the same
class of error as the PR review comment when the `ccache --zero-stats` command
succeeds.

Evidence:

```text
D:/projects/TheRock/.venv/Scripts/python.exe -c "import sys; sys.path.insert(0, r'D:/projects/TheRock/build_tools'); import setup_ccache; setup_ccache._log('zero stats output', end='')"
TypeError: _log() got an unexpected keyword argument 'end'
```

**Required action:** Either keep this as `print(proc_ccache.stdout, end="", file=sys.stderr)`
or extend `_log` deliberately to support `end` and audit all call sites.

**BLOCKING: `CCACHE_CONFIGPATH` setup command moved from stdout to stderr**

At `build_tools/setup_ccache.py:198` and `build_tools/setup_ccache.py:200`, the
commit changes the final shell command from `print(...)` to `_log(...)`.
That makes the generated command part of diagnostic logging instead of stdout.

This breaks documented and tested usage patterns such as:

```bash
eval "$(./build_tools/setup_ccache.py)"
```

and the sanity script at `build_tools/hack/ccache/test_ccache_sanity.sh:14`.
Command substitution captures stdout, not stderr.

Evidence from the current commit:

```text
D:/projects/TheRock/.venv/Scripts/python.exe D:/projects/TheRock/build_tools/setup_ccache.py --dir D:/scratch/codex/setup-ccache-review-705f4d23d --init --no-reset-stats
exit=0
stdout: <empty>
stderr: [setup_ccache] set CCACHE_CONFIGPATH=D:\scratch\codex\setup-ccache-review-705f4d23d\ccache.conf
```

**Required action:** Keep the final environment command on stdout with plain
`print(...)`. Only diagnostic/status messages should go through `_log`.

---

## Testing Performed

* Fetched the linked GitHub review comment via `gh api`.
* Reviewed `git diff main..HEAD` and the current file around the changed lines.
* Ran `setup_ccache.py --init --no-reset-stats` with stdout/stderr redirected
  separately. The command exited 0, stdout was empty, and the environment setup
  command appeared on stderr.
* Called `_log(..., end="")` directly to confirm the remaining unsupported
  keyword argument raises `TypeError`.

---

## Testing Recommendations

Add or update a lightweight test for `setup_ccache.py` that verifies:

1. Diagnostic messages are emitted on stderr.
2. The final `CCACHE_CONFIGPATH` command is the only stdout payload.
3. The reset-stats success path does not pass unsupported arguments to `_log`.

The existing `build_tools/hack/ccache/test_ccache_sanity.sh` is useful for
manual validation, but this regression is narrow enough to cover with a Python
unit test using a temporary directory and a fake successful `ccache` executable
on `PATH`.

---

## Conclusion

**Approval Status: CHANGES REQUESTED**

The direction is right, but the current commit should not be pushed as-is. It
still contains an unsupported `_log` keyword call and breaks the script's stdout
contract for local `eval`/`for /f` usage.
