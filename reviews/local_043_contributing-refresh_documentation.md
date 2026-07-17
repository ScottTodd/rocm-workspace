# Documentation Review: contributing-refresh

**Branch:** `contributing-refresh`
**Base:** `main`
**Reviewed:** 2026-07-17
**Commits:** 5
**Review Type:** Documentation

---

## Summary

This branch substantially reorganizes `CONTRIBUTING.md` around developer
policies and development workflows, adds explanations for branch, issue, and
pull-request policies, and introduces a pull request template.

**Net changes:** +202, -76 across 2 files.

The new top-level structure is much easier to scan than the previous document.
The branch and issue policies generally explain both the rule and its purpose,
and the pull-request standards table gives contributors a useful overview.

---

## Overall Assessment

**Status: CHANGES REQUESTED**

The overall direction and organization are good, but the new template currently
defeats two PR-description checks, and several navigation links do not resolve
to this repository. The tracking policy is also described inconsistently across
the table, detailed section, template, and policy bot. Those issues should be
resolved before the new guidance becomes the contributor entry point.

---

## Detailed Findings

### BLOCKING: The blank template satisfies the PR bot's description checks

[`pull_request_template.md:5`](https://github.com/ROCm/TheRock/blob/ce899b19d3ca5bb1c92061e73d9cc0bba4d23679/.github/pull_request_template.md#L5)
through
[`pull_request_template.md:7`](https://github.com/ROCm/TheRock/blob/ce899b19d3ca5bb1c92061e73d9cc0bba4d23679/.github/pull_request_template.md#L7)
put a fully formed issue URL inside an HTML comment:

```markdown
<!-- GitHub issue: https://github.com/ROCm/TheRock/issues/1234 -->
```

The policy bot validates the raw PR body. It does not remove HTML comments
before counting characters or searching for issue-reference patterns. As a
result, the untouched template is already longer than the 30-character minimum,
and the example URL satisfies the GitHub issue URL pattern. A direct call to
`ensure_pr_description()` with the new template as the body returned an empty
error list (`[]`).

This means a contributor can leave every substantive section empty and still
pass both the meaningful-description and tracking-reference portions of the
policy check.

**Required action:** Make the template and validator agree about boilerplate.
At minimum, the example must not contain a reference that matches the bot's
pattern. To preserve the meaningful-description check as well, validate only
contributor-supplied content after excluding HTML comments and other template
boilerplate, or use some equivalent mechanism that makes an untouched template
fail.

### BLOCKING: Repository links escape the repository, and the checklist uses a nonexistent branch

Many links in `CONTRIBUTING.md` use a leading slash, including the links to
[`skills/` at line 63](https://github.com/ROCm/TheRock/blob/ce899b19d3ca5bb1c92061e73d9cc0bba4d23679/CONTRIBUTING.md#L63),
[the PR bot and template at line 165](https://github.com/ROCm/TheRock/blob/ce899b19d3ca5bb1c92061e73d9cc0bba4d23679/CONTRIBUTING.md#L165),
[`CODEOWNERS` at line 179](https://github.com/ROCm/TheRock/blob/ce899b19d3ca5bb1c92061e73d9cc0bba4d23679/CONTRIBUTING.md#L179),
and [`CLAUDE.md` at line 249](https://github.com/ROCm/TheRock/blob/ce899b19d3ca5bb1c92061e73d9cc0bba4d23679/CONTRIBUTING.md#L249).
GitHub renders a target such as `/skills/` as `href="/skills/"`, which sends the
reader to `https://github.com/skills/`, not to this repository's `skills/`
directory. Links from the repository-root `CONTRIBUTING.md` should omit the
leading slash.

Separately,
[`pull_request_template.md:23`](https://github.com/ROCm/TheRock/blob/ce899b19d3ca5bb1c92061e73d9cc0bba4d23679/.github/pull_request_template.md#L23)
links to `ROCm/TheRock/blob/develop/CONTRIBUTING.md`. The repository's default
branch is `main`, and the GitHub branches API currently returns 404 for
`develop`, so the only actionable checklist link is broken.

**Required action:** Use repository-relative links without a leading slash in
`CONTRIBUTING.md`, and point the PR-body checklist at the `main` version of
`CONTRIBUTING.md` (or another URL that remains valid when rendered in a PR
description).

### IMPORTANT: The tracking requirement has four different formulations

The contributor-facing text does not establish one precise rule:

- [`CONTRIBUTING.md:165`](https://github.com/ROCm/TheRock/blob/ce899b19d3ca5bb1c92061e73d9cc0bba4d23679/CONTRIBUTING.md#L165)
  says pull requests "must link an issue."
- [`CONTRIBUTING.md:184`](https://github.com/ROCm/TheRock/blob/ce899b19d3ca5bb1c92061e73d9cc0bba4d23679/CONTRIBUTING.md#L184)
  and line 186 say a GitHub issue is "expected," while lines 201-203 allow JIRA
  IDs and unspecified case-by-case exceptions.
- [`pull_request_template.md:5`](https://github.com/ROCm/TheRock/blob/ce899b19d3ca5bb1c92061e73d9cc0bba4d23679/.github/pull_request_template.md#L5)
  says a GitHub issue is only "strongly encouraged."
- The policy bot FAQ says a tracking item is required and accepts a JIRA ID,
  ISSUE ID, closing keyword, bare issue number, or GitHub issue URL.

The distinction matters because a first-time contributor cannot tell whether a
GitHub issue is mandatory, preferred over another required tracking item, or
optional. The exception sentence also does not explain who can grant an
exception or how a contributor requests one.

**Recommendation:** Define the policy once using consistent terms and modal
verbs, then mirror that language in the overview table and template. If the
actual rule is "a tracking reference is required, with GitHub issues strongly
preferred," make that distinction explicit and document the exception process.

### IMPORTANT: The unit-test row overstates the enforced policy

[`CONTRIBUTING.md:167`](https://github.com/ROCm/TheRock/blob/ce899b19d3ca5bb1c92061e73d9cc0bba4d23679/CONTRIBUTING.md#L167)
says "Changes must be unit tested." The bot policy and FAQ are narrower:
documentation and configuration-only PRs pass automatically, while changes to
recognized source-code extensions must include a test-file change.

The table's absolute wording makes this documentation-only branch appear to
violate its own policy and does not explain what contributors should do for
changes that are not reasonably unit-testable.

**Recommendation:** Scope the row to source-code changes and mention or link to
the exemptions. If this is intended to express a broader human-review policy
than the bot enforces, explain that distinction and briefly justify what forms
of verification are expected for non-code changes.

### IMPORTANT: Several proofreading errors remain in the revised text

The clearest copy errors are:

- [`CONTRIBUTING.md:83`](https://github.com/ROCm/TheRock/blob/ce899b19d3ca5bb1c92061e73d9cc0bba4d23679/CONTRIBUTING.md#L83):
  "One notable exception is GitHub Actions workflows ..." is missing "that"
  after "is."
- [`CONTRIBUTING.md:88`](https://github.com/ROCm/TheRock/blob/ce899b19d3ca5bb1c92061e73d9cc0bba4d23679/CONTRIBUTING.md#L88):
  "a branch in the shared workflow" should refer to the shared repository.
- [`CONTRIBUTING.md:140`](https://github.com/ROCm/TheRock/blob/ce899b19d3ca5bb1c92061e73d9cc0bba4d23679/CONTRIBUTING.md#L140):
  "so we triage efficiently" needs "can" or a different construction.
- [`CONTRIBUTING.md:189`](https://github.com/ROCm/TheRock/blob/ce899b19d3ca5bb1c92061e73d9cc0bba4d23679/CONTRIBUTING.md#L189):
  "helps with for release planning" has an extra word.

Additional polish opportunities:

- [`CONTRIBUTING.md:5`](https://github.com/ROCm/TheRock/blob/ce899b19d3ca5bb1c92061e73d9cc0bba4d23679/CONTRIBUTING.md#L5)
  repeats "help" in "volunteer to help contribute to help close these gaps"
  and would benefit from punctuation around "even better."
- [`CONTRIBUTING.md:153`](https://github.com/ROCm/TheRock/blob/ce899b19d3ca5bb1c92061e73d9cc0bba4d23679/CONTRIBUTING.md#L153)
  needs a comma after the introductory phrase "When planning complex changes."
- [`CONTRIBUTING.md:175`](https://github.com/ROCm/TheRock/blob/ce899b19d3ca5bb1c92061e73d9cc0bba4d23679/CONTRIBUTING.md#L175)
  would read more naturally as "request a review" and "code owner" rather than
  "request review" and "CODEOWNER."
- [`CONTRIBUTING.md:251`](https://github.com/ROCm/TheRock/blob/ce899b19d3ca5bb1c92061e73d9cc0bba4d23679/CONTRIBUTING.md#L251)
  should hyphenate the compound modifier in "higher-quality contributions."

**Recommendation:** Address the meaning-changing and obvious grammatical errors
before merge, then make one final manual proofreading pass for the smaller
items.

### SUGGESTION: Put prerequisite guidance before the request-review step

Within "Creating pull requests," the document presents the overview table,
immediately discusses drafts and requesting review, then returns to the issue
requirement and pre-commit preparation. The style guides appear after the whole
pull-request section. This tells a first-time contributor how to request review
before walking them through the work expected before review.

The split between "Developer policies" and "Development workflows" also puts
branch creation and naming well before issue and feature discussion, even though
the natural contributor sequence is usually discussion, branch creation,
implementation/verification, PR creation, and review.

**Recommendation:** Consider ordering the actionable material as a contributor
journey: issue or feature discussion; branch creation/naming; style, testing,
and pre-commit expectations; PR creation and tracking reference; draft state;
then reviewer selection. Restoring the explicit instruction to target `main`
would also answer a basic first-time-contributor question removed by this
rewrite.

### SUGGESTION: Clean up table HTML and source formatting

The pull-request standards table is a useful overview, but its embedded list
HTML is inconsistent. In
[`CONTRIBUTING.md:164`](https://github.com/ROCm/TheRock/blob/ce899b19d3ca5bb1c92061e73d9cc0bba4d23679/CONTRIBUTING.md#L164),
`</ul>` appears before `</li>`, and line 165 opens a second `<li>` without
explicitly closing the first. Browsers will usually repair this, but valid,
consistent markup will be more portable and maintainable.

Several prose lines are also much longer than the surrounding wrapped text,
most notably the 321-character policy quotation at line 52. Wrapping prose in
block quotes and list items consistently would make the Markdown source easier
to review.

**Recommendation:** Correct the list nesting (or use simpler `<br>` separators)
and wrap non-table prose consistently.

### SUGGESTION: Clarify the status and source of the AI-policy quotation

[`CONTRIBUTING.md:50`](https://github.com/ROCm/TheRock/blob/ce899b19d3ca5bb1c92061e73d9cc0bba4d23679/CONTRIBUTING.md#L50)
introduces a block quote with "Of particular note," but does not say whether the
paragraph is quoted from LLVM, PyTorch, both, or is TheRock's own synthesized
policy. That ambiguity weakens an otherwise useful accountability rule.

**Recommendation:** Attribute the quotation to its source, or present it in the
project's own voice as a direct TheRock requirement. If it is direct project
policy, wording such as "of sufficiently high quality" would also read more
naturally than "high enough quality."

---

## Recommendations

### REQUIRED (Blocking)

1. Prevent untouched template boilerplate from satisfying the PR bot's
   meaningful-description and tracking-reference checks.
2. Repair the repository navigation links and the template's nonexistent
   `develop`-branch link.

### Recommended

1. State one consistent tracking-reference policy across all contributor-facing
   surfaces.
2. Scope and justify the unit-test requirement accurately.
3. Fix the meaning-changing and obvious grammatical errors.

### Consider

1. Reorder the workflow around the sequence a first-time contributor follows.
2. Correct the table's HTML nesting and wrap long prose lines.
3. Attribute or restate the AI accountability quotation.

---

## Verification

- Reviewed the complete `main..HEAD` diff and both full changed files.
- Ran `git diff --check main..HEAD`; no whitespace errors were reported.
- Confirmed all local file destinations referenced by the new material exist.
- Used GitHub's GFM rendering API to verify that `/skills/` remains
  `href="/skills/"` rather than becoming repository-relative.
- Used the GitHub repository API to confirm that the default branch is `main`
  and that `develop` returns 404.
- Called the current PR bot's `ensure_pr_description()` with the untouched pull
  request template; it returned no validation errors.
- Rendered the Markdown table locally to inspect its generated HTML.
- No dedicated typo checker was available on `PATH`; typo and grammar review
  was manual.
- No CI run was inspected: no PR was discoverable through the authenticated CLI
  in this environment, and the changed files are documentation/template files.

---

## Conclusion

**Approval Status: CHANGES REQUESTED**

The revised document has a solid high-level structure and much better policy
rationale than the previous version. Fix the template/bot interaction and
broken links first, then align the policy wording and complete the proofreading
pass. After those changes, the remaining ordering and formatting suggestions
are editorial rather than merge blockers.

---

_Review generated by OpenAI Codex._
