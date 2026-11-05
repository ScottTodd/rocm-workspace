# Minimal release cherry-pick draft

This is a reviewable example, not an installed workflow. Copy the YAML to
`.github/workflows/cherry-pick-to-release.yml` and the Bash/Python files to
`build_tools/automation/` when integrating it. The workflow should be dispatched
from `main`; `release_branch` selects the destination independently.

Configure `AUTOMATION_RUNNER` as a Linux runner label with Git, Bash, gh, and the
usual Git mirrors. Set `THEROCK_GIT_MIRROR_DIR` in the runner service environment,
as documented in TheRock's `docs/development/git_mirror_setup.md`. Mirrors are
reused by `fetch_sources.py`; they are not created on every dispatch. TheRock's
own source uses the top-level checkout. The App secrets are the existing
systems/libraries secrets, and their installations need the requested permissions.

The workflow routes inputs and credentials. Bash runs the existing checkout
script and ordinary Git/gh commands. Python validates request syntax and formats
the PR description, including upstream explanations and explicit source links.
Git's native failure handling stops the script on conflicts, empty picks, and
unsupported merge picks. Nothing is pushed until every pick succeeds.

The draft preserves original messages with standard `cherry-pick -x` provenance;
the JIRA key goes in the PR body. It deliberately does not reproduce the proposed
custom commit-message prefix or ticket-derived branch names. Run ID and attempt
identify the destination, allowing separate batches for the same ticket. An API
failure after push leaves the branch available for inspection/manual PR creation;
the summary prints its name before calling `gh pr create`.

`--dvc-projects disabled` selects no matching project and avoids binary payload
downloads (the current argument parser requires a nonempty list). The include
flags select the requested component; branch-configured source sets remain
additive, so verify those if changing the workflow checkout from `main`.
Allowing an empty `--dvc-projects` list in the shared parser would remove the
sentinel and its missing-config warning; that small cleanup is not implemented
by this draft.

Before landing, add CODEOWNERS for the scripts and workflow, skip ROCm build CI
for the automation subtree, and keep its checks in unit/lint/security workflows.
No changes to the shared checkout implementation are proposed here.

The Bash script uses `set -euxo pipefail`: expanded commands are logged as they
run, in addition to Git/gh diagnostics. `fetch_sources.py` already logs its own
commands and mirror selection. Tokens remain in `GH_TOKEN`, which is read by gh;
the script never expands the token into command arguments. The PR title appears
in the command trace, while the full PR body is written to the job summary.
Successful ancestry checks produce no native output, but their commands appear
in the trace. Conflicts retain Git's normal paths and diagnostics.

Validation: Bash syntax and Python/YAML parsing passed. Local smoke runs passed
for dry-run, publication to a disposable local remote, and a conflict that
publishes nothing. The GitHub CLI was stubbed, so no GitHub writes occurred.
Checked the actual `fetch_sources.py` argument parser/source selection without
fetching: the draft's libraries flags select only `rocm-libraries` in the current
checkout. Mirror-backed network checkout, runner integration, and real App/PR
publication have not been exercised for this draft. With tracing enabled, the
one-commit local smoke examples logged 29 lines for dry-run, 35 for publication,
and 30 for a conflict; component fetching adds its own output. The test token
was absent from the logs. Latest smoke logs and generated PR text are under
`D:/scratch/codex/cherry-pick-draft-smoke-29c13d63`.

Generated with Codex
