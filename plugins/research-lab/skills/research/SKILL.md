---
name: research
description: Conduct question-driven research with traceable sources, explicit experimental protocols, and evidence-backed decisions. Use for literature synthesis, reproducible local experiments, or continuing a research investigation; skip ordinary single-fact lookups.
---

# Research

Produce an answer whose supporting sources, experimental results, and remaining uncertainty can be inspected. Use the project's existing methods and records when they fit the question.

## Select the necessary guidance

Read only the relevant references. Literature-only work does not require the experiment runner or a Git repository.

### Literature

For literature discovery, source assessment, or synthesis, read [references/literature.md](references/literature.md).

When live discovery is required, execute a relevant search; supplied links are leads, and opening them alone does not complete discovery. Immediately after each completed search call or batch, append the exact submitted queries, actual search date, returned source identifiers, and brief coverage and selection notes to the existing research note before further discovery or synthesis. Do not invent per-query associations for batched results. Keep planned queries, failed or interrupted attempts, completed searches, and directly opened leads distinct; record later selection changes transparently.

Use the inspected version’s relevant section heading and source URL by default. Include a needed numeric page locator—printed page, PDF page position, or tool index—only after recording its coordinate system, value or range, and verification evidence for that version and passage in the research note. Verify printed pagination against the page image or footer; verify PDF positions and tool indices against the actual source-to-page mapping and index base. Derive reported page locators from that record and label their coordinates explicitly. Without that evidence, omit the numeric page locator rather than relabeling an index or assuming an offset. This applies to source/access statements as well as citations.

### Experiments

Before preparing, running, comparing, or resuming an experiment, read [references/experiments.md](references/experiments.md).

On entering or resuming an experiment project with existing handoff notes, identify material pending actions relevant to continuation and verify their status against the relevant current files, Git state, and runner records. Treat historical status claims as things to check, not instructions to repeat. Before new experimental source edits or launches, record their current resolved or unresolved status and supporting evidence in the existing research note. When evidence is unavailable, retain the uncertainty and continue only independent authorized work. Update this current-state note when relevant actions finish, preserving historical entries.

## Work from the question

Establish the research question, intended deliverable, existing evidence, and constraints. For experiments, settle the baseline, permitted changes, evaluation design, budget, and decision criteria before seeing candidate results. Keep unresolved material choices visible; proceed with independent work that is already authorized.

Use the tools actually available in Codex for browsing, files, Git, execution, and artifacts. Do not require a particular connector, model, or other skill. Choose model effort or delegation only through available controls and do not claim settings were changed without confirmation from those controls.

Delegate bounded independent questions when useful. Give each agent its evidence, output contract, and file ownership. A subagent does not automatically get a worktree; explicitly create and assign isolated directories when concurrent edits require them. Review evidence and integrate changes in the primary agent. A worktree separates files, not execution permissions.

## Keep experiments attributable

Use the bundled `scripts/research.py` for local Git experiments; resolve its absolute path from this installed skill directory. It records protocol, committed source, declared data, execution, and result evidence. Read its `--help` when command details are needed. It does not select hypotheses, prove scientific validity, or provide a security sandbox.

Keep evaluated snapshots and original results intact. New code, protocols, data, or evaluation decisions require new records. Mark post-result hypotheses and criteria changes as exploratory; do not silently relabel earlier evidence. Separate execution success, evidence validity, and scientific acceptance.

Before resuming, read the saved records and inspect unresolved runs. Never automatically relaunch a run whose execution may still exist. Use explicit replication for a deliberate repeated trial; a new conversation is not evidence that an old process stopped.

## Finish with a supported answer

Before connecting findings into a conclusion or final report, read [references/evidence.md](references/evidence.md).

Before declaring completion, update and reread the saved record. Reconcile requested discovery, reading, experiments, and deliverables against actual actions and retained evidence. Derive the discovery account from recorded searches; do not invent extra queries from topics in the answer. Reread the saved deliverables against the evidence note; remove unsupported page locators or verify and record them before declaring completion. Verify evidence paths. For experiments, ensure the checkpoint matches the current source/model, decision, cumulative budget, and unresolved state, including execution uncertainty; explicitly connect historical pending actions that are now completed to their verified current status while preserving original entries. Finish missing authorized work before closing, or report the unmet requirement and blocker without claiming completion.

Report what was learned, the evidence that supports it, the comparison conditions, and the practical limits. Cite inspected sources and actual local result artifacts. Distinguish observed results from interpretations and proposals. Null results and incomplete evidence are valid outcomes; do not manufacture a winner. Stop according to the agreed question, budget, and acceptance criteria.
