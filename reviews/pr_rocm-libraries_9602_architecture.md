# Architecture Review: ROCm/rocm-libraries#9602

* **PR:** [ROCm/rocm-libraries#9602](https://github.com/ROCm/rocm-libraries/pull/9602)
* **Issue:** [ROCm/rocm-libraries#9601](https://github.com/ROCm/rocm-libraries/issues/9601)
* **Branch:** `users/tony-davis/therock-ref-merge-base`
* **Base:** `develop`
* **Review type:** Architecture / dependency baseline selection
* **Reviewed:** 2026-08-17
* **State:** Merged on 2026-08-04 (this is a retrospective design review)

---

## Summary

The PR fixes one real problem: one workflow run now resolves a single concrete
TheRock SHA and passes it through all downstream jobs, eliminating within-run
drift. The pull-request selection policy, however, does not identify the
TheRock stack that the external repository was last validated with. It chooses
the newest TheRock commit whose **committer timestamp** is no later than the
external repository merge-base timestamp.

That is a chronological heuristic, not a repository synchronization
relationship. The code never reads TheRock's `rocm-libraries` gitlink and never
checks whether that gitlink is equal to or an ancestor of the PR merge base.
The existing TheRock bump and back-reference automation does record such a
causal relationship, so eliminating that mapping loses the strongest evidence
available.

---

## Behavior Comparison

There are two different "before" states worth separating. The multi-arch
workflow immediately before #9602 used live `main` in each job. The established
TheRock CI path separately used a hardcoded pin maintained by bump automation.

### Before #9602: multi-arch jobs could resolve different stacks

```mermaid
flowchart LR
    A["Setup starts<br/>ref: main"] --> T1["TheRock T1"]
    U["TheRock main advances<br/>T1 → T2"]
    B["Linux build starts later<br/>ref: main"] --> T2["TheRock T2"]
    C["Windows build starts later<br/>ref: main"] --> T2
    T1 --> S1["systems S1<br/>LLVM L1<br/>other pins"]
    T2 --> S2["systems S2<br/>LLVM L2<br/>other pins"]
```

Example: setup could configure against `T1`, then a TheRock merge moves `main`
to `T2` before a downstream job checks out its sources. The jobs belong to one
workflow run but do not necessarily build one source stack. #9602 correctly
fixes this part by resolving once and passing a concrete SHA everywhere.

### Existing pinned CI: stable, causal, but only as fresh as the bump-backreference process

```mermaid
flowchart LR
    M["rocm-libraries merge base M<br/>contains therock-ref = T0"] --> T0["TheRock T0"]
    T0 --> P0["rocm-libraries gitlink P0"]
    T0 --> S0["rocm-systems S0"]
    T0 --> L0["LLVM L0 + other pins"]
    P0 -->|"P0 is ancestor/equal"| M
    T0 -->|"one concrete SHA"| J["all CI jobs"]
```

At #9602's base, the recorded pin was TheRock `2d0da43`, whose
`rocm-libraries` gitlink was `a777282`. That pin was stale, but its meaning was
clear: it was a specific TheRock submodule bump commit recorded back into
rocm-libraries history. The staleness came from generated back-reference PRs
waiting for humans, not from an inability to represent the relationship.

### What #9602 changed it to: stable selection by time, without graph validation

```mermaid
flowchart LR
    B["PR base SHA"] --> MB["Find merge base M"]
    H["PR head SHA"] --> MB
    MB --> TS["Read M committer time τ"]
    TS --> Q["Newest TheRock main commit<br/>with commit time ≤ τ"]
    Q --> TT["Selected T_time"]
    TT --> J["all CI jobs use one SHA"]
    TT -. "not inspected" .-> P["rocm-libraries gitlink P?"]
    P -. "not compared" .-> MB
```

Concrete example from the demonstration run:

```text
M      = rocm-libraries 5bd9db7 (17:43 UTC)
T_time = TheRock       7c274d3 (17:06 UTC)
T_time's rocm-libraries gitlink = 1aa4641
1aa4641 is 18 commits behind M
```

This is deterministic enough to freeze the run, but it does not answer why
`7c274d3` is the validated baseline for `5bd9db7`. The arrows that would prove
that relationship are precisely the dotted, unimplemented part of the diagram.

### Recommended: lock once using the recorded bump relationship, then validate it

```mermaid
flowchart LR
    MB["PR merge base M"] --> PIN["Read recorded TheRock pin T<br/>from M"]
    PIN --> TREE["Read T's external-repo gitlink P"]
    TREE --> CMP{"Is P ancestor/equal to M?"}
    CMP -->|Yes| OUT["Emit T, P, M<br/>and use T for every job"]
    CMP -->|No| FAIL["Fail closed<br/>or require explicit override"]
```

The update loop should keep that recorded relationship fresh:

```mermaid
flowchart LR
    P1["rocm-libraries develop P1"] --> BP["TheRock submodule bump PR<br/>P0 → P1"]
    BP --> CI["Test TheRock stack<br/>P1 + systems + LLVM + others"]
    CI -->|Pass and merge| T1["TheRock commit T1"]
    T1 --> BR["Generate back-reference PR<br/>therock-ref = T1"]
    BR --> V["Verify scope, main ancestry,<br/>gitlink, and CI result"]
    V -->|Auto-approve / auto-merge| R1["Future rocm-libraries merge bases<br/>record T1"]
```

This gives the desired behavior in plain terms: a PR stays on the baseline
recorded in its merge-base history; bump PR automation advances that baseline
only after TheRock validates a synchronized stack; and all jobs within the run
use the same SHA.

---

## Explicit Git-History Examples

The examples below use these symbols:

- `M`: the external repository PR merge base;
- `Tn[R=Pn]`: TheRock commit `Tn` whose external-repository gitlink is `Pn`;
- `P <= M`: `P` is equal to or an ancestor of `M`; and
- `pin(Tn)`: an external-repository commit recording `Tn` as its CI baseline.

The horizontal order is **git parent/child history**. Times in parentheses are
committer timestamps, which are metadata and are not the graph itself.

### Case 1: The timestamp heuristic happens to choose a compatible stack

```text
rocm-libraries develop:
    P0 -------- P1 -------- M -------- H (PR head)
                 \_________/
                    P1 <= M

TheRock main:
    T0[R=P0] --- T1[R=P1] --- T2[R=P1, systems/LLVM advanced]
    (08:00)      (09:00)      (09:30)

M committer time: 10:00
timestamp result: T2
```

This case works because `T2` happens to contain `P1`, and `P1` is an ancestor
of `M`. TheRock CI also had an opportunity to validate the `T2` source bundle.
The problem is that the resolver does not check either fact—it succeeds here by
the normal cadence of the two repositories, not by enforcing an invariant.

### Case 2: Normal integration lag excludes the synchronization commit

```text
rocm-libraries develop:
    P0 ---------------- M ---------------- H
                       (10:00)

TheRock main:
    T0[R=P0] --- T1[R=P0] ---------------- B1[R=M]
    (08:00)      (09:55)                    (11:00)
                    ^                          ^
                    |                          |
          timestamp chooses this      bump CI validates M here
```

`B1` cannot exist until after `M` exists and a bump PR has run. Therefore a
rule requiring `TheRock time <= M time` necessarily excludes the commit that
most directly records and validates `M`. It selects `T1`, a stack tested with
`P0`, and describes the result using temporal skew rather than the actual
`T1[R=P0]` relationship.

This is not an exotic failure; it is the expected ordering of asynchronous
repository synchronization.

### Case 3: Commit timestamps do not define TheRock history order

Git permits child commits to have timestamps older than their parents—for
example after cherry-picking, importing, or deliberately preserving dates:

```text
TheRock main graph (parent order):
    T0[R=P0] -------- T1[R=P1] -------- T2[R=P2]
    date 08:00         date 10:30        date 09:30
                                           ^
                                           child of T1 despite older timestamp

External merge base M date: 10:00
```

A query filtered only by `until=10:00` can admit `T2` by timestamp even though
`T2` is topologically after `T1`, whose timestamp is outside the cutoff. In
other words, "commit date no later than M" does not mean "state of main that
existed when M was created." Git ancestry is authoritative; dates are labels
on graph nodes.

### Case 4: Similar timestamps can hide divergent source history

```text
rocm-libraries:
                         M --- H              (develop / PR history)
                        /
    P0 ----------------+
                        \
                         Q1 --- Q2             (release or divergent history)

TheRock main:
    T0[R=P0] --- T1[R=Q2]
                  (timestamp is just before M)
```

The timestamp resolver accepts `T1`. But `Q2` is not an ancestor of `M`, so
TheRock validated `T1` with a different rocm-libraries history than the PR's
baseline. A graph-aware resolver rejects it:

```text
compare Q2...M => diverged
eligibility     => false
result          => fail closed or use a different recorded baseline
```

This is why merely reading the gitlink is insufficient; the gitlink must be
compared with the caller's merge base.

### Case 5: "Newest compatible gitlink" is valid but can still move between reruns

Suppose `M` already contains both `P0` and `P1`, but TheRock has not caught up
when the PR first runs:

```text
rocm-libraries develop:
    P0 -------- P1 -------- M -------- H
    P0 <= M     P1 <= M

TheRock at PR run 1:
    B0[R=P0]
    newest eligible => B0

TheRock later, same unchanged PR:
    B0[R=P0] -------- B1[R=P1]
                       ^ bump lands after run 1
    newest eligible => B1
```

This algorithm is much safer than timestamps because both candidates have a
proven ancestry relationship. It still violates the promise that an unchanged
PR keeps the same baseline: run 1 selects `B0`, while run 2 selects `B1`.

Avoiding that movement requires either durable per-PR state or a mapping already
present in immutable history. The recorded back-reference pin provides the
latter without adding a separate database.

### Case 6: A pin recorded at the merge base stays frozen until the PR resyncs

```text
TheRock main:
    T0[R=P0] ---------------- T1[R=P1]
       |                          |
       | bump automation          | later bump automation
       v                          v

rocm-libraries develop:
    P0 --- pin(T0) --- P1 --- M -------- pin(T1) --- D
                               \
                                H1 --- H2            (unchanged PR ancestry)
```

For the PR whose merge base is `M`:

```text
run 1: read pin at M => T0
run 2 after T1 lands: merge base is still M => T0
run 3 after merging/rebasing develop to D: new merge base D => T1
```

This has exactly the stability semantics sought by #9602. The baseline changes
only when the PR author changes the branch's relationship to the base branch.
Unlike the timestamp method, the selected SHA is the result of an explicit bump
feedback edge stored in git history.

### Case 7: Validation makes a recorded pin fail safely if automation is wrong

A stored pin should be evidence, not blindly trusted:

```text
rocm-libraries merge base:
    P0 -------- M, containing pin(Tbad)

TheRock Tbad:
    Tbad[R=Q2, systems=S7, LLVM=L9]

ancestry check:
    Q2 <= M ?  NO (diverged)
```

Expected resolver behavior:

```text
ERROR: TheRock Tbad pins rocm-libraries Q2, which is not an ancestor of M.
       Refusing to choose an unvalidated baseline.
       Correct the bump pin or provide an explicitly validated override.
```

The current implementation would never notice this mismatch. The proposed
design logs `Tbad`, `Q2`, and `M`, then stops before expensive build jobs start.

### Resulting behavior matrix

| Design | Uses a causal git relationship? | Stable for unchanged PR? | Detects divergence? | Main failure mode |
|---|---:|---:|---:|---|
| Per-job live `main` | No | No, even within one run | No | Jobs build different stacks |
| One SHA by merge-base timestamp (#9602) | No | Usually | No | Chronological approximation is mistaken for validation |
| Newest TheRock commit with compatible gitlink | Yes | No, if a later eligible bump lands | Yes | Baseline advances between reruns |
| Pin recorded at merge base, no validation | Yes, by convention | Yes | No | Automation error is consumed silently |
| Pin recorded at merge base + gitlink ancestry validation | Yes, enforced | Yes | Yes | Stale pin, handled by bump automation/SLA |

---

## Overall Assessment

**Status: CHANGES REQUESTED** (follow-up/replacement required because the PR is
already merged)

The per-run locking should be kept. The timestamp-based automatic selection
should not be treated as a validated dependency baseline and should be replaced
before it becomes the common policy for other external repositories.

---

## Detailed Findings

### BLOCKING: The selection rule does not prove that the selected stack was validated with the PR baseline

[`resolve_ref()`](https://github.com/ROCm/rocm-libraries/blob/a69d3716d5709093349679e13b6ffb8a850e824a/.github/scripts/resolve_therock_ref.py#L173-L218)
does the following for a pull request:

1. Find the external repository merge base.
2. Read that commit's committer timestamp.
3. Ask for the first `ROCm/TheRock@main` commit at or before that timestamp.

There is no lookup of TheRock's `rocm-libraries` submodule entry and no ancestry
comparison in `ROCm/rocm-libraries`. Consequently, the returned SHA means only
"nearby in wall-clock time." It does not mean "the stack that incorporated and
validated this repository baseline."

The PR's own demonstration makes the gap concrete:

| Item | Commit | Evidence |
|---|---|---|
| rocm-libraries PR merge base | [`5bd9db75e640`](https://github.com/ROCm/rocm-libraries/commit/5bd9db75e64032aec711661ca8965a5e53ccfa18) | Committed 2026-07-20 17:43 UTC |
| TheRock commit selected by the resolver | [`7c274d31805e`](https://github.com/ROCm/TheRock/commit/7c274d31805e8ee90b8b845cd6eb2f12728ebce3) | Committed 2026-07-20 17:06 UTC |
| `rocm-libraries` gitlink in that TheRock commit | [`1aa464152f7b`](https://github.com/ROCm/rocm-libraries/commit/1aa464152f7ba1bbb762f7e0d81388b3f9742062) | 18 rocm-libraries commits behind the merge base |
| Next TheRock submodule bump containing the merge base in its ancestry | [`cb90066183b9`](https://github.com/ROCm/TheRock/commit/cb90066183b93a80ca4d8ee7b88e7e4bdf3c740b) | Bumped the gitlink to `3b121fd`, five commits after `5bd9db7` |

The selected TheRock commit may be a usable stack, and TheRock main should have
tested its own gitlinks. What the resolver cannot establish is that it is the
appropriate last-validated stack for `5bd9db7`. In particular, a synchronization
commit that incorporates an external-repository commit necessarily happens
*after* that external commit; an `at or before the external commit time` cutoff
systematically excludes the synchronization event that supplies the evidence.

Commit timestamps are also not graph ordering. Cherry-picks, rebases, delayed
merges, and rewritten committer dates can all make chronological proximity
diverge from repository ancestry.

**Required action:** Replace the timestamp mapping with an explicit, validated
mapping. The preferred design is to use the TheRock ref recorded in the
external repository at the PR merge base, then validate it against TheRock's
gitlink. If a fully dynamic resolver is retained, it must inspect TheRock's
submodule history and prove the selected gitlink is compatible with the merge
base; it must not infer compatibility from timestamps.

### BLOCKING: Falling back to live `main` violates the promised per-PR stability

When no TheRock commit is returned by the timestamp query, the resolver
[falls back to the live tip](https://github.com/ROCm/rocm-libraries/blob/a69d3716d5709093349679e13b6ffb8a850e824a/.github/scripts/resolve_therock_ref.py#L202-L218)
and merely emits a warning. The tests explicitly preserve this behavior.

This is the exact failure mode the PR is intended to prevent: rerunning an
unchanged PR can select a different TheRock commit. It also converts an inability
to establish a baseline into a green build against an unvalidated choice.

**Required action:** Fail closed when no eligible baseline can be established.
Require an explicit override or a repaired baseline mapping instead of silently
switching to live `main`.

### IMPORTANT: The resolver does not emit an auditable decision trace

The successful demonstration job logged the input SHAs and only the final
output:

```text
BASE_SHA: 5239ffcde0ed9af3290d9b40da8e3a7884375f3f
HEAD_SHA: cb120a28ecccf941bac93663f3721d38040ef63b
INFO:root:Setting github output:
{'therock_ref': '7c274d31805e8ee90b8b845cd6eb2f12728ebce3'}
```

The step summary is useful after success, but it is not a live diagnostic and
will not explain a failure before summary generation. There is no trace of the
mode, discovered merge base, cutoff, candidates considered, submodule gitlink,
ancestry result, or fallback decision.

**Recommendation:** Log each decision input and invariant check as it happens.
At minimum log the event/mode, source repository, base/head, merge base, selected
TheRock candidate, candidate gitlink for the external repository, ancestry
comparison result, and the final reason for selection or rejection. Do not log
the token.

---

## Recommended Design

### Preferred: preserve the back-reference pin and automate its maintenance

The existing chain already encodes the relationship that the resolver needs:

1. A TheRock bump PR advances the `rocm-libraries` gitlink and runs TheRock CI
   with the complete set of pinned sources.
2. After that bump merges, [`bump_automation.py`](https://github.com/ROCm/TheRock/blob/main/build_tools/github_actions/bump_automation.py)
   creates a rocm-libraries PR that records the exact merged TheRock commit in
   `.github/actions/ci-env/action.yml`.
3. A rocm-libraries PR merge base therefore contains the last accepted TheRock
   baseline known at that point in repository history.

[rocm-libraries#10558](https://github.com/ROCm/rocm-libraries/pull/10558) is an
example: TheRock commit `f5a34f5` bumped its `rocm-libraries` gitlink to
`67811f1`, and the generated back-reference PR updates the CI pin to that exact
TheRock commit. The fact that this PR remained open is an automation/ownership
latency problem, not a reason to discard the causal mapping.

Automate approval/merge for these narrowly scoped PRs after verifying:

- the proposed TheRock SHA is on `ROCm/TheRock@main`;
- its external-repository gitlink matches the bump that triggered the PR;
- that gitlink is an ancestor of or equal to the destination branch;
- required TheRock CI for the bump succeeded; and
- the PR changes only the expected pin.

Developer rotations can own failures and a maximum-lag SLA rather than routine
manual merging.

### If dynamic resolution is required

Define the policy in graph terms:

- Let `M` be the external repository PR merge base.
- For a candidate TheRock synchronization commit `T`, read the external repo
  gitlink `P` from `T`.
- Require `P == M` or `P` to be an ancestor of `M` (with the exact rule stated
  explicitly).
- Select among eligible **submodule bump/validated milestone commits** by a
  documented git-history rule, not by timestamps.
- Fail if no eligible validated candidate exists.

The workflow should output all of `T`, `P`, and `M`, so downstream logs show the
validated relationship rather than only the final TheRock SHA.

---

## Validation Performed

- Inspected the PR, issue, full diff, reviews, comments, and all reported PR
  checks.
- Inspected the pull-request demonstration run `29780090396`, including the
  `Resolve TheRock ref` job log.
- Queried the gitlink stored by TheRock commit `7c274d3` and compared
  `1aa4641...5bd9db7` through GitHub's compare API (`5bd9db7` is 18 commits
  ahead).
- Inspected TheRock submodule bump history around the demonstrated merge base.
- Ran the currently merged resolver tests locally:
  `D:\projects\TheRock\.venv\Scripts\python.exe -m pytest .github/scripts/tests/resolve_therock_ref_test.py -q`
  — **11 passed in 0.33s**. These tests validate the implemented timestamp
  policy; they do not validate a gitlink/ancestry policy.

---

## Conclusion

The answer to the central question is **no**: PR #9602 does not select TheRock
by comparing TheRock's external-repository submodule pin with the PR merge
base. It selects by committer time. Keep the single-SHA-per-run plumbing, but
replace the selection policy with the bump-derived pin or another explicit
git-history invariant before propagating it across ROCm repositories.

---

*Review generated with OpenAI Codex.*
