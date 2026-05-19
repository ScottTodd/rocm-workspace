---
name: review-branch
description: Review the current local branch using this workspace's ROCm review system. Use when Codex is asked to review a branch, review local changes, review current work before a PR, or run focused local reviews for style, tests, documentation, architecture, security, or performance.
---

# Review Branch

Use this skill to create an evidence-based review file for the current local
branch or another local branch the user identifies.

## Workflow

1. Parse the request.
   - Optional review types: `style`, `tests`, `documentation`, `architecture`,
     `security`, `performance`.
   - If no type is provided, perform a comprehensive review.
   - Confirm which repository is being reviewed when the workspace has multiple
     candidate repos.

2. Gather branch context.
   ```bash
   git branch --show-current
   git status --short
   git log --oneline main..HEAD
   git diff --stat main..HEAD
   git diff main..HEAD
   ```
   If `main` is not the right base, try `upstream/main`, the tracked upstream,
   or the base branch named by the user.

3. Determine the output filename.
   - Scan `reviews/local_*.md` and choose the next zero-padded counter.
   - Sanitize the branch name by replacing `/` with `-`.
   - Use `reviews/local_{COUNTER}_{branch-name}.md` for comprehensive reviews.
   - Use `reviews/local_{COUNTER}_{branch-name}_{TYPE}.md` for a single focused
     review.

4. Read review instructions.
   - Always read `reviews/REVIEW_GUIDELINES.md`.
   - Read `reviews/REVIEW_TYPES.md` for focused reviews.
   - Read relevant files under `reviews/guidelines/` based on changed files:
     tests, documentation, GitHub Actions, artifacts, PR hygiene, security.

5. Review the diff.
   - For comprehensive reviews, cover correctness, style, tests,
     documentation, architecture, security, and performance.
   - For focused reviews, stay inside the requested focus unless another issue
     is severe enough to mention.
   - Account for uncommitted changes in `git status`; do not ignore them.
   - Prefer concrete findings with file/line evidence, impact, and a required
     action or recommendation.

6. Write the review file.
   - Include branch, base, date, commit count, summary, overall assessment,
     detailed findings, recommendations, testing recommendations, and
     conclusion.
   - Use `APPROVED`, `CHANGES REQUESTED`, or `REJECTED`.
   - Use severity labels: `BLOCKING`, `IMPORTANT`, `SUGGESTION`, `FUTURE WORK`.

7. Report results.
   - State the review file path.
   - Lead with blocking findings, if any.
   - Summarize the overall assessment.

## Notes

- Do not modify reviewed code while performing the review unless the user asks
  for fixes.
- If the branch depends on sibling repositories, use `directory-map.md` to
  choose paths and prefer `git -C <path>` for commands.
