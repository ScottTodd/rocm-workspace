# Working with worktrees

Git worktrees let us develop on several branches without changing the checkout
used by a running build. Each worktree has its own files, index, and checked-out
branch. Branches, remotes, and Git objects are shared across the repository.

## Location and naming

Use this layout for new TheRock worktrees:

```text
D:/scratch/codex/TheRock-worktrees/<short-description>
users/scotttodd/<short-description>
```

For example, `TheRock-worktrees/zizmor-github-app` holds branch
`users/scotttodd/zizmor-github-app`. Keep names descriptive and use the same
suffix for the directory and branch. Existing worktrees can stay where they
are; `git worktree list` remains the complete inventory.

## Create a worktree

These examples use PowerShell. First inspect the repository and fetch the base:

```powershell
git -C D:/projects/TheRock worktree list
git -C D:/projects/TheRock status --short
git -C D:/projects/TheRock branch --list 'users/scotttodd/zizmor-github-app'
git -C D:/projects/TheRock fetch origin main
git -C D:/projects/TheRock rev-parse origin/main
```

Record that base SHA in the work notes. Fetching updates the remote-tracking
reference without switching the main checkout or changing its files. If the
user specifies another base, use that instead.

Check that the destination does not already exist, then create the worktree:

```powershell
Test-Path D:/scratch/codex/TheRock-worktrees/zizmor-github-app
New-Item -ItemType Directory -Force D:/scratch/codex/TheRock-worktrees
git -C D:/projects/TheRock worktree add `
  -b users/scotttodd/zizmor-github-app `
  D:/scratch/codex/TheRock-worktrees/zizmor-github-app origin/main
git -C D:/scratch/codex/TheRock-worktrees/zizmor-github-app status --short --branch
```

If the branch already exists, inspect it and attach it with `git worktree add
<path> <branch>` instead of creating or resetting it. Git normally permits a
branch to be checked out in only one worktree; use the existing worktree if it
is already attached.

## Editors, Git clients, and checks

Open the worktree directory as a folder in your editor. A separate editor
window for each branch makes it easier to see which files you are editing.
Git clients share the branch list across worktrees, but support for displaying
several working directories varies. Register each worktree as a repository
folder if needed. The common parent directory makes those folders easy to find.

Run commands with the worktree as the working directory, or use `git -C` with
its path. Check `git status --short --branch` before editing or committing.
Read the target repository's agent instructions and style guides.

Worktrees do not copy ignored build directories or virtual environments.
For TheRock Python checks, use `D:/projects/TheRock/.venv/Scripts/python.exe`
explicitly, running from the new worktree's `build_tools` directory so tests
exercise the changed source. Keep pytest caches under
`D:/scratch/codex/pytest-cache`, as described in AGENTS.md. If dependency changes
require another environment, create a separate one instead of modifying the
environment used by other work.

Do not reuse the main checkout's CMake build tree. Workflow and documentation
edits usually need no submodule initialization or source build. Initialize only
the submodules required by the task; worktrees containing initialized submodules
have additional Git limitations for moving and removing them.

## Split a change set into reviewable branches

1. Agree on the groups and whether they are independent or stacked. Record the
   branch names, paths, base SHA, and files or changes assigned to each group.
2. Preserve the original combined worktree. Do not reset it while distributing
   changes. Include untracked files in the inventory; ordinary diffs omit them.
3. Create independent branches from the same recorded base SHA. For a dependent
   branch, use its prerequisite branch's commit as the base and document that
   dependency for review.
4. Transfer only the intended changes. Whole-file copies work when every change
   in a file belongs to one group and the bases match. Use selected patches or
   careful edits when a file contains changes for several groups. Check patches
   with `git apply --check` before applying them.
5. Compare each branch with its base and run the relevant checks from that
   worktree. Verify that shared edits are accounted for without accidentally
   bringing unrelated changes into a branch. Compare the combined result with
   the original change set before discarding that reference.
6. Leave changes unstaged for review until committing is authorized. Prepare
   messages and finish checks before batching signed commits, so the user can
   handle hardware signing together. If signing fails, retain the staged changes
   and report the failure; never retry without signing.

After committing, provide the branch-to-commit mapping. Push only with explicit
authorization. Worktrees do not change the usual rules for amending commits or
publishing branches.

## Cleanup after merge

Cleanup is a separate, requested operation. Start by listing worktrees and
fetching `origin/main`. For each candidate, check:

- The associated PR is merged, and no later local or remote commits still need
  review. A closed PR alone is not evidence that its changes landed.
- `git status --short --untracked-files=all` is clean. Also inspect ignored files
  with `git status --short --ignored`; build outputs and local notes may matter.
- No build, editor task, or other process still uses the directory.
- The resolved absolute path is the intended worktree, not the main checkout or
  a parent directory. Existing worktrees outside the new root need the same check.

`git branch --merged origin/main` is useful for ancestry-based merges, but squash
and rebase merges can leave the original commits outside `main`'s history. Check
the merged PR and resulting changes in those cases rather than treating every
unlisted branch as unfinished or safe to delete.

After verifying the candidate and obtaining cleanup authorization:

```powershell
git -C D:/projects/TheRock worktree remove D:/scratch/codex/TheRock-worktrees/zizmor-github-app
git -C D:/projects/TheRock branch -d users/scotttodd/zizmor-github-app
git -C D:/projects/TheRock worktree list
```

Removing a worktree does not delete its branch. Prefer normal removal and
`branch -d`; if either refuses, investigate instead of automatically forcing it.
A squash-merged branch may need `branch -D`, but only after verifying that its
changes landed and deletion is authorized. Remote branch deletion is separate.

Use `git worktree prune --dry-run` to inspect stale administrative entries left
by directories removed outside Git. Pruning cleans those entries; it does not
remove existing worktree directories or decide which branches have merged.
Prefer `git worktree remove` over deleting directories manually.

## Permissions

Creating worktrees writes both the destination directory and the repository's
shared Git metadata. Writable access to the scratch root alone may not be enough.
Permission rules should narrowly allow routine fetch and worktree creation for
the intended repository and destination. They should preserve explicit
authorization for pushing and cleanup, and preserve commit signing.

AGENTS.md records development conventions; it does not grant sandbox access.
Permission configuration is managed separately.

---

Generated with Codex
