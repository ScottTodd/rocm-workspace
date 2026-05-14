---
name: review-pr
description: Review a GitHub pull request using this workspace's ROCm review system. Use when Codex is asked to review a PR URL, review a ROCm/TheRock pull request, perform a comprehensive PR review, or run focused PR reviews for style, tests, documentation, architecture, security, or performance.
---

# Review PR

Use this skill to create an evidence-based review file for a GitHub pull
request.

## Workflow

1. Parse the request.
   - Required input: GitHub PR URL.
   - Optional review types: `style`, `tests`, `documentation`, `architecture`,
     `security`, `performance`.
   - If no type is provided, perform a comprehensive review.

2. Fetch PR context with `gh`.
   ```bash
   gh pr view <URL> --json number,title,author,body,files,additions,deletions,state,baseRefName,headRefName
   gh pr diff <URL>
   gh pr checks <URL>
   ```
   If `gh` is unavailable or unauthenticated, report that clearly and use any
   supplied diff/context instead of inventing PR details.

3. Read review instructions.
   - Always read `reviews/REVIEW_GUIDELINES.md`.
   - Read `reviews/REVIEW_TYPES.md` for focused reviews.
   - Read relevant files under `reviews/guidelines/` based on changed files:
     tests, documentation, GitHub Actions, artifacts, PR hygiene, security.

4. Gather CI evidence when available.
   - Check all PR checks, not only a run linked in the PR body.
   - Inspect failing or suspicious jobs before finalizing findings.
   - For job step details, use:
     ```bash
     gh api repos/OWNER/REPO/actions/jobs/JOB_ID \
       --jq '{name, steps: [.steps[] | {name, conclusion, started_at, completed_at}]}'
     ```
   - Compare against a recent baseline on `main` when timing, cache behavior, or
     workflow changes matter.

5. Review the diff.
   - For comprehensive reviews, cover correctness, style, tests,
     documentation, architecture, security, and performance.
   - For focused reviews, stay inside the requested focus unless another issue
     is severe enough to mention.
   - Prefer concrete findings with file/line evidence, impact, and a required
     action or recommendation.
   - Do not post GitHub comments unless the user explicitly asks.

6. Write the review file.
   - Extract the repository name from the PR URL.
   - Use `reviews/pr_{REPO}_{NUMBER}.md` for comprehensive reviews.
   - Use `reviews/pr_{REPO}_{NUMBER}_{TYPE}.md` for a single focused review.
   - For multiple focus areas, either write one combined review with sections or
     suffix the file with a concise combined label.

7. Report results.
   - State the review file path.
   - Lead with blocking findings, if any.
   - Include the overall assessment: `APPROVED`, `CHANGES REQUESTED`, or
     `REJECTED`.

## Severity

- `BLOCKING`: must fix before approval.
- `IMPORTANT`: should fix before human review or before merge.
- `SUGGESTION`: optional improvement.
- `FUTURE WORK`: useful but out of scope for this PR.
