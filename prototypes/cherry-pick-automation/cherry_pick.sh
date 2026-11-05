#!/usr/bin/env bash
# Copyright Advanced Micro Devices, Inc.
# SPDX-License-Identifier: MIT

# Stop on failed commands/pipelines and trace the Git operations for diagnosis.
# Authentication stays in GH_TOKEN; no command expands the token into its args.
set -euxo pipefail

# Keep generated PR text outside the checkout so it cannot enter a picked commit.
automation_dir="${GITHUB_WORKSPACE}/build_tools/automation"
output_dir="${RUNNER_TEMP}/cherry-pick-${GITHUB_RUN_ID}-${GITHUB_RUN_ATTEMPT}"
mkdir -p "${output_dir}"

# TheRock is already checked out. Components use the shared mirror-backed fetcher.
if [[ "${REPOSITORY}" == TheRock ]]; then
  target_dir="${GITHUB_WORKSPACE}"
else
  # Fetch only the requested component, without build patches or binary payloads.
  python "${GITHUB_WORKSPACE}/build_tools/fetch_sources.py" \
    --no-include-system-projects --no-include-compilers \
    --no-include-debug-tools --no-include-ml-frameworks \
    --no-include-media-libs --no-include-math-libraries \
    --no-include-rocm-libraries --no-include-rocm-systems \
    "--include-${REPOSITORY}" --no-apply-patches --dvc-projects disabled
  target_dir="${GITHUB_WORKSPACE}/${REPOSITORY}"
fi

# Refresh both refs: picks must come from the default branch and target the release.
cd "${target_dir}"
default_branch="$(gh repo view "ROCm/${REPOSITORY}" --json defaultBranchRef --jq .defaultBranchRef.name)"
git fetch --no-tags origin \
  "+refs/heads/${RELEASE_BRANCH}:refs/remotes/origin/${RELEASE_BRANCH}" \
  "+refs/heads/${default_branch}:refs/remotes/origin/${default_branch}"
# Validate inputs, resolve/deduplicate SHAs in order, and format the prospective PR.
python "${automation_dir}/prepare_pr.py" "${output_dir}"

# Each attempt gets its own branch. Git preserves authors/messages and adds -x
# provenance. A conflict, empty pick, or failed ancestry check exits before push.
branch="shared/cherry-pick/${GITHUB_RUN_ID}-${GITHUB_RUN_ATTEMPT}"
git switch --create "${branch}" "refs/remotes/origin/${RELEASE_BRANCH}"
git config user.name therockbot
git config user.email therockbot@amd.com
while IFS= read -r commit; do
  git merge-base --is-ancestor "${commit}" "refs/remotes/origin/${default_branch}"
  git -c commit.gpgsign=false cherry-pick -x "${commit}"
done < "${output_dir}/commits.txt"

# Dry runs perform the same picks and show the PR body, then stop before publishing.
cat "${output_dir}/body.md" >> "${GITHUB_STEP_SUMMARY}"
if [[ "${DRY_RUN}" == true ]]; then
  echo 'Dry run: nothing was pushed and no PR was created.' >> "${GITHUB_STEP_SUMMARY}"
  exit 0
fi

# Publish only after all picks succeed. The empty lease requires an absent branch;
# the per-command credential helper reads GH_TOKEN without storing it in Git config.
git -c credential.helper= -c 'credential.helper=!gh auth git-credential' \
  push --force-with-lease="refs/heads/${branch}:" origin "HEAD:refs/heads/${branch}"
# If the API call fails after push, leave the branch and its name for manual recovery.
echo "Branch published: ROCm/${REPOSITORY}:${branch}" >> "${GITHUB_STEP_SUMMARY}"
gh pr create --repo "ROCm/${REPOSITORY}" --base "${RELEASE_BRANCH}" \
  --head "${branch}" --title "$(cat "${output_dir}/title.txt")" \
  --body-file "${output_dir}/body.md" | tee -a "${GITHUB_STEP_SUMMARY}"
