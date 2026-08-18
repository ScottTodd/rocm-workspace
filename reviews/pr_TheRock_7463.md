# PR Review: Add whl-next aggregate index generator

* **PR:** https://github.com/ROCm/TheRock/pull/7463
* **Head:** `051414a1e21986b1d137fc1b0eadf92f39dbe242`
* **Base:** `main`
* **Reviewed:** 2026-08-18
* **Scope:** Architecture first, then tests, style, and PR hygiene

## Summary

This PR adds a schema-versioned ownership manifest and a standalone tool that can
render the `/rocm/whl-next/` root, an exact routing artifact, and a validation
report. The implementation has strong input validation, deterministic output,
and extensive cross-platform unit coverage.

The main risk is not low-level correctness. It is the contract between this tool
and TheRock-Infra: deployment-shaped outputs can currently be produced without
validating the product indexes, and the PR intentionally folds release-stream
availability into a manifest that issue #6948 defined as ownership-only. Those
decisions should be resolved explicitly before this becomes the source of a
public package index.

**Net changes:** +2,958 lines across four files.

## Overall Assessment

**CHANGES REQUESTED**

I would not merge the current deployment contract without resolving the two
blocking findings below. The underlying parsing and rendering code is in good
shape, but it is too easy for a caller to produce authoritative-looking output
without authoritative content validation.

## High-Leverage Architectural Findings

### BLOCKING: Deployment-shaped output is not coupled to content validation

[`generate_outputs()`](https://github.com/ROCm/TheRock/blob/051414a1e21986b1d137fc1b0eadf92f39dbe242/build_tools/packaging/python/aggregate_index.py#L587-L644)
uses the manifest directly when `content_root` is absent, then passes both the
manifest-only and content-validated cases through the same
`ValidatedIndexContent` and writes identically named deployment artifacts.
`declared_index_content()` even constructs `ValidatedPackage` objects using
empty `Path()` placeholders. Separately,
[`--allow-unpublished`](https://github.com/ROCm/TheRock/blob/051414a1e21986b1d137fc1b0eadf92f39dbe242/build_tools/packaging/python/aggregate_index.py#L1191-L1253)
can exclude manifest-owned packages, write a root and route table, print only a
warning, and return success.

This contradicts the core invariant in
[#6948](https://github.com/ROCm/TheRock/issues/6948): the manifest, validated
product content, aggregate root, and routing package sets are expected to be
equal, and validation failures should stop generation. A typo in an Infra
invocation can currently create routes to missing pages or publish an incomplete
aggregate index while still producing files that look ready to deploy.

**Required action:** agree on one enforceable deployment boundary with the
TheRock-Infra consumer before merging. My preference is:

1. Make the command that writes deployable artifacts require an authoritative
   content snapshot and strict validation.
2. Keep permissive inventory behavior in `validate-content` (or another
   diagnostic command) and do not let it write deployment-named artifacts.
3. If manifest-only generation must remain, give it a clearly distinct output
   contract and make the Infra consumer reject reports where
   `content_validated` is false. That guard needs an end-to-end test in the
   consumer, not just a comment in this module.

### BLOCKING: The checked-in 111-route policy has not been validated against authoritative content

The PR test plan runs `validate-manifest`, which checks schema and syntax, but it
does not run `validate-content` or `generate --content-root` against a real
product-index snapshot. The synthetic fixtures prove that the validator works;
they do not prove that the checked-in owners and per-stream availability are
correct.

Because the manifest is intended to become authoritative policy, this is the
highest-value data review in the PR. A wrong owner is a public routing bug, and a
wrong stream assignment can either hide a published package or route users to a
404.

**Required action:** attach validation evidence from authoritative product-local
snapshots for every distinct stream package set, using strict completeness and
without `--allow-unpublished`. If obtaining those snapshots is exclusively an
Infra responsibility, land the corresponding consumer/preflight enforcement
with this change or narrow this PR so it does not yet establish the unchecked
manifest as deployable policy.

### IMPORTANT: Ownership and release availability are now one policy surface

The manifest introduces global and per-package release stream declarations at
[`rocm_whl_next_ownership.yaml`](https://github.com/ROCm/TheRock/blob/051414a1e21986b1d137fc1b0eadf92f39dbe242/build_tools/packaging/python/rocm_whl_next_ownership.yaml#L8-L20).
That is an intentional departure from #6948, which says that the ownership
manifest must not contain release-stream names.

Ownership answers "where does this package route?" Availability answers "was
this package published in this release stream?" The former is relatively stable
policy; the latter changes with publishing state. Combining them makes ordinary
release changes edit the ownership schema and creates another place that must be
kept in lockstep with the product indexes.

The restricted architecture set appears to follow the actual release matrix,
not the somewhat stale readiness table in `SUPPORTED_GPUS.md`. Successful
[`ROCm/rockrel` prerelease run 31840058334](https://github.com/ROCm/rockrel/actions/runs/31840058334)
built Linux families `gfx101x`, `gfx103x`, `gfx110x`, `gfx120x`, `gfx1150-1153`,
`gfx908`, `gfx90a`, `gfx94x`, `gfx950`, and `gfx125x`, with the corresponding
Windows subset. That aligns with the manifest's RC/stable-enabled architecture
families. The three targets limited to `dev` and `nightly`--`gfx900`, `gfx906`,
and `gfx90c`--are precisely the ones absent from the prerelease run.

This removes the apparent data inconsistency, but the relationship is not
documented or enforced. A reader comparing only with `SUPPORTED_GPUS.md` would
reach the wrong conclusion, while a future release-matrix change can silently
leave the hand-maintained manifest stale.

**Recommendation:** either split stable ownership from stream availability and
derive/validate availability from the stream-specific product snapshots, or
formally amend #6948 and document which system owns availability updates. This
is a design decision worth the requester's direct attention; it will determine
the long-term review and release burden of this file. Document the authoritative
release-matrix source for each exception and preferably generate or validate
stream availability from the release workflow configuration. Do not use
`SUPPORTED_GPUS.md` as the machine-readable source unless its purpose and
freshness guarantees change.

### IMPORTANT: Define and test the actual CloudFront consumer format and size budget

For `nightly`, the generated route artifact contains 111 routes and is 18,241
bytes as written. Minifying the current list-of-records shape is still 13,884
bytes. AWS documents a non-adjustable 10 KB maximum for an entire
[CloudFront Function](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/cloudfront-limits.html#limits-functions),
including the routing code. A compact `package -> owner_path` map for the same
data is approximately 4,738 bytes before JavaScript is added, so the design is
feasible, but only if the Infra translation deliberately discards the repeated
fields and remains compact as package count grows.

The route JSON therefore cannot be treated as an embeddable artifact in its
current form. It is an intermediate representation whose consumer transform is
part of the correctness contract.

**Recommendation:** define the consumer-facing schema with TheRock-Infra now
(the map shape from #6948 is a better starting point), add an end-to-end route
rewrite test, and fail generation/deployment when the final CloudFront source
exceeds the 10 KB quota. Consider CloudFront KeyValueStore if long-term package
growth makes inline data too tight.

### SUGGESTION: Treat the three files as one immutable generation

[`write_generated_outputs()`](https://github.com/ROCm/TheRock/blob/051414a1e21986b1d137fc1b0eadf92f39dbe242/build_tools/packaging/python/aggregate_index.py#L647-L673)
checks package-set equality in memory and atomically replaces each individual
file, but the three-file set is not atomic. A failure after replacing the HTML
but before replacing the route table can leave mixed generations in a reused
output directory.

Have the deployment workflow generate into a fresh, versioned staging
directory and promote/upload the generation as a unit. Including a manifest
digest or generation ID in both JSON artifacts would also make cross-artifact
verification straightforward.

### SUGGESTION: Split the module at domain boundaries

The new 1,339-line module contains YAML loading/schema validation, domain
models, HTML parsing, content validation, rendering, filesystem writes, and CLI
handling. The `ValidatedPackage(Path(), Path())` placeholder noted above is a
symptom of the manifest-only and validated modes sharing a model that does not
fit both.

Before more backends or indexes are added, separate the manifest model/parser,
content validation, output rendering, and CLI orchestration. At minimum, use
distinct declared-route and validated-content types so a caller cannot mistake
unvalidated data for evidence-backed data.

## Smaller Coding, Test, and Documentation Details

### IMPORTANT: Add durable user and maintainer documentation

The 70-line module docstring is currently the only documentation for a new
manifest schema, three output contracts, stream behavior, strict versus
permissive validation, and the handoff to TheRock-Infra. This is too much
operational policy to leave inside one implementation file, particularly when
the documented `validate-content` example is already inconsistent with the CLI.

**Recommendation:** add an aggregate-index section to
[`docs/packaging/python_packaging.md`](https://github.com/ROCm/TheRock/blob/main/docs/packaging/python_packaging.md)
and cross-link it from
[`build_tools/third_party/s3_management/README.md`](https://github.com/ROCm/TheRock/blob/main/build_tools/third_party/s3_management/README.md).
Cover the manifest ownership/availability contract, the source of stream
exceptions, safe deployment invocation, diagnostic modes, artifact schemas,
the TheRock-Infra boundary, and worked commands. Link both the historical
[PEP 503](https://peps.python.org/pep-0503/) and the maintained
[Simple Repository API specification](https://packaging.python.org/en/latest/specifications/simple-repository-api/)
where the code relies on normalized project names and simple-index links.

### BLOCKING: Remove the framework-only unsupported-argument test

[`test_main_rejects_unsupported_content_flag`](https://github.com/ROCm/TheRock/blob/051414a1e21986b1d137fc1b0eadf92f39dbe242/build_tools/packaging/python/tests/aggregate_index_test.py#L838-L880)
only verifies that `argparse` rejects unknown arguments. The workspace test
guidelines classify tests of framework behavior as blocking test sprawl.

**Required action:** remove this test. Keep CLI tests where they exercise this
tool's own validation, exit-code, or output contract. While editing the file,
consider consolidating the repeated validate/generate/main cases so each layer
adds distinct behavioral coverage. In particular, the permissive/strict/missing
package matrix is repeated through `validate_product_indexes`,
`generate_outputs`, `main generate`, and `main validate-content`; keep the
exhaustive matrix at the core behavior layer and only a happy path plus error
translation at each CLI boundary. The malformed/unhashable YAML and three
determinism groups have similar consolidation opportunities.

Organizing the tests into classes or separate files for manifest parsing,
content validation, rendering/output, and CLI behavior would communicate the
coverage better than a large explanatory comment at the top. Add comments only
where two cases look redundant but protect materially different invariants.

### IMPORTANT: The documented `validate-content` command cannot run

The module usage example at
[`aggregate_index.py`](https://github.com/ROCm/TheRock/blob/051414a1e21986b1d137fc1b0eadf92f39dbe242/build_tools/packaging/python/aggregate_index.py#L37-L43)
omits `--stream`, but the argument is required at
[`main()`](https://github.com/ROCm/TheRock/blob/051414a1e21986b1d137fc1b0eadf92f39dbe242/build_tools/packaging/python/aggregate_index.py#L1304-L1326).
Copying the documented command exits with an argparse error.

**Recommendation:** add a concrete stream to the example and add a lightweight
help/example check only if it validates project-owned documentation rather than
argparse itself.

### IMPORTANT: Update the PR's test metadata

The PR reports 82 tests, while the current file collects 83. It also omits the
test duration required by the workspace review guidance for new tests. The
Linux CI log shows the full `build_tools` suite completing in 55.72 seconds;
the aggregate-index cases themselves execute quickly, approximately 0.4
seconds in that job.

**Recommendation:** update the count and include the targeted test duration.
Also explain why this 2,958-line initial implementation is best reviewed as one
PR, since the repository guidance asks for justification above 1,000 lines.

### SUGGESTION: Start newly introduced schemas at version 1

The manifest, route, and validation schemas all start at version 2, but no
version 1 of these artifacts exists in the repository and no migration path is
implemented. Unless an external v1 consumer already shipped, starting at 1
makes the public contract easier to explain.

### SUGGESTION: Consolidate packaging dependency declarations later

`packaging==25.0` now appears in the root `requirements.txt`,
`requirements-test.txt`, and
[`build_tools/packaging/requirements.txt`](https://github.com/ROCm/TheRock/blob/main/build_tools/packaging/requirements.txt#L1-L5).
The root declaration is not simply removable in this PR: general workflows
install the root requirements, unit CI installs `requirements-test.txt`, and
the release promotion/upload scripts document the packaging-specific file.
However, three independently pinned copies can drift.

Track a follow-up to establish one canonical pin with context-specific
requirements including it, or give the aggregate-index tool a deliberately
minimal dependency set that TheRock-Infra installs. This is cleanup rather than
a reason to block the feature.

### SUGGESTION: Document intent on the longer validation helpers

Public functions have docstrings, but several substantial private helpers only
expose mechanics. `_parse_python_index`, `_package_name_from_root_href`, and the
strict-completeness branch in `validate_product_indexes` would benefit from
short comments/docstrings explaining the invariant they protect and why the
edge cases are rejected. Expand the existing `validate_product_indexes`
docstring to describe `stream`, `strict_completeness`, and
`require_all_manifest_packages`; those flags are the most consequential API in
the module.

### SUGGESTION: Prefer positive boolean names if explicit false forms are needed

The Python style guide demonstrates `argparse.BooleanOptionalAction`, but using
it directly for `--allow-unpublished` would create the awkward double-negative
`--no-allow-unpublished`, whose behavior is identical to the current default.
For a one-way safety override, `store_true` is defensible. If workflow callers
need explicit true/false arguments, first rename the concept positively (for
example `--require-all-manifest-packages` with an explicit negative form), or
preferably remove permissive generation as recommended above. Do not apply
`BooleanOptionalAction` mechanically to both safety flags.

### SUGGESTION: Clean up temporary files on write failure

`_write_text_atomic()` uses `NamedTemporaryFile(delete=False)` and does not
remove the temporary file if `write`, close, or `replace` fails. Wrap the
temporary lifecycle so failures preserve the original target and remove the
orphaned `.tmp` file when possible.

## CI and Verification Evidence

* `pre-commit`: passed.
* Gitleaks: passed.
* Unit Tests on Ubuntu 24.04: passed; `build_tools` reported 1,943 passed, 8
  skipped, and 122 subtests passed in 55.72 seconds.
* Unit Tests on Windows Server 2022: passed.
* The aggregate-index tests are present in the CI log and pass on Linux; CI also
  reports 97.19% statement coverage for `aggregate_index.py`.
* Manual manifest-only generation for `nightly` produced 111 routes: route JSON
  18,241 bytes, aggregate HTML 7,928 bytes, validation JSON 30,553 bytes.
* ROCm/rockrel prerelease run 31840058334 completed successfully for the
  RC/stable architecture family set represented by the manifest, including
  successful Linux and Windows Python-package build and publication jobs. This
  supports the stream-availability choices, but does not validate the resulting
  product-local index contents or ownership routes.
* Multi-Arch CI was still in progress at review time. The already-completed
  compiler-runtime stages passed on Linux and Windows.

## Conclusion

The code is defensive and well tested at the unit level, but the public-index
safety properties currently depend on callers remembering the right combination
of optional flags. Resolve that API boundary, validate the real manifest data,
and prove the CloudFront consumer/size contract before treating these artifacts
as deployable.

**Approval status: CHANGES REQUESTED**

Generated with Codex
