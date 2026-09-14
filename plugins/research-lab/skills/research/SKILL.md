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
Literature-only work needs neither Git nor the experiment runner.

Use the existing research note or checkpoint as the working record. Create
only a necessary record within the authorized area, preserve historical
entries, and carry its current state forward instead of reconstructing it
from conversation at the end.

Follow the applicable work path, then Write, Review saved content, and Answer.
Continue ordinary authorized work without waiting for a coordinator to advance
these stages. Actual permission requests remain subject to their approval path.

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
When native tool composition is available, use the capture pattern in the
literature reference to save and verify the actual request, date, and response
within the same call before returning it. Link that verified receipt from the
working record and add brief coverage and selection notes; do not copy its
raw fields again.

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

Use the same native capture transaction for bounded source-reading responses.
Retain each actual open/find request and its returned passage or access error,
verify the saved response, then expose it for synthesis. A find that returns
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

Before drawing conclusions or writing the report, read
[references/evidence.md](references/evidence.md).

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

## Review saved content

After saving, read the relevant contents of the actual saved deliverables
and compare them with the retained evidence.

For literature, cover all source/access statements and citation locators.
For experiments, read the current checkpoint, including inherited-action
resolutions, and reconcile its source, decision, paths, cumulative budget,
and unresolved state with current files and runner records.

Filename lists, sizes, input hashes, remembered drafts, and creation diffs
do not substitute for saved-content review. Relevant passages suffice; no
particular command or every-byte reread is required.

Correct discrepancies and read back the affected saved content after changes.
Preserve historical entries and original evidence. Reconcile requested work
against performed actions, not merely the existence of output files.

## Answer from reviewed results

Summarize the reviewed answer and cite inspected sources and actual artifacts.
Do not introduce new unverified factual claims or locators in the final message.

Finish missing authorized work when possible within the agreed budget.
Otherwise identify the unmet requirement and concrete blocker without claiming
completion. Negative scientific results and truthful incomplete outcomes are
valid reports, not substitutes for unmet task requirements.

Stop according to the agreed question, budget, and acceptance criteria.

## Tools, ownership, and authorization

Use tools actually available in Codex; require no particular connector, model,
or other skill. Change effort or delegation settings only through available
controls and claim changes only when confirmed.

Use the smallest search, inspection, or test that resolves the current
uncertainty. Reuse verified evidence while its inputs remain valid; broaden or
repeat work only for changed inputs, a failure, or an unresolved question.
Keep full records in files and return relevant evidence without repeatedly
loading or copying raw outputs into context.

Delegate bounded independent questions when useful, specifying evidence,
output, and file ownership. Explicitly assign isolated directories when
concurrent edits require them; subagents do not automatically get worktrees.
Review and integrate their evidence. File isolation does not grant permissions.

Keep existing host protections and approval boundaries authoritative. Do not
reconfigure host/Git security, widen permissions, or reroute a denied action
to work around a failure. Report the concrete blocker and continue independent
authorized work. Never fabricate a protected-action approval.

Research authorization does not itself authorize purchases, credit resets,
global safety changes, or interference with unrelated work. Neither this
skill, the runner, nor a worktree is a security sandbox or durable supervisor.
