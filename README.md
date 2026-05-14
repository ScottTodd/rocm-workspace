# ROCm Workspace

A meta-workspace for work on [ROCm/TheRock](https://github.com/ROCm/TheRock)
and related projects. This repository provides centralized agent context,
review workflows, notes, and helper scripts for AI-assisted development.

## Why a Meta-Workspace?

Build infrastructure work on ROCm involves multiple scattered repositories and
build directories. Rather than making any single ROCm project the workspace,
this separate meta-repository:

- Provides shared context for Codex and Claude Code
- Maps local directory locations in [`directory-map.md`](/directory-map.md)
- Contains review workflows, notes, reports, and helper scripts
- Stays version-controlled without polluting ROCm source repositories

## Directory Structure

```text
rocm-workspace/
|-- AGENTS.md              # Canonical shared agent instructions
|-- CLAUDE.md              # Symlink to AGENTS.md for Claude Code
|-- directory-map.md       # Map of ROCm directories on this system
|
|-- .agents/
|   `-- skills/            # Codex-readable project skills
|       |-- review-pr/
|       `-- review-branch/
|
|-- .codex/                # Codex project configuration
|   `-- config.toml        # Sandbox defaults and writable roots
|
|-- .claude/               # Claude Code configuration
|   |-- commands/          # Slash commands (/task, /review-pr, etc.)
|   |-- agents/            # Claude Code subagents
|   `-- settings.json      # Shared Claude settings
|
|-- tasks/                 # Legacy markdown task tracking
|   |-- active/
|   `-- completed/
|
|-- reviews/               # Code review system and completed reviews
|   |-- README.md
|   |-- REVIEW_GUIDELINES.md
|   |-- REVIEW_TYPES.md
|   |-- guidelines/
|   |-- pr_*.md
|   `-- local_*.md
|
|-- plans/                 # Implementation plans and design docs
|-- reports/               # Audit reports and analyses
`-- scripts/               # Launchers and helper scripts
```

## Agent Instructions

[`AGENTS.md`](/AGENTS.md) is the canonical instruction file. Claude Code reads
[`CLAUDE.md`](/CLAUDE.md), which is kept as a symlink for compatibility.

Tool-specific behavior lives outside the shared instructions:

- Claude slash commands: [`.claude/commands/`](/.claude/commands/)
- Claude subagents: [`.claude/agents/`](/.claude/agents/)
- Codex project config: [`.codex/config.toml`](/.codex/config.toml)
- Codex review skills: [`.agents/skills/`](/.agents/skills/)

## Code Review System

The [`reviews/`](/reviews/) directory contains the review methodology,
checklists, and completed reviews.

Request examples:

```text
Review this PR: https://github.com/ROCm/TheRock/pull/1234
Review my current branch
Do a style review of my changes
Run tests and security reviews in parallel
```

Claude Code can use the slash commands in [`.claude/commands/`](/.claude/commands/):

```bash
/review-pr https://github.com/ROCm/TheRock/pull/1234
/review-branch
/review-branch style tests
```

Codex can use the project skills:

- [`review-pr`](/.agents/skills/review-pr/SKILL.md)
- [`review-branch`](/.agents/skills/review-branch/SKILL.md)

Review output is written under `reviews/` using the naming conventions in
[`reviews/README.md`](/reviews/README.md).

## Task Tracking

The existing [`tasks/`](/tasks/) directory is legacy markdown task context.
This workspace is moving toward [Beads](https://github.com/gastownhall/beads)
for issue and dependency tracking.

Beads is not initialized by this repository yet. Once the `bd` CLI is installed
and the user chooses to initialize it, agents should prefer `bd prime`,
`bd ready`, `bd show`, `bd update --claim`, and `bd close` over creating new
markdown task files.

## Setup

1. Clone this repository.
2. Update [`directory-map.md`](/directory-map.md) with your actual paths.
3. Set up the Python environment.
4. Launch either Claude Code or Codex with the matching script.

### Python Environment

Use task-specific Python environments instead of relying on Codex inheriting an
activated venv.

For TheRock `build_tools` work, the preferred environment is TheRock's own
`.venv`:

```powershell
cd D:\projects\TheRock\build_tools
D:\projects\TheRock\.venv\Scripts\python.exe -m pytest tests\<target>_test.py
```

Launch Claude Code:

```powershell
.\scripts\claude.bat
```

Launch Codex:

```powershell
.\scripts\codex.bat
```

`scripts\codex.bat` does not activate a venv. Codex should run Python tools with
the appropriate venv Python directly, such as
`D:\projects\TheRock\.venv\Scripts\python.exe -m pytest` for TheRock
`build_tools` tests.

`scripts\claude.bat` still activates the workspace `3.12.venv` for Claude Code.

### Codex Sandbox

Codex sandbox defaults are checked in at [`.codex/config.toml`](/.codex/config.toml).
That file keeps Codex in `workspace-write` mode and adds the common sibling
repositories and Codex scratch directory as writable roots:

- `D:/projects/TheRock`
- `D:/projects/rockrel`
- `D:/scratch/codex`

Codex only loads project `.codex/` configuration for trusted projects. If edits
outside `rocm-workspace` are unexpectedly denied, trust this project in Codex
and restart the session so the sandbox is recreated with the project config.
Keep the paths in `.codex/config.toml` aligned with
[`directory-map.md`](/directory-map.md) when moving between machines.

Project-local Codex execution rules live in
[`.codex/rules/default.rules`](/.codex/rules/default.rules). They allow
repo-scoped `git add` and `git commit -m` commands for this workspace and
TheRock after the user asks to commit. They do not allow pushing.

## Adapting For Another Project

1. Replace ROCm-specific content in [`AGENTS.md`](/AGENTS.md).
2. Keep tool-specific config under `.claude/`, `.agents/`, or client-specific
   launch scripts.
3. Update [`directory-map.md`](/directory-map.md).
4. Customize the review guidelines for the project's conventions.
5. Choose a task tracker; this repo is experimenting with Beads.
