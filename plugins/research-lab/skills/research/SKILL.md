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

Start with existing handoff notes and saved run records. Carry material
pending actions relevant to continuation into the current part of the working
record as claims to verify, preserving their historical wording.

Use those claims to choose the necessary file, Git, and runner inspections.
For a content-restoration claim, compare the relevant current content with
its recorded reference and confirm that content in the current committed
source. A clean tree or commit subject alone is insufficient. Inspect the
relevant content before attributing restoration to a particular commit;
otherwise qualify or omit that attribution.

Record each material action's current status and supporting evidence before
new experimental source edits or evaluator launches. An initial unverified
entry is not a completed check. When verification is genuinely unavailable,
record the uncertainty and continue only independent authorized work.

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

Immediately after each completed search call or batch, append its exact
queries, actual search date, returned source identifiers, and brief coverage
and selection notes to the working record, before further discovery or
synthesis.

Copy identifiers as complete opaque tokens, preserving prefixes. Reconcile
the record against available completed results before describing it as exact
or complete. Do not invent per-query associations for batched results.
Distinguish planned queries, failed or interrupted attempts, completed
searches, and directly opened leads. Record unavailable coverage and later
selection changes truthfully.

### Read into reusable evidence entries

Read the source supporting each material claim. In the working record, retain
its identity and version, actual access and inspected passages, relevant
section heading and URL, and brief evidence supporting the claim. Follow the
reference's primary-source, evidence-family, conflicting-finding, access, and
source-instruction handling requirements.

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
