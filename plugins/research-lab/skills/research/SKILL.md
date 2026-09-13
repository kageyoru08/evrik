---
name: research
description: Conduct question-driven research with traceable sources, explicit experimental protocols, and evidence-backed decisions. Use for literature synthesis, reproducible local experiments, or continuing a research investigation; skip ordinary single-fact lookups.
---

# Research

Produce an answer whose supporting sources, experimental results, and remaining uncertainty can be inspected. Use the project's existing methods and records when they fit the question.

## Select the necessary guidance

- For literature discovery, source assessment, or synthesis, read [references/literature.md](references/literature.md).
- Before preparing, running, comparing, or resuming an experiment, read [references/experiments.md](references/experiments.md).
- When connecting findings into a conclusion or final report, read [references/evidence.md](references/evidence.md).

Read only the relevant references. Literature-only work does not require the experiment runner or a Git repository.

## Work from the question

Establish the research question, intended deliverable, existing evidence, and constraints. For experiments, settle the baseline, permitted changes, evaluation design, budget, and decision criteria before seeing candidate results. Keep unresolved material choices visible; proceed with independent work that is already authorized.

Use the tools actually available in Codex for browsing, files, Git, execution, and artifacts. Do not require a particular connector, model, or other skill. Choose model effort or delegation only through available controls and do not claim settings were changed without confirmation from those controls.

Delegate bounded independent questions when useful. Give each agent its evidence, output contract, and file ownership. A subagent does not automatically get a worktree; explicitly create and assign isolated directories when concurrent edits require them. Review evidence and integrate changes in the primary agent. A worktree separates files, not execution permissions.

## Keep experiments attributable

Use the bundled `scripts/research.py` for local Git experiments; resolve its absolute path from this installed skill directory. It records protocol, committed source, declared data, execution, and result evidence. Read its `--help` when command details are needed. It does not select hypotheses, prove scientific validity, or provide a security sandbox.

Keep evaluated snapshots and original results intact. New code, protocols, data, or evaluation decisions require new records. Mark post-result hypotheses and criteria changes as exploratory; do not silently relabel earlier evidence. Separate execution success, evidence validity, and scientific acceptance.

Before resuming, read the saved records and inspect unresolved runs. Never automatically relaunch a run whose execution may still exist. Use explicit replication for a deliberate repeated trial; a new conversation is not evidence that an old process stopped.

## Finish with a supported answer

Report what was learned, the evidence that supports it, the comparison conditions, and the practical limits. Cite source pages and local result artifacts. Distinguish observed results from interpretations and proposals. Null results and incomplete evidence are valid outcomes; do not manufacture a winner. Stop according to the agreed question, budget, and acceptance criteria.
