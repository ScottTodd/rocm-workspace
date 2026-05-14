# ROCm Build Infrastructure Workspace

## Overview

This workspace is for build infrastructure work on ROCm via the
[ROCm/TheRock](https://github.com/ROCm/TheRock) repository and related projects.
It is a meta-workspace: the actual source and build directories live in sibling
repositories and build trees, while this repository holds shared agent context,
review workflows, notes, and helper scripts.

## Agent Entry Points

`AGENTS.md` is the canonical shared instruction file for coding agents.
`CLAUDE.md` is kept as a Claude Code compatibility symlink to this file.

Tool-specific files are intentionally separate:

- `.claude/` contains Claude Code commands, agents, settings, and output styles.
- `.agents/skills/review-pr/` and `.agents/skills/review-branch/` contain
  Codex-readable review workflow instructions.
- `scripts/claude.bat` and `scripts/codex.bat` launch each client with the
  workspace Python environment activated.

If the user asks for a code review in natural language, follow the Review
Workflow section below even when a tool-specific slash command is not available.

## Working Environment

See `directory-map.md` for local directory locations.

Important conventions:

- This meta-workspace directory is `D:/projects/rocm-workspace`.
- The main TheRock checkout is usually `D:/projects/TheRock`.
- Use relative paths when editing sibling repositories from this workspace.
  Example: edit `../TheRock/docs/development/README.md`, not an absolute path,
  unless a tool explicitly requires an absolute path.
- Do not assume all directories under `directory-map.md` exist on every machine.
  Check before using them.

## Project Context

ROCm is AMD's open-source GPU compute platform. TheRock is the super-project
used to build and package ROCm components across multiple repositories and
submodules.

Build infrastructure work commonly involves:

- CMake build system configuration
- CI/CD pipeline maintenance
- Build dependency management
- Cross-platform build support
- Build performance optimization
- Package generation and distribution

TheRock is a super-project. Submodules such as `rocm-systems` and
`rocm-libraries` are sub-projects. When dependency management or build ordering
is in question, prefer the super-project build rules. For example, ROCR-Runtime
and clr relationships are governed from `core/CMakeLists.txt` and documented in
`docs/development/build_system.md`.

## Common Tasks

### Building

Builds typically happen in separate build trees. Out-of-tree builds are standard
practice, and full builds can be very expensive. Prefer task-specific
configuration and incremental builds over broad rebuilds unless the user asks
for a full build.

For build-infra iteration when C++ debugging is not expected:

```bash
cmake -B /develop/therock-build -S /develop/therock -GNinja -DTHEROCK_AMDGPU_FAMILIES=gfx1201 \
  -DCMAKE_C_COMPILER_LAUNCHER=ccache \
  -DCMAKE_CXX_COMPILER_LAUNCHER=ccache
```

Then build only what is needed. A full `ninja` can be very time consuming:

```bash
cd /develop/therock-build && ninja
```

For specific ROCm components, configure the appropriate `THEROCK_ENABLE_*`
subset as described in TheRock's README, then iterate on named project targets:

```bash
cd /develop/therock-build
ninja clr+expunge && ninja clr+dist
```

When configuration details are unclear, ask for task-specific build instructions
before starting a long-running configure or build.

### Source Navigation

- Source code is spread across multiple repositories and worktrees.
- Git submodules are used extensively.
- When editing build configuration, check both source CMake files and build-tree
  caches when relevant.

### Testing

- Unit tests, integration tests, and packaging tests may all be relevant.
- Tests may run on different GPU architectures such as `gfx906`, `gfx908`,
  `gfx90a`, `gfx110X`, `gfx120X`, and `gfx94X`.
- Prefer targeted tests that validate the changed behavior before broader test
  runs.

## Playbook

Default scratch directory: `D:/scratch/rocm-workspace`. Historical notes and
old local artifacts may still use `D:/scratch/claude`; treat that path as a
legacy scratch location, not as a Claude-only convention.

### Download CI Artifacts Without Extracting

```bash
# 1. Find the latest successful run for an artifact group
cd /d/projects/TheRock/build_tools && python find_latest_artifacts.py \
  --artifact-group gfx110X-all -v

# 2. Download archives to scratch; use the run-id from step 1
cd /d/projects/TheRock/build_tools && python fetch_artifacts.py \
  --run-id=<RUN_ID> \
  --artifact-group=gfx110X-all \
  --output-dir=/d/scratch/rocm-workspace/artifacts/<RUN_ID> \
  --no-extract
```

Common artifact groups: `gfx110X-all`, `gfx120X-all`, `gfx94X-all`.

### Download a Subset of CI Artifacts and Test Locally

This is useful for validating review feedback without rebuilding. Positional
arguments to `fetch_artifacts.py` are prefix-matched include filters.

```bash
# 1. Download only the artifacts you need.
#    --flatten merges artifacts into an install-prefix-like layout.
cd /d/projects/TheRock/build_tools && python fetch_artifacts.py \
  --run-id=<RUN_ID> \
  --artifact-group=gfx110X-all \
  --output-dir=/d/scratch/rocm-workspace/artifacts/<LABEL> \
  --flatten \
  "core-ocl_test" "core-ocl_run" "core-ocl_lib" "base_run" "base_lib"

# 2. Explore the layout.
ls /d/scratch/rocm-workspace/artifacts/<LABEL>/bin/
ls /d/scratch/rocm-workspace/artifacts/<LABEL>/tests/

# 3. Rearrange files to test a hypothesis.
cp /d/scratch/rocm-workspace/artifacts/<LABEL>/tests/ocltst/* \
   /d/scratch/rocm-workspace/artifacts/<LABEL>/bin/

# 4. Run from the rearranged layout.
cd /d/scratch/rocm-workspace/artifacts/<LABEL>/bin && ./ocltst.exe -m oclruntime.dll
```

Notes:

- `--flatten` strips the `<subproject>/stage/` prefix and merges all artifacts
  into one tree that resembles a normal install prefix.
- PR branch artifacts stay in S3 after GitHub artifact expiry. Use the run ID
  from `gh pr checks <URL>` or `gh api repos/.../actions/runs`.
- Always test with the ROCm-built libraries, not system-installed ones.
- Artifacts built at one driver version may not work on a machine with a
  different driver version.

### Inspect an Artifact Archive Without Extracting

```bash
python -c "
from _therock_utils.archive_util import open_archive_for_read
from pathlib import Path
with open_archive_for_read(Path('<archive.tar.zst>')) as tf:
    for m in tf:
        print(m.name)
"
```

## Conventions And Gotchas

### Coding Standards

Follow the style guides in `../TheRock/docs/development/style_guides/`:

| Guide | Use For |
|-------|---------|
| `python_style_guide.md` | Python code |
| `cmake_style_guide.md` | CMake build configuration |
| `bash_style_guide.md` | Shell scripts |
| `github_actions_style_guide.md` | CI/CD workflows |

Key principles across languages:

- Fail fast: never silently continue on errors.
- Prefer explicit code over implicit behavior.
- Validate that operations actually succeeded.
- Apply DRY, YAGNI, and KISS pragmatically.

### Shell Command Conventions

The active shell may be PowerShell, Bash, or an agent-specific shell wrapper.
Follow the shell in the environment context and the host tool's permission
model.

For Bash or MSYS2-style tool calls:

- Use paths like `/d/projects/...`, not `D:/projects/...`.
- Prefer `python -m pytest <path>` over bare `pytest`.
- Use `pre-commit run` rather than `python -m pre_commit`.
- Prefer separate tool calls over long `&&` chains when permissions are
  command-pattern based.
- Copy files from restricted or external locations into an approved scratch
  directory before processing them.

For Git operations in sibling repositories, prefer `git -C <path>`:

```bash
git -C /d/projects/TheRock status --short
git -C /d/projects/TheRock log --oneline -10
```

### Git Workflow

Branch names should use:

```text
users/<username>/<short-description>
```

Examples:

- `users/scotttodd/add-simde-third-party`
- `users/scotttodd/fix-cmake-detection`

Commit guidance:

- First line: concise summary, roughly 50-72 characters.
- Follow with a blank line and explanatory body when useful.
- Include testing and verification notes when they matter.
- Do not include issue references such as `Fixes #123` unless the user asks.
- Do not include PR references such as `#123`; PR metadata belongs in PR text.
- Do not add tool-specific AI footers unless the user asks for them or the
  repository policy requires them.
- Never retry a failed signed commit with `--no-gpg-sign`; the user uses a
  hardware signing device.
- Never push without explicit authorization.
- Do not amend commits without explicit authorization.

## Review Workflow

Code reviews happen at two levels: comprehensive reviews and focused reviews.

Natural-language triggers include:

```text
Review this PR: https://github.com/ROCm/TheRock/pull/2761
Review PR https://github.com/ROCm/TheRock/pull/2761
Can you review https://github.com/ROCm/TheRock/pull/2761
Review my current branch
Do a style review of my changes
Run tests and security reviews in parallel
```

Tool-specific entry points:

- Claude Code slash commands live in `.claude/commands/`.
- Codex-readable review workflow specs live in `.agents/skills/review-pr/` and
  `.agents/skills/review-branch/`.

Review types:

- `style`: formatting, naming, conventions, readability
- `tests`: test coverage, edge cases, test quality
- `documentation`: docs, comments, help text
- `architecture`: design, module boundaries, maintainability
- `security`: secrets, validation, permissions, injection risks
- `performance`: efficiency, scaling, resource usage
- comprehensive/default: all of the above

Output files:

- PR reviews: `reviews/pr_{REPO}_{NUMBER}.md`
- Focused PR reviews: `reviews/pr_{REPO}_{NUMBER}_{TYPE}.md`
- Branch reviews: `reviews/local_{COUNTER}_{branch-name}.md`
- Focused branch reviews:
  `reviews/local_{COUNTER}_{branch-name}_{TYPE}.md`

Severity levels:

- `BLOCKING`: must fix before approval.
- `IMPORTANT`: should fix before human review or before merge.
- `SUGGESTION`: optional improvement.
- `FUTURE WORK`: useful but out of scope for the current change.

When reviewing:

1. Read `reviews/REVIEW_GUIDELINES.md`.
2. Read `reviews/REVIEW_TYPES.md` for focused reviews.
3. Consult the domain-specific files under `reviews/guidelines/` when relevant.
4. Gather CI evidence when available; do not rely only on the diff if CI logs
   can confirm or disprove a concern.
5. Write findings with concrete file/line references, impact, and required
   action or recommendation.
6. Lead the final response with findings, ordered by severity.

For PR reviews, use `gh pr view`, `gh pr diff`, and `gh pr checks` when
available. For local branch reviews, compare against `main` or `upstream/main`
as appropriate and scan existing `reviews/local_*.md` files to choose the next
counter.

### Inline Review Markers

For quick iteration, comments may use:

| Marker | Meaning |
|--------|---------|
| `RVW:` | Discuss first; propose a fix and wait for confirmation |
| `RVWY:` | Make the fix directly |

When asked to process review comments, search for these markers and handle them
according to the table.

### Documenting Experiments

When running local experiments, especially with downloaded CI artifacts, include
the full command and output in review files or notes. If logs are too large,
save them to a local scratch file so they can be shared later.

## Task Tracking

This repository is moving toward [Beads](https://github.com/gastownhall/beads)
for task tracking.

When Beads is available in the environment:

- Run `bd prime` at the start of task-oriented work for workflow context.
- Use `bd ready` to find unblocked work.
- Use `bd show <id>` to inspect an issue.
- Use `bd update <id> --claim` before taking ownership.
- Use `bd close <id>` when work is complete.
- Use `bd remember "insight"` for durable project memory.

Do not initialize Beads, run `bd setup`, or migrate existing markdown tasks
unless the user asks. Until Beads is initialized, `tasks/active/` and
`tasks/completed/` remain legacy workspace context.

## Reference

- [ROCm Documentation](https://rocm.docs.amd.com/)
- [TheRock repository](https://github.com/ROCm/TheRock)
- [Beads repository](https://github.com/gastownhall/beads)

## Standing User Preferences

- Do not be sycophantic. Push back when reasoning seems unsound, then respect
  the user's decision.
- Do not describe work as "production" code or use shaky progress metrics.
- Before committing to `rocm-kpack`, run `pre-commit`.
- When writing design docs, include an "Alternatives Considered" section that
  covers major rejected architectural options.
