---
name: research
description: Conduct question-driven research with traceable sources, explicit experimental protocols, and evidence-backed decisions. Use for literature synthesis, reproducible local experiments, or continuing a research investigation; skip ordinary single-fact lookups.
---

# Research

Produce an answer whose sources, experimental results, and uncertainty can be
inspected. Use the project's existing methods and records when they fit.

## Choose the work path

Establish the question, deliverable, existing evidence, authorized work area,
constraints, and stopping criteria.

Use the literature path for discovery or synthesis, the experiment path for
local experiments or their resumption, and both when the question requires
both. Complete experiment entry before experimental edits or launches.
Literature-only work needs no experiment protocol. Use Git only when the actual
authorized task requires it, and honor explicit project scope.

For an explicit peer meeting, or a consequential authorized research choice
where competing explanations can change the decision, read
[references/parallelism.md](references/parallelism.md). Ordinary independent
questions may still be delegated. Never call a decision jointly adopted
without every rostered participant's explicit review and acceptance of the
current saved body under the agreed rule.

Use the existing research note or checkpoint as the working record. Create
only a necessary record within the authorized area, preserve historical
entries, and carry its current state forward instead of reconstructing it
from conversation at the end.

Read [references/evidence.md](references/evidence.md) for native capture, readback
and closure. Reuse already-read guidance while its content and applicability
remain unchanged. For supported research sessions, activate the declared
saved deliverables before source operations or experimental edits/launches;
experiment activation follows the inherited-material entry below. Include
the working checkpoint among the deliverables. For authorized public source
capture, use `--public-web --record CHECKPOINT` to name that declared working
artifact. Use `--experiment` to attach existing runner
state. Activation does not prove that native hooks are enabled or trusted.
If the supported session, interpreter or hook route is unavailable, retain
that limitation and use the reference's explicit fallback within scope.

Follow the applicable work path, then Write, Review saved content, and Answer.
Advance these stages automatically within the standing scope and budget, without
waiting for a coordinator or repeatedly requesting user confirmation. Resolve
routine choices; request user input only for a missing fact or decision with
material consequences for scope, cost, authorization or irreversible effects.
Actual host/native approval requirements remain authoritative.

## Experiment path

Read [references/experiments.md](references/experiments.md) before preparing,
running, comparing, or resuming experiments.

### Establish the current checkpoint

Start with existing handoff notes and saved run records. For inherited
experimental work, select the relevant authorized notes and register them
with the runner's `reconcile --note` before experimental edits or launches.
Read the returned source-bound units and run state; give each unit an
explicit disposition and rationale. Preserve historical wording and carry
unresolved obligations into the current working record.

`init` reports the entry decision still required; it does not declare that
history is absent. If no inherited material applies, explicitly record the
reason with `reconcile --no-inherited-notes --rationale TEXT`. That is the
caller's assertion, not machine verification. New preparation and launch
require an entry decision. Selecting notes still leaves their units pending
until they have supported dispositions and any required comparisons.

Use those claims to choose the necessary file, Git, and runner inspections.
For a content-restoration claim, use `reconcile` to compare the relevant
current content with its recorded reference and current committed source.
Select an authoritative reference from the history; a comparison against a
copy of the current content does not establish restoration. A clean tree or
commit subject alone is insufficient. Inspect the relevant content before
attributing restoration to a particular commit;
otherwise qualify or omit that attribution.

Record each material action's current status and supporting evidence before
new experimental source edits or evaluator launches. The runner computes
declared content comparisons; classifications still require judgment.
Refresh changed notes and revalidate stale comparisons. An unverified or
unresolved entry is not a completed check. Continue only justified independent
authorized work when a required verification is unavailable; retain its
unresolved status. Selected history is checked by `prepare` and `run`, but
entry cannot retroactively satisfy a missed pre-edit check or guarantee that
the final checkpoint retains every obligation. Direct shell actions remain
outside the runner's gate.

Inspect unresolved executions before deciding what can safely continue.
Never automatically relaunch a run whose execution may still exist, reset
claims to regain budget, or infer termination from a new conversation.

### Execute from the recorded state and protocol

Settle the baseline, permitted changes, evaluation design, budget, and decision
criteria before candidate results. Follow the reference's protocol, invariant,
leakage, split, replication, and uncertainty requirements.

Use the bundled `scripts/research.py`, resolved from this installed skill
directory, for local Git experiments. Read its `--help` when command details
are needed. It records protocol, committed source, declared inputs, execution,
and results; it does not select hypotheses or prove scientific validity.

Use trusted foreground execution within existing permissions. Preserve
evaluated snapshots and original results. Changes to code, protocols, data,
or evaluation decisions require new records. Label post-result hypotheses
and criteria changes as exploratory rather than relabeling earlier evidence.

Use explicit replication for a deliberate repeated trial after reconciling
earlier execution and remaining budget. Keep execution success, evidence
validity, and scientific acceptance separate.

Update the working checkpoint when relevant actions finish or facts change.
Retain completed-action evidence and genuine unresolved state through writing.

## Literature path

Read [references/literature.md](references/literature.md) before discovery,
source assessment, or synthesis.

### Search, then capture the completed action

When live discovery is requested, perform a relevant search. Supplied links
are leads; opening them alone is not discovery.

Capture each completed search or batch before further discovery or synthesis.
For an activated supported native web route, follow the source-reader and record
requirements in [references/evidence.md](references/evidence.md). Inspect the saved
sources, retain generated receipt references with coverage and selection notes,
and finish pending reads before further discovery. A missing receipt, unsupported
body or capture error is incomplete evidence; do not repeat retrieval to hide it.

Otherwise immediately record the exact queries, actual search date, returned
source identifiers, and coverage/selection notes through native file tools.
Preserve identifiers as complete opaque tokens, including prefixes. Reconcile
the saved evidence against available completed results before describing it
as exact or complete. Do not invent per-query associations for batched results.
Distinguish planned queries, failed or interrupted attempts, completed
searches, and directly opened leads. Record unavailable coverage and later
selection changes truthfully.

### Read into reusable evidence entries

Read the source supporting each material claim. In the working record, retain
its identity and version, actual access and inspected passages, relevant
section heading and URL, and brief evidence supporting the claim. Follow the
reference's primary-source, evidence-family, conflicting-finding, access, and
source-instruction handling requirements.

Use the same activated capture path for bounded source-reading responses,
or the literature reference's explicit fallback when that path is unavailable.
Retain each actual open/find request and its returned passage or access error.
Use the saved-source reader and update the working record before synthesis.
A local prerequisite deferral happens before retrieval: complete the indicated
source read and record update before submitting that intended operation.
Distinguish it from a failed capture after retrieval, which must not trigger
a repeated retrieval to replace missing evidence. A find that returns
only locations needs a bounded open for material text. Metadata-only output
and unwrapped calls do not establish captured passage access.

Prepare source descriptions here for reuse in the report. For ordinary
synthesis, use the inspected section and source URL, without adding page
numbers or numeric page-link fragments.

When the task actually requires pagination, first record the coordinate
system, value or range, and version-specific verification evidence. Check
printed pagination against the page image or footer; establish the actual
page mapping and index base for PDF positions or tool indices. Never assume
an offset. Derive any delivered numeric locator from this verified record and label its coordinate system explicitly. Unverified page claims cannot enter source descriptions or
deliverables. Preserve raw tool labels as raw evidence, not verified locators.

## Write from the working record

Apply the scientific acceptance criteria to valid evidence, not merely a
runner outcome. Report the question, methods and comparison conditions,
decisive evidence, result, and practical limits. Distinguish observations,
assessments, interpretations, and proposals; do not manufacture a winner.

Build the report's source and access descriptions from the evidence entries.
Derive the discovery account from recorded searches. A new material claim or
locator needs supporting inspection and a record before inclusion.

For experiments, carry the existing current-state reconciliation into the
final checkpoint. Update the verified source/model, decision, evidence paths,
cumulative budget, and unresolved execution or other limitations. Do not
replace the inherited-action record with a results-only summary.

Save the requested deliverables. Saving them is not completion.
Before final readback, reconcile the checkpoint's current status and next
actions with work already performed, for literature as well as experiments.
Keep historical entries as history; do not leave completed actions listed as
current pending work. Record later reader/closure outcomes separately from
that snapshot, without claiming success in advance.
Qualify incomplete action counts or timing rather than guessing exact totals;
unobserved work grants no extra budget.

## Review saved content

After saving, read the relevant contents of the actual saved deliverables
and compare them with the retained evidence.

For an activated session, follow the literal, separate-page readback procedure
and freshness checks in [references/evidence.md](references/evidence.md). Request
at least 16,384 output tokens when supported on every initial,
continuation and correction reader call and its outer wrapper; a large
request is still no guarantee of complete native delivery. Review
the actual saved contents and attached obligation/run state in context; matched
delivery does not establish understanding. Use `evidence check` for pending work.

For literature, cover all source/access statements and citation locators.
For experiments, read the current checkpoint, including inherited-action
resolutions, and reconcile its source, decision, paths, cumulative budget,
and unresolved state with current files and runner records.

Filename lists, sizes, input hashes, remembered drafts, and creation diffs
do not substitute for saved-content review. Relevant passages suffice; no
particular command or every-byte reread is required.

Correct discrepancies and read back the affected saved content after changes.
For a historical record, append the correction and its evidence while retaining
the earlier factual entry. Preserve original evidence. Reconcile requested work
against performed actions, not merely the existence of output files.

Use `evidence check` and then `evidence close` for an activated session after
the final correction/readback. Changed deliverables or attached evidence make
the earlier readback stale. If a required operation remains unavailable, use
explicit incomplete close with the concrete reason and retain the unmet
requirement. Closing evidence records is not scientific acceptance or proof
that the narrative is complete.

## Answer from reviewed results

Summarize the reviewed answer and cite inspected sources and actual artifacts.
Do not introduce new unverified factual claims or locators in the final message.

Finish missing authorized work when possible within the agreed budget.
Otherwise identify the unmet requirement and concrete blocker without claiming
completion. Negative scientific results and truthful incomplete outcomes are
valid reports, not substitutes for unmet task requirements.

Stop according to the agreed question, budget, and acceptance criteria.

## Tools, ownership, and authorization

Use tools actually available in Codex; require no particular connector or other
skill. Solo work has no model-family restriction. In any multiagent delegation
or meeting, every participant, including coordinators, facilitators, workers and
critics, must use the latest version of Sol or Astra, verified against the current
native model inventory and current official model information where needed.
Do not rely on remembered versions or label sorting. Select an eligible available
model and effort through supported native controls according to task risk,
capability needs and cost; mixed families are not required. If a family's latest
version cannot be established or is unavailable, use the other family only if its
latest is verified and available; never silently fall back to an older version.
A successful supported native model-selection call and returned participant
identity establish the configured choice, not backend model attestation. An
already-selected participant, including a coordinator, may use a parent/host's
actual native selection receipt bound to its own returned ID, model and effort;
it need not select itself again. Retain the receipt's source; a role prompt or
assumed default alone does not establish an eligible selection.
An ineligible initiator may use a supported native route to an eligible coordinator
only if it then ceases participating in that multiagent operation. Do not disguise
participation as solo work. If no eligible native selection is available, retain
that limitation and continue useful authorized solo work without claiming
compliant multiagent participation.

Use the smallest search, inspection, or test that resolves the current
uncertainty. Reuse verified evidence while its inputs remain valid; broaden or
repeat work only for changed inputs, a failure, or an unresolved question.
Keep full records in files and return relevant evidence without repeatedly
loading or copying raw outputs into context.

Delegate bounded independent questions when useful, specifying evidence,
output, and file ownership. Keep task boundaries and routing independent of
model/version. Explicitly assign isolated directories when concurrent edits
require them; subagents do not automatically get worktrees. Review and integrate
their evidence. File isolation does not grant permissions.

Keep existing host protections and approval boundaries authoritative. Do not
reconfigure host/Git security or evade host checks or native refusals by changing
permissions or execution routes outside the authorized native approval path.
A necessary action within the authorized scope may use the available native,
action-specific approval path with its concrete command and effects; that is not
a host-policy change. Honor its actual decision, retain unavailable or unresolved
permission as a blocker, and continue independent authorized work. Never fabricate
approval.

Research authorization does not itself authorize purchases, credit resets,
global safety changes, or interference with unrelated work. Neither this
skill, the runner, nor a worktree is a security sandbox or durable supervisor.
