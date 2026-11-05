# Review: TheRock release cherry-pick automation

Reviewed 2026-11-05. **CHANGES REQUESTED**, principally for the concurrency defect below. Revised after discussion with the user: prefer a small coordinator using the existing selective, mirror-backed `fetch_sources.py` checkout path and ordinary Git operations. The original recommendation to prefer the checkout-free implementation overlooked this existing infrastructure.

- [PR 9637](https://github.com/ROCm/TheRock/pull/9637), reviewed head `2bddfdc1fade291cebba4ffcd6b244d7e36dedf9`.
- [Problem statement, issue 9485](https://github.com/ROCm/TheRock/issues/9485).
- [Release-process documentation, rockrel PR 134](https://github.com/ROCm/rockrel/pull/134).
- [Conventional implementation, PR 9719](https://github.com/ROCm/TheRock/pull/9719), compared head `fbcf2edd443ad50bb79c751c57d6c22a70c60a56`. This comparison is not a separate comprehensive review of 9719.

## Findings

### 1. BLOCKING: Independent BKC requests can cancel each other while pending

[Workflow lines 39–41](https://github.com/ROCm/TheRock/blob/2bddfdc1fade291cebba4ffcd6b244d7e36dedf9/.github/workflows/cherry-pick-to-release.yml#L39-L41) group requests by repository, release branch, and JIRA key. Every ticketless request for the same BKC branch therefore shares one group, even when the requested commits and prospective destination branches are different.

With one run executing, a second request pending, and a third request arriving, the third cancels the second. `cancel-in-progress: false` protects the executing run; it does not preserve pending runs. GitHub documents this default and the available `queue: max` setting in [its concurrency documentation](https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/control-workflow-concurrency).

**Required action:** Prefer removing this concurrency group. Different requests can operate independently, and the create-only push already protects competing publication to the same destination. If serialization is intentional, use a queue that preserves pending requests and explain the reason for serialization. Adding commits to the key alone still leaves repeated identical requests subject to pending replacement.

This applies to both implementations. No workflows were dispatched to demonstrate cancellation; this finding follows from the group expression and documented scheduler semantics.

### 2. IMPORTANT: Historical provenance prevents legitimate reapplication after a revert

[Git helper lines 285–315](https://github.com/ROCm/TheRock/blob/2bddfdc1fade291cebba4ffcd6b244d7e36dedf9/build_tools/git_cherry_pick.py#L285-L315) treats ancestry or any matching historical provenance text as proof that a change remains present. After a successful pick is reverted, the provenance remains in history, so a later request to reapply it fails before Git can calculate the patch result. A different JIRA key does not help.

I reproduced this with the PR's real local-repository fixture: pick a source commit, commit the generated provenance message, revert that commit, and request the original SHA again. The automation rejects it as already cherry-picked; ordinary `git cherry-pick` succeeds and restores the file. The existing [previous-pick test](https://github.com/ROCm/TheRock/blob/2bddfdc1fade291cebba4ffcd6b244d7e36dedf9/build_tools/github_actions/tests/cherry_pick_to_release_test.py#L1128-L1139) goes further: an empty commit merely mentioning the provenance is enough to trigger rejection.

**Recommendation:** Let the calculated tree identify an empty pick, and keep branch publication safety separate. Remove the historical text veto, or make it advisory. Review the ancestry veto for the same reverted-change case. This simplifies the normal path and removes a history scan per requested commit. Add a behavioral regression covering pick → revert → successful reapplication. Both implementations share this policy issue.

### 3. IMPORTANT: Generated PR descriptions provide an inventory but little release rationale

[Coordinator lines 233–258](https://github.com/ROCm/TheRock/blob/2bddfdc1fade291cebba4ffcd6b244d7e36dedf9/build_tools/github_actions/cherry_pick_to_release.py#L233-L258) emits SHA, subject, ticket, and workflow provenance. It discards the available original commit bodies, and the SHAs are inside code spans rather than explicit source links. Multi-commit titles are also generic.

The actual [generated rocm-libraries PR 15152](https://github.com/ROCm/rocm-libraries/pull/15152) confirms this output. It identifies the change but gives no explanation of why it belongs in the release, its risk, or how it was validated. This falls short of the user's requested replacement for manually preparing a meaningful PR description, though the core branch-and-PR automation works.

**Recommendation:** Add explicit source commit links and preserve useful upstream explanation in clearly identified source-context sections. Offer an optional release-reason input, with a sensible generated description when omitted. Distinguish upstream testing from testing of the release pick; do not automatically claim the latter passed. A small input is sufficient; mandatory forms and extra API lookups are unnecessary for the first version.

## Strategy and implementation choice

The workflow satisfies the main mechanical goal: an operator supplies repository, ordered SHAs, release branch, and an optional/required ticket in the web UI; the automation prepares commits, publishes a new branch, and opens the target PR. Centralizing the workflow in TheRock is a reasonable evolution from the issue's original proposal to duplicate it in the component repositories. The documentation correctly explains that TheRock dispatch permission, rather than the operator's personal component write access, is used.

**Prefer the common mirror-backed checkout path, followed by ordinary `git cherry-pick`.** `fetch_sources.py` already supports selective initialization through its source-set and include/exclude arguments, and uses `--reference-dir` or `THEROCK_GIT_MIRROR_DIR` to reuse local Git mirrors. It is unnecessary to design a new selective checkout mechanism or assume that using it means initializing every component. The selected repository can then be switched to the target release branch, picked, pushed, and submitted as a PR by a small coordinator. Use `--no-apply-patches` for this operation; build patches must not become part of a release cherry-pick. Source-set arguments are additive in the current implementation, so select the include/exclude settings with the branch configuration in mind rather than assuming `--source-sets` alone excludes everything else.

The checkout-free implementation has demonstrated acceptable performance. In [the live libraries run](https://github.com/ROCm/TheRock/actions/runs/42072499572/job/127403908126), the script step ran from 17:13:59 to 17:14:17 UTC and opened a real PR. The [systems dry run](https://github.com/ROCm/TheRock/actions/runs/42067844312/job/127386910907) took about ten seconds and reported actual conflicts without publishing. The author's [disk measurements](https://github.com/ROCm/TheRock/pull/9637#issuecomment-6603232176) report roughly 64 MB after one pick versus 17.12 GB for the conventional implementation. Those disk measurements are author-provided, not independently reproduced here. Neither these disk measurements nor the dispatch timing establishes that a separate Git engine is warranted over the existing mirror-backed path.

The checkout-free loop is understandable: use the source parent as the explicit merge base, merge onto the generated target head, reject conflicts/unchanged trees, then create a commit with that head as its sole parent. The source author is preserved and the App is the committer. Using `GIT_ATTR_SOURCE` at each generated head matters; the integration tests exercise target attributes and attributes introduced by an earlier pick.

9719 uses more familiar commands, but its full clone materializes the default branch before checking out the release tree, and its policy/publishing complexity is largely unchanged. It does not solve the findings above. Comparing its 430-line Git helper to 9637's 490-line helper accepts too much shared machinery as necessary. The useful baseline is the existing mirror-backed source acquisition followed by a short sequence of ordinary Git operations. Git already supplies author preservation, conflict handling, and empty-pick detection; disposable checkouts provide isolation. Keep release-specific messages and PR presentation in the coordinator without reconstructing Git's commit machinery.

The remaining integration details are selecting a runner with the configured mirrors, obtaining the release ref and requested commits, and routing commands/token/PR metadata to the selected repository. TheRock itself uses the top-level checkout; component selections use their submodule checkout. The current workflow uses a hosted `ubuntu-26.04` runner, so local mirrors are not supplied merely by calling `fetch_sources.py`: wire this workflow into the standard runner/mirror setup. Fetching sources also starts from the configured submodule revision, so explicitly switch to the requested release ref before picking. These are workflow integration concerns, not a reason to create a second source-acquisition implementation. No same-runner benchmark of this common path against 9637 was performed in this review.

A [minimal replacement draft](../prototypes/cherry-pick-automation/README.md) now illustrates this approach: workflow inputs and App-token routing, a Bash sequence for selective checkout/cherry-pick/push/PR creation, and a small Python helper for request syntax and PR text. It has local smoke coverage with disposable Git repositories and a stubbed GitHub CLI; it is not installed or dispatched.

## Maintainability: keep checks where they establish a real guarantee

Retain input parsing, supported repository/release policy, source eligibility and parent-count checks, conflict/empty-result detection, and the create-only push. The early destination check saves wasted work; the push lease addresses a different race. They are not redundant. Preserve sanitized push diagnostics and the recovery context when PR creation fails after publication. Never automatically delete a successfully pushed branch after an uncertain API outcome.

The current head still contains low-value validation that earlier review comments questioned:

- [Default branch revalidation](https://github.com/ROCm/TheRock/blob/2bddfdc1fade291cebba4ffcd6b244d7e36dedf9/build_tools/github_actions/cherry_pick_to_release.py#L261-L276): a required metadata field check can be concise; running `check-ref-format` on GitHub's returned default branch adds little.
- [Bot response checks](https://github.com/ROCm/TheRock/blob/2bddfdc1fade291cebba4ffcd6b244d7e36dedf9/build_tools/github_actions/cherry_pick_to_release.py#L279-L307): remove the echoed-login comparison and elaborate email/type alternatives. Constructing the standard noreply identity from the known login and returned ID is sufficient.
- [Provenance URL validation](https://github.com/ROCm/TheRock/blob/2bddfdc1fade291cebba4ffcd6b244d7e36dedf9/build_tools/github_actions/cherry_pick_to_release.py#L350-L380) is not authentication. These values are supplied by the workflow or local caller. Requiring them for reporting is a policy choice; validating their shape does not prove their origin.

These are **SUGGESTIONS**, not separate security defects. Avoid replacing the current checks with a new validation framework. Likewise, a `Protocol`, multiple metadata dataclasses, and a fully general Git-helper API do not need expansion without another caller. The helper's `validate_commits` already accepts source-branch and provenance policy, so the PR's claim that it owns only generic Git operations is stronger than the actual boundary. Keep the boundary practical and describe it accurately.

The ticket-only branch name also intentionally permits only one outstanding request per release/ticket and requires inspection on retries. That is documented and acknowledged in the PR discussion, so I have not treated it as an accidental defect. Consider whether subsequent independent batches for one ticket are common before freezing that convention. Existing-branch safety and request identity are separate decisions.

## Code location and CI cost

**Recommended for this PR:** establish `build_tools/automation/` for on-demand repository maintenance and put the coordinator, its private Git helper, and their tests together. A root `automation/` directory is also reasonable if the team prefers a stronger separation; the key is a narrow, documented boundary, not the spelling.

Include the following in the move:

1. Add the chosen subtree to [skip-ci-config.toml](https://github.com/ROCm/TheRock/blob/main/build_tools/github_actions/skip-ci-config.toml). Do not exempt all of `build_tools/` or all GitHub Actions helpers.
2. Add explicit owners for the automation subtree and the privileged workflow in [CODEOWNERS](https://github.com/ROCm/TheRock/blob/main/.github/CODEOWNERS).
3. Update workflow entry points and test imports/discovery. Keep the tests in the unit-test workflow and pytest configuration, plus lint and security scanning, even though ROCm build/test CI is skipped.
4. Exercise the existing [path-filter logic](https://github.com/ROCm/TheRock/blob/main/build_tools/github_actions/configure_ci_path_filters.py) with automation-only changes and a mixed automation/build change. The latter must still require build CI.

The dispatcher workflow is already outside the explicit CI workflow list; the newly added production Python paths are what require the full build pipeline. No change to the filtering algorithm appears necessary. Keep build-consumed shared helpers outside a skipped subtree. Migrating every existing maintenance script can be separate follow-up work.

## Documentation and rockrel integration

Keep the workflow-specific inputs, examples, limitations, and recovery instructions in TheRock's new guide. Add one complete web-UI example and explicitly distinguish the workflow's **Use workflow from: main** selector from the `release_branch` input. Explain that conflicts require manual resolution and that a successful push followed by PR-creation failure requires inspecting the named branch and possibly opening the PR manually.

When expanding [rockrel PR 134's guide](https://github.com/ROCm/rockrel/pull/134/files), link to this operator guide from an “Updating release branches” section. That page should explain release policy and the larger sequence: select upstream fixes, open/review/merge component release PRs, then ensure TheRock consumes the intended component revisions for subsequent builds. This automation does not itself update TheRock submodule pins or coordinate a cross-repository change set. State that boundary without expanding this PR to automate it. The existing three-repository support is a reasonable initial scope; the other repositories listed in rockrel remain manual for now.

## Validation and evidence

- Downloaded the exact changed files and the GitHub API helper into `D:/scratch/codex/review-9637`; no source checkout was modified.
- From `D:/scratch/codex/review-9637/build_tools`, ran:

  ```text
  D:/projects/TheRock/.venv/Scripts/python.exe -m pytest --override-ini=cache_dir=D:/scratch/codex/pytest-cache/TheRock-review-9637 tests/git_cherry_pick_test.py github_actions/tests/cherry_pick_to_release_test.py -q
  ...........................................................              [100%]
  59 passed in 37.88s
  ```

- Ran the additional local reproduction with disposable repositories, using the PR's fixture:

  ```text
  D:/projects/TheRock/.venv/Scripts/python.exe D:/scratch/codex/review-9637/reapply_repro.py
  Fixture: source commit was picked onto release and then reverted.
  Automation rejected reapplication: Commit e0a3931a5c47ac764611dbdbd3308a8b34121709 was already cherry-picked onto release/therock-10.2
  Ordinary git cherry-pick exit status: 0
  Reapplied file: first fix
  ```

  Windows denied access to sandbox-created temporary directories during the first attempts; the successful reproduction ran with approved escalation. The script is saved in scratch for inspection.

- [PR unit-test CI](https://github.com/ROCm/TheRock/actions/runs/41944294165) passed at the reviewed head. Required unit-test, security-summary, and pre-commit checks passed. The focused tests exercise real Git repositories, compare tree results against ordinary cherry-pick, and test publication races; that is useful coverage worth retaining.
- [Multi-Arch CI](https://github.com/ROCm/TheRock/actions/runs/41944294260) is not green. Inspected the failing [rocprofiler test job](https://github.com/ROCm/TheRock/actions/runs/41944294260/job/127008078073): the failures are ATT no-intercept execution/validation, including a subprocess abort. Four Python wheel test jobs are cancelled. These do not establish a defect in the cherry-pick scripts, but the overall CI failure should not be represented as a passing run.
- The successful libraries dispatch was live; the failing systems dispatch was an expected conflict dry run. Live TheRock publication and a live BKC example were not established by the runs inspected. No additional workflows were triggered and no GitHub comments or reviews were posted.
- Full fetched diffs, metadata, dispatch logs, and the inspected failing job log are preserved under `D:/scratch/codex/review-9637`.

## Draft Bash logging output

The [commented Bash draft](../prototypes/cherry-pick-automation/cherry_pick.sh) uses `set -euxo pipefail`. These are complete script captures from local smoke runs with disposable Git repositories and a stubbed `gh` command. Publication pushes to a local bare repository; the PR URL is a placeholder. No GitHub writes occurred. The fixture uses `develop` as the default branch even for the TheRock selection.

The harness saved stdout followed by stderr, so the captures below preserve all output but do not represent chronological interleaving. GitHub Actions normally displays the streams as they arrive. `fetch_sources.py` was not invoked in these top-level TheRock cases; component fetching adds its own command and mirror-selection logs.

| Case | Captured lines | Result |
| --- | ---: | --- |
| Dry-run | 29 | Picks built; no branch published or PR requested |
| Local publication | 35 | Branch pushed to local remote; stub PR command called |
| Conflict | 30 | Git diagnostic preserved; no branch published or PR requested |

The test token was absent from all three captures. Authentication is supplied through `GH_TOKEN`, which the script never expands into command arguments. The full PR body goes to the job summary; the expanded title appears in the trace.

Command:

```text
D:/projects/TheRock/.venv/Scripts/python.exe D:/scratch/codex/review-9637/draft_smoke.py
```

Harness results:

```text
PASS: dry-run
PASS: local-publication
PASS: conflict
Artifacts: D:\scratch\codex\cherry-pick-draft-smoke-29c13d63
```

### dry-run

```text
branch 'shared/cherry-pick/1-1' set up to track 'origin/release/therock-10.2'.
[shared/cherry-pick/1-1 5f2f159] Fix the problem
 Date: Thu Nov 5 15:27:02 2026 -0800
 1 file changed, 1 insertion(+), 1 deletion(-)
+ automation_dir=D:/scratch/codex/cherry-pick-draft-smoke-29c13d63/dry-run/build_tools/automation
+ output_dir=D:/scratch/codex/cherry-pick-draft-smoke-29c13d63/cherry-pick-1-1
+ mkdir -p D:/scratch/codex/cherry-pick-draft-smoke-29c13d63/cherry-pick-1-1
+ [[ TheRock == TheRock ]]
+ target_dir=D:/scratch/codex/cherry-pick-draft-smoke-29c13d63/dry-run
+ cd D:/scratch/codex/cherry-pick-draft-smoke-29c13d63/dry-run
++ gh repo view ROCm/TheRock --json defaultBranchRef --jq .defaultBranchRef.name
+ default_branch=develop
+ git fetch --no-tags origin +refs/heads/release/therock-10.2:refs/remotes/origin/release/therock-10.2 +refs/heads/develop:refs/remotes/origin/develop
+ python D:/scratch/codex/cherry-pick-draft-smoke-29c13d63/dry-run/build_tools/automation/prepare_pr.py D:/scratch/codex/cherry-pick-draft-smoke-29c13d63/cherry-pick-1-1
+ branch=shared/cherry-pick/1-1
+ git switch --create shared/cherry-pick/1-1 refs/remotes/origin/release/therock-10.2
Switched to a new branch 'shared/cherry-pick/1-1'
+ git config user.name therockbot
+ git config user.email therockbot@amd.com
+ IFS=
+ read -r commit
+ git merge-base --is-ancestor f9034cd1b745de7a38cf9da72c07c9d1bbf41415 refs/remotes/origin/develop
+ git -c commit.gpgsign=false cherry-pick -x f9034cd1b745de7a38cf9da72c07c9d1bbf41415
+ IFS=
+ read -r commit
+ cat D:/scratch/codex/cherry-pick-draft-smoke-29c13d63/cherry-pick-1-1/body.md
+ [[ true == true ]]
+ echo 'Dry run: nothing was pushed and no PR was created.'
+ exit 0
```

### local-publication

```text
branch 'shared/cherry-pick/2-1' set up to track 'origin/release/therock-10.2'.
[shared/cherry-pick/2-1 e4e4610] Fix the problem
 Date: Thu Nov 5 15:27:02 2026 -0800
 1 file changed, 1 insertion(+), 1 deletion(-)
https://example.invalid/pull/1
+ automation_dir=D:/scratch/codex/cherry-pick-draft-smoke-29c13d63/local-publication/build_tools/automation
+ output_dir=D:/scratch/codex/cherry-pick-draft-smoke-29c13d63/cherry-pick-2-1
+ mkdir -p D:/scratch/codex/cherry-pick-draft-smoke-29c13d63/cherry-pick-2-1
+ [[ TheRock == TheRock ]]
+ target_dir=D:/scratch/codex/cherry-pick-draft-smoke-29c13d63/local-publication
+ cd D:/scratch/codex/cherry-pick-draft-smoke-29c13d63/local-publication
++ gh repo view ROCm/TheRock --json defaultBranchRef --jq .defaultBranchRef.name
+ default_branch=develop
+ git fetch --no-tags origin +refs/heads/release/therock-10.2:refs/remotes/origin/release/therock-10.2 +refs/heads/develop:refs/remotes/origin/develop
+ python D:/scratch/codex/cherry-pick-draft-smoke-29c13d63/local-publication/build_tools/automation/prepare_pr.py D:/scratch/codex/cherry-pick-draft-smoke-29c13d63/cherry-pick-2-1
+ branch=shared/cherry-pick/2-1
+ git switch --create shared/cherry-pick/2-1 refs/remotes/origin/release/therock-10.2
Switched to a new branch 'shared/cherry-pick/2-1'
+ git config user.name therockbot
+ git config user.email therockbot@amd.com
+ IFS=
+ read -r commit
+ git merge-base --is-ancestor f9034cd1b745de7a38cf9da72c07c9d1bbf41415 refs/remotes/origin/develop
+ git -c commit.gpgsign=false cherry-pick -x f9034cd1b745de7a38cf9da72c07c9d1bbf41415
+ IFS=
+ read -r commit
+ cat D:/scratch/codex/cherry-pick-draft-smoke-29c13d63/cherry-pick-2-1/body.md
+ [[ false == true ]]
+ git -c credential.helper= -c 'credential.helper=!gh auth git-credential' push --force-with-lease=refs/heads/shared/cherry-pick/2-1: origin HEAD:refs/heads/shared/cherry-pick/2-1
To D:\scratch\codex\cherry-pick-draft-smoke-29c13d63\remote.git
 * [new branch]      HEAD -> shared/cherry-pick/2-1
+ echo 'Branch published: ROCm/TheRock:shared/cherry-pick/2-1'
+ tee -a D:/scratch/codex/cherry-pick-draft-smoke-29c13d63/local-publication-summary.md
++ cat D:/scratch/codex/cherry-pick-draft-smoke-29c13d63/cherry-pick-2-1/title.txt
+ gh pr create --repo ROCm/TheRock --base release/therock-10.2 --head shared/cherry-pick/2-1 --title '[therock-10.2] Fix the problem' --body-file D:/scratch/codex/cherry-pick-draft-smoke-29c13d63/cherry-pick-2-1/body.md
```

### conflict

```text
branch 'shared/cherry-pick/3-1' set up to track 'origin/release/therock-10.2'.
Auto-merging content.txt
CONFLICT (content): Merge conflict in content.txt
+ automation_dir=D:/scratch/codex/cherry-pick-draft-smoke-29c13d63/conflict/build_tools/automation
+ output_dir=D:/scratch/codex/cherry-pick-draft-smoke-29c13d63/cherry-pick-3-1
+ mkdir -p D:/scratch/codex/cherry-pick-draft-smoke-29c13d63/cherry-pick-3-1
+ [[ TheRock == TheRock ]]
+ target_dir=D:/scratch/codex/cherry-pick-draft-smoke-29c13d63/conflict
+ cd D:/scratch/codex/cherry-pick-draft-smoke-29c13d63/conflict
++ gh repo view ROCm/TheRock --json defaultBranchRef --jq .defaultBranchRef.name
+ default_branch=develop
+ git fetch --no-tags origin +refs/heads/release/therock-10.2:refs/remotes/origin/release/therock-10.2 +refs/heads/develop:refs/remotes/origin/develop
+ python D:/scratch/codex/cherry-pick-draft-smoke-29c13d63/conflict/build_tools/automation/prepare_pr.py D:/scratch/codex/cherry-pick-draft-smoke-29c13d63/cherry-pick-3-1
+ branch=shared/cherry-pick/3-1
+ git switch --create shared/cherry-pick/3-1 refs/remotes/origin/release/therock-10.2
Switched to a new branch 'shared/cherry-pick/3-1'
+ git config user.name therockbot
+ git config user.email therockbot@amd.com
+ IFS=
+ read -r commit
+ git merge-base --is-ancestor f9034cd1b745de7a38cf9da72c07c9d1bbf41415 refs/remotes/origin/develop
+ git -c commit.gpgsign=false cherry-pick -x f9034cd1b745de7a38cf9da72c07c9d1bbf41415
error: could not apply f9034cd... Fix the problem
hint: After resolving the conflicts, mark them with
hint: "git add/rm <pathspec>", then run
hint: "git cherry-pick --continue".
hint: You can instead skip this commit with "git cherry-pick --skip".
hint: To abort and get back to the state before "git cherry-pick",
hint: run "git cherry-pick --abort".
hint: Disable this message with "git config advice.mergeConflict false"
```

### Generated PR body

```markdown
Cherry-picks into `release/therock-10.2`.

Required release fix.

JIRA ID: AIRDEL-123

### Fix the problem
Source: https://github.com/ROCm/TheRock/commit/f9034cd1b745de7a38cf9da72c07c9d1bbf41415

<details><summary>Original commit message</summary>

> Fix the problem
> 
> Explanation and upstream validation.

</details>

Release-branch validation: review the checks on this PR.

Requested by @fixture via https://example.invalid/run/1.
```

Generated with Codex
