# Peer meetings

Use a meeting when requested or when competing explanations can materially
change an authorized research decision. Keep ordinary direct work and bounded
independent delegation available. An explicit meeting request needs reciprocal
discussion; delegated summaries alone do not satisfy it. If native participation
is unavailable, retain that limit and continue useful authorized work without
claiming that a meeting occurred.

## Establish the meeting

Settle the question, hard constraints, available evidence and access, actual
participants and addresses, file ownership, decision rule, and finite limits
before exchanging conclusions. Apply the [multiagent model rule](../SKILL.md#tools-ownership-and-authorization)
to every participant, including the facilitator: the roster must contain both
Sol and Astra. Two participants means the facilitator and one peer, one from
each family. Choose the smallest roster that covers the question's difficulty,
independent subproblems and material uncertainties. Add a participant only for
distinct useful analysis or verification, not to fill capacity or multiply votes.
Choose supported effort per role: bounded routine checks may need low or medium
effort; difficult reasoning, ambiguous evidence or consequential verification
can justify higher effort. Briefly record the role, family and effort choices
and why the headcount fits the task in the existing initial packet. Verify
actual selection receipts before relying on the roster; prompts alone do not
select a model. No particular connector, external consultation or Pro skill is
required. Bound participants, activations, messages, tools, evaluations and time
as applicable. Reserve capacity for final review and one revision.

[Stellar Colosseum, section 6](https://arxiv.org/html/2609.15983v2#S6)
reports complementary errors and improved critique-based selection between two
model runs on TCS-Bench. This motivates family diversity; it does not establish
independent errors or an accuracy gain for Sol/Astra meetings. Preserve evidence,
objections and task-specific verification instead of treating model diversity
or agreement as proof of correctness.

Start independent work when its inputs and native capacity are ready. Check
shared writes, tools and evaluation budgets as well as data dependencies. Review
a ready contribution without waiting for unrelated work; wait for the full set
only where the decision needs it. Use ordinary code for exact counting and
deduplication, retaining failed or missing contributions. Final joint adoption
still requires the complete roster's review of the same decision.

The facilitator is an equal substantive participant and the administrative
record keeper. It saves its own initial judgment and accepts criticism. It
cannot filter objections, overwrite another position, remove a dissenter,
dismiss a disputed material blocker alone or declare an unreviewed decision
joint. Every participant may request evidence, propose alternatives, revise a
position and withhold adoption. Shared standing does not expand permission.

Prefer one compact, identified initial task packet in the coordinator's existing
note, with the common question and evidence, allowed work area, excluded
operations, each peer's file ownership and remaining shared limits. Include
available native selection receipts, without the facilitator's preliminary
answer. Send a pointer to avoid duplicate copies; verify actual recipient
read/response as below. Read-only actions still have to satisfy these boundaries.
Include applicable entry prerequisites, their order and known resolved guidance paths.
Peers must finish required guidance in bounded reads before dependent scientific
operations; do not batch those operations with unread guidance. If ordinary local
guidance output is incomplete, read its missing required passages within the
existing budget and access restrictions. This does not repair an earlier entry
violation or authorize repeating source retrieval, evaluator or evidence-reader
actions; honor explicit stops. Use fresh context where supported; disclose
inherited exposure rather than claiming
cognitive independence. Each participant preserves its initial position,
supporting evidence and uncertainties before seeing others' conclusions. Keep
author-owned notes append-only: retain every earlier entry and append corrections
that identify the affected claim and supporting evidence. Prefer an end-of-file
append operation for later entries. Any permitted writing method must put new
material after the old end of file and verify that all prior bytes remain an
unchanged prefix; combine the write and verification in one authorized operation
where supported. Preserving an initial prefix alone does not preserve later
entries. Before publishing an append subject to a hard size limit, check that its
complete encoded suffix, including separators, fits the remaining space. A failed
write may leave bytes behind: inspect current content and preserve those bytes as
history. Never truncate or restore an earlier prefix to fit a limit; retain an
incomplete result if a valid correction cannot fit.

For a pre-existing append-only note, do not use a line-oriented patch, `Set-Content`,
`WriteAllText`, or another decode-and-rewrite operation: it can normalize existing
newline bytes. Use a binary append. Immediately before writing, require the current
byte length and SHA-256 to equal the values observed after the last read; otherwise
refuse without writing. With the designated single writer, open in binary append
mode, write only the complete UTF-8 suffix, flush and close, then verify that the
saved bytes equal the exact old prefix followed by the exact suffix. This compact
standard-library pattern is an executable control; fill the four inputs from the
current task rather than copying illustrative values:

```python
import hashlib, os
from pathlib import Path

path = Path(os.environ["APPEND_PATH"])
expected_length = int(os.environ["APPEND_EXPECTED_LENGTH"])
expected_sha256 = os.environ["APPEND_EXPECTED_SHA256"].lower()
suffix = os.environ["APPEND_SUFFIX"].encode("utf-8")
old = path.read_bytes()
if len(old) != expected_length or hashlib.sha256(old).hexdigest() != expected_sha256:
    raise SystemExit("stale append precondition; no bytes written")
with path.open("ab") as stream:
    stream.write(suffix)
    stream.flush()
    os.fsync(stream.fileno())
saved = path.read_bytes()
if saved[:expected_length] != old or saved[expected_length:] != suffix:
    raise SystemExit("append verification failed; preserve current bytes as history")
```

Use one writer for the shared
decision body, which may be revised subject to renewed review below; avoid
unnecessary new records.

## Exchange evidence and objections

Inspect the native declarations actually provided to each actor. Direct tools
may be separate from a nested registry such as `ALL_TOOLS`; absence there does
not prove direct absence. Use the declared schemas and invocation route, actual
returned peer addresses and supported follow-up for idle participants. Do not
guess a broadcast, resume or close API, inspect private capability caches, or
assume that sending a message wakes an idle peer.

Prefer direct peer messages for evidence-specific questions, objections and
responses. Before dispatch, save the complete material question, objection or
response in the author's existing note with its evidence reference and an identity that
later appends preserve. Send the exact text or a pointer to that identified
content. Administrative notices need no duplicate substantive record. When using
facilitator relay, record the workflow reason and any observed native limitation;
keep unknown availability unknown. Carry the complete attributed content or its
pointer and label the route as relay. The facilitator must not select or paraphrase away
objections during transport. A successful send, saved note or notification alone
does not prove consumption: the recipient must read the identified content and
record an evidence-specific response tied to it. Distinguish observed native
sends from shared-note consumption; saved content does not reveal an opaque
message envelope. Reuse existing peers for subsequent turns; do not create a new
user-facing task for every round or duplicate substantive dispatch.

Require a reciprocal critique/response cycle. Permit at most one additional
cycle for a material unresolved issue within the entry budget. A useful
objection names the claim or hard constraint, its material consequence, and
supporting evidence or a concrete missing verification. Preference alone is
not blocking. Agreement supported by evidence is valid; do not force opposition
or an answer change to make the meeting appear useful.

Resolve objections by correction, evidence-backed rebuttal or acknowledged
uncertainty. Record the disposition and any retained dissent. Repeated objections
refer to that disposition unless new evidence changes it. When materiality is
disputed, the facilitator cannot dismiss it alone. Headcount cannot establish
factual truth, override scientific acceptance or grant permission. A majority
tie rule is usable only if agreed before positions are known and only between
evidence-admissible options.

## Adopt one saved decision

Save a concise body containing the recommendation, decisive evidence identities,
objection dispositions, remaining uncertainty and practical limits. Identify its
exact revision/content, for example with the saved file's hash. Keep participants'
responses in separate author-owned notes so they do not change the reviewed body.

Every rostered participant, including the facilitator, independently reads that
same actual body and relevant evidence and states:

- whether its position and evidence are represented accurately;
- whether it endorses the recommendation;
- whether it accepts adoption under the agreed rule.

Default joint adoption requires explicit acceptance by all participants.
Representation acknowledgment alone is insufficient. A participant can accept
an admissible option while preferring another: record joint adoption with dissent
without calling it unanimous belief. No acceptance may be inferred from silence,
task completion or a facilitator's summary.

Any change to the body or its decisive evidence requires renewed review by
everyone; a concise diff plus relevant evidence may suffice. Bind renewed responses
to the current body and evidence identities. Missing
or stale review, withheld adoption or an unresolved material blocker leaves the
decision provisional or blocked when the finite budget ends. Do not restart
rounds, replace dissenters or invent responses to manufacture agreement. A jointly
accepted decision to defer can be a completed sound decision. Consensus never
guarantees that every possible defect has been found.

## Preserve evidence and close

Use the existing research records and applicable evidence, literature and
experiment paths. Automatic source capture is limited to supported root sessions;
peers inspect shared saved evidence, request omitted sources or use the documented
native fallback for their own authorized retrieval. They must not impersonate
the root or claim inherited automatic capture. Share one canonical evaluator
ledger and total budget; parallel work does not create extra launches or retries.

Track attempted operations as they occur. At existing note or response updates,
record compact participant subtotals by the applicable tool/category, including
failed/rejected attempts and the current update. Count every underlying
invocation once, including shell reads, every file patch, evidence commands,
sends, follow-ups and waits. Count tools invoked by a wrapper without charging
that wrapper again; a wrapper doing work without a nested tool counts once in
its applicable category. Before more work, check the remaining assigned or
verified shared allowance, keeping final review, a permitted revision and
closure reserved. Unknown usage is not extra allowance. Combine related reads
or concise attributed material items where permitted, preserving complete
objections and responses; do not add a separate ledger or a bookkeeping call
for every action. Reconcile subtotals against visible calls and returns before
reporting a shared total. Mark incomplete count or timing coverage as unknown or
qualified rather than guessing exact totals. Constrained budgets and the canonical
launch ledger still apply.
A normal wait timeout consumes its wait allowance and is not a failed send or
proof that a peer failed. Continue only within the remaining shared time and
permitted activations; never reset the deadline or blindly repeat an ambiguous
substantive action. Retain missing participation and unresolved execution truthfully.

Read the actual final saved body and participant responses after the last edit.
Report scientific correctness, reciprocal influence, the route actually used,
adoption and resource use separately. A correct answer cannot compensate for
missing participation, and agreement cannot compensate for invalid evidence.
Do not claim superiority or efficiency without an appropriate comparison.

Account for each participant's actual turn and owned execution before closing.
Completion, interruption and archival are distinct from process termination or
released native capacity; preserve uncertainty where observation ends. When
cleanup is authorized and the native app supports it, archive only known owned
completed tasks, retaining evidence and pending participants.
