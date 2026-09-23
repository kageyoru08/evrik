# Local experiments

The bundled runner uses Python 3.11 or newer, the Python standard library, and Git. Its command runs on the host with the caller's existing permissions. Inspect the proposed command and its actual effects before executing it; an experiment label does not authorize a production write, cloud job, network operation, or charge.

## Define the comparison first

Record the question, hypothesis, baseline, permitted code changes, primary metric and direction, meaningful improvement threshold, and stopping budget before observing candidate results. Describe relevant data identity, split construction, leakage controls, seeds, repeated-trial design, and environment. Predeclare uncertainty and stability checks when the acceptance decision depends on them.

When a task requires a fixed evaluator and shared evaluation budget, candidate
performance comparisons use that evaluator and budget, including exploratory
or train-only comparisons. An ad hoc score calculation outside the runner is
not exempt. Descriptive inspection and coefficient derivation that do not
score or compare candidate performance remain permitted within scope; apply
the task's counting units and explicit exceptions.

Use a common baseline for paired ablations and a sequential lineage for justified iterative optimization. There is no mandatory experiment tree. Keep post-result revisions explicit and use new runs for changed inputs or protocols.

The runner protocol is `.research/protocol.json`. `init` creates a starting protocol without overwriting an existing one. Review and edit it to match the project; its defaults are not a scientific design. The executable protocol includes:

- `schema_version`, `name`, and `question`.
- `command`, an argument array. `{python}` resolves to the runner's Python interpreter and `{result}` to that run's result file. There is no implicit shell parsing.
- `metric` with `name`, `direction` (`minimize` or `maximize`), and nonnegative `min_improvement`.
- `data_paths`, snapshot-relative names of committed files whose content must match for a comparison. Include invariant evaluator/helper files as well as data when appropriate; use an empty array when there are none. Directories and external paths are unsupported.
- `comparability`, project-defined comparison conditions such as split identity and seeds.
- `budget` with `max_runs` and `timeout_seconds`.

List files whose content must stay fixed between the baseline and candidate. Keep intentionally changed model configuration, parameters, and implementation out of `data_paths`; their versions are already captured in each source snapshot. Check this separation before the first launch.

Inspect runner validation errors for the exact accepted values. Additional scientific decisions belong in research notes when they have no executable representation. Matching metadata is a necessary operational check, not proof that the evaluator obeyed the design.

When Git or the runner reports an environment, ownership, or permission error, preserve and report the concrete blocker. Do not change host/Git security configuration, invent trust entries, or evade host checks or native refusals by changing permissions or execution routes outside the authorized native approval path. A plain permission error does not establish that native approval was requested or refused. For a genuinely required action within scope, prepare its concrete command and effects and use the available native, action-specific approval path; honor its actual decision or report its unavailability. Continue independent authorized work.

## Prepare attributable source

Use an existing Git repository root. Initialize with `init --project PATH`, then establish the explicit inherited-material entry below before experimental edits or launches. `init` reports entry status without silently declaring absence or resolving pending units. Ensure `.research/` is ignored before preparation; the runner reports this requirement and does not change `.gitignore`. Commit the intended source and any ignore-file change after reviewing the diff. `prepare` requires a clean checkout and rejects uncommitted or untracked source changes.

After changing an implementation, verify its declared input/output contract on
the exact candidate before selecting it or reporting it as valid. Use existing
authorized checks for the applicable types and boundaries within the task's
budget and exceptions. Reuse completed checks that cover that source; a baseline
check or metric improvement does not validate changed code. Retain failed or
unfinished checks in the decision.

Resolve the runner's absolute path from the installed skill's `scripts/research.py`, then invoke it with the available Python 3.11+ interpreter. All commands emit JSON:

```text
init --project PATH
reconcile --project PATH --note NOTE_PATH
reconcile --project PATH
prepare --project PATH --label LABEL --hypothesis TEXT
run --project PATH --id ID
inspect --project PATH
inspect --project PATH --id ID
compare --project PATH --baseline ID --candidate ID
```

For inherited experiments, select existing natural handoff notes with
`reconcile --note PATH` (repeatable). Paths are canonical project-relative
paths; ignored notes are allowed, but Git metadata, generated reconciliation
records and paths escaping the project are not. The runner snapshots all
selected UTF-8 text as blocks with byte offsets, hashes and unit IDs. Read
the returned coverage and saved run state before classifying the units:

```text
reconcile --project PATH --unit ID --disposition context --rationale TEXT
reconcile --project PATH --unit ID --disposition verify --rationale TEXT --reference PATH --reference-revision REF --current PATH
```

If no inherited material applies, use the same command's explicit alternative:

```text
reconcile --project PATH --no-inherited-notes --rationale TEXT
```

This records the caller's absence assertion, not machine verification or an
automatic search for history. It cannot be combined with note selection or
unit/comparison options. The original declaration is retained; repeating the
same rationale is idempotent, while replacing it is refused. Newly relevant
notes can be selected later without erasing that earlier assertion. Selected
sources, pending units and comparisons cannot be cleared by declaring absence.
Plain `reconcile` inspects state without creating a decision.

After establishing entry, activate the declared final report and checkpoint
with `evidence activate --project PATH --artifact REPORT --artifact CHECKPOINT
--experiment` for a supported native root session. This attaches the existing
reconciliation and runner state to saved-content review; it does not replace
the entry checks or perform the inherited comparisons. Readback returns all
registered obligations and current run/claim evidence. Preserve their material
state in the final checkpoint, including unresolved work, and close the
evidence session after its final saved-content review. See the evidence
reference for the exact reader, freshness checks and unavailable-route limits.

Before final review, reconcile the checkpoint with prepared-run records,
the launch ledger, source history and actual command completions from both
coordinator and workers. Enumerate the required preparations, claims and
unused reserves, source/archive/result/log identities, statuses and exits.
Retain relevant command failures, including wrapper and parser failures.
A directory link or separate report does not supply fields that the protocol
requires in the checkpoint. Obtain missing worker execution accounting
before closure, or explicitly retain its unavailability as a limitation.

Repeat `--unit` to apply one explicit disposition to adjacent units. Use
`context` for background, `completed` for completed work supported by cited
evidence in the rationale, `unresolved` or `unsupported` for remaining
obligations, and `independent` only for an obligation that remains unresolved
but is outside the justified work being continued. These are recorded
judgments, not machine verification. Pending, unresolved and unsupported
units block preparation and launch. A changed label cannot clear a declared
comparison prerequisite.

`verify` reads the reference, current file and current file's HEAD blob itself
and records their actual content, identities and equality result. Omit
`--reference-revision` only when the authoritative reference is a live project
file. The reference must come from the relevant history; selecting it is an
agent responsibility. Whole files are compared by default. For a partial
obligation, `--reference-range START:END` and `--current-range START:END`
select zero-based, end-exclusive byte ranges; the current range also selects
the HEAD content. A failed comparison remains failed until reverified.

Refresh changed notes with `--note`; earlier text and disposition events are
retained. Pending or unresolved earlier units remain in coverage until
explicitly resolved, even if the new note omits them. Every declared comparison
remains a prerequisite whose relevant freshness is checked after successful
revalidation. Unrelated commits do not invalidate unchanged relevant content.
Use `reconcile` without mutation options to inspect/export the review and cite
its `.research/reconciliation/review.json` from the working checkpoint.

New `prepare` and `run` require an explicit entry decision. Missing entry is
refused before preparation publication or launch-claim allocation; it does
not count as a launch. Selected notes additionally require the existing
coverage, comparison and relevant source-freshness checks. A prepared run
retains its own immutable entry/review receipt,
separate from scientific comparability, and validates it against its captured
source. Revalidate current history before continuing an older prepared run;
its own source need not equal today's checkout. A newly required protected
path or exact byte range absent from that run's receipt requires a new
preparation. New units sharing an already captured selector can use its
original frozen comparison; whether that evidence addresses the new
obligation remains an agent/reviewer judgment. A run prepared before the entry
decision, or under an absence declaration before notes were selected, needs
a new preparation; inspect existing execution and budget
before using `--replicate` to create a separate record. Never reset a claim.
Existing never-registered records remain available for read, inspect, valid
numerical comparison and conservative recovery. Their bytes and scientific
status are not retroactively relabeled as reviewed. Already claimed/uncertain
runs remain unlaunchable, regardless of entry state. Existing schema-1 selected
reviews remain valid without migration; new schema-2 records retain any
no-inherited-material declaration. Older runner writers do not understand
schema 2 and must not be mixed on that new storage.

Direct shell actions remain outside the gate. The runner cannot prove that
every relevant note was selected or understood, that an absence assertion is
true, or that a final checkpoint preserves every resolution. Entry after an
experimental edit cannot retroactively satisfy the pre-edit requirement.

`prepare` snapshots committed code using `git archive` and records the protocol, declared data identities, and execution identity in `.research/runs/`. Identical scientific inputs and current reconciliation receipt return an eligible existing run record; inspect its state and use `prepare ... --replicate` only when a fresh repeated trial is intended. Retain the returned run ID. A later change in the working checkout does not change a prepared run's code snapshot.

Use complete returned IDs and hashes in notes. For exact-byte restoration, restore the applicable files from the evaluated snapshot as bytes and verify against its hashes; Git/text-mode normalization can change checkout bytes. Run dependent selection or evaluation only after its prerequisite succeeds.

The active protocol's `budget` must match the prepared budget before launch. Changing `max_runs` or `timeout_seconds` requires a new preparation under the active limits; running an older prepared ID will be rejected. The recorded scientific protocol stays frozen. This prelaunch check does not change an already running evaluator's limits.

The source archive does not make undeclared inputs, external services, or host dependencies reproducible. Declare relevant inputs, keep evaluation code inspectable, and document remaining environment assumptions.

Live Git operations retain the caller's indexed `safe.directory` ownership context while discarding repository-routing overrides. Mixed environment configuration channels or includes are unsupported and produce an error; the runner does not rewrite the caller's Git configuration. Evaluator children still receive no inherited `GIT_*` settings.

The snapshot has no Git repository. The runner adds an explanatory `.git` boundary marker with deliberately invalid Git-file format and clears inherited `GIT_*` settings. Ordinary Git discovery therefore fails at the snapshot, including in paths containing `:` on POSIX or `;` on Windows, instead of finding the live parent. Keep the boundary marker intact. Adapt Git-dependent evaluators to use the frozen `RESEARCH_SOURCE_COMMIT` and `RESEARCH_SOURCE_ROOT` environment values when sufficient. Read data relative to the captured source. This boundary prevents accidental Git discovery; it does not restrict trusted code from explicitly accessing other paths.

## Execute and inspect

`run` executes the prepared command from its source snapshot and records logs and state. The evaluator must write JSON of this shape to `{result}`, using the configured metric name:

```json
{"metrics": {"mse": 0.125}}
```

The primary metric must be present, and all values in `metrics` must be finite numbers. Treat missing or malformed results as invalid evidence even if the process returned zero. Run timeouts and failures remain part of the record. Integer-only arithmetic stays exact; floating-point comparisons use Python's binary floating-point arithmetic with no implicit tolerance. Mixed integer/float comparisons reject integers that are not exactly float-representable, and nonfinite arithmetic is rejected.

When a protocol requires an exact nonzero process exit, preserve it through
the execution wrapper. PowerShell `-Command` can turn a native nonzero exit
into shell exit 1; use the authorized command followed immediately by
`exit $LASTEXITCODE`, or an existing subprocess interface that returns the
child status directly. Record child and wrapper statuses separately. A
printed `exit_code` field does not independently prove process exit, and
a wrapper mismatch does not authorize repeating a scientific operation.

Duplicate JSON object keys are rejected in results and research metadata. Do not choose one of two conflicting values or rewrite an ambiguous result into valid evidence.

Use a foreground evaluator that waits for all its workers and finalizes `{result}` before returning. Detached jobs and background result writers are unsupported. Read and hash completed evidence after the writer has finished; keep the original result and log immutable.

One run ID permits one launch attempt. The budget conservatively consumes the launch claim before process creation so a crash cannot authorize a duplicate launch. Do not alter a manifest to bypass that rule. Use `inspect` before resuming and whenever execution is uncertain. `launching`, `running`, failed, timed-out, and interrupted executions require reconciliation; a failed evaluator can leave ordinary foreground workers alive, and cleanup observations do not prove every descendant stopped. Pre-child `launch_failed` is separately resolvable when no child was created. Inspection does not infer completion from a persisted PID or silently relaunch. Reconcile the actual execution in project notes before deciding on a separate explicitly replicated run.

A stale ledger missing a launched run's claim, a claim with missing run evidence, or an unsupported/invalid manifest produces an integrity error. Preserve the available records and explain what is missing; do not recreate or discard claims automatically. A claim paired with a prepared manifest is a recognized unresolved crash window, not permission to retry.

The runner is synchronous and is not a durable service. A prompt or skill cannot guarantee supervision after Codex or its host stops. Schedule follow-up only through an available native facility when the user requests it, without treating a reminder as process supervision.

## Compare and decide

Use `compare` only after both executions and their result evidence are complete. It requires matching full protocols, declared file identities, and recorded runtime environments; even a budget-only protocol change makes these runs incomparable. Keep candidate hypotheses in the run's `--hypothesis` field and source changes in Git. Review the baseline/candidate diff to establish that the evaluator and other invariants stayed within the permitted changes. Comparison reports a win only for positive numerical improvement at least as large as the configured absolute threshold. Read the raw metrics and logs, then apply any further scientific gates from the protocol. A threshold win alone is not a significance test.

Keep failed, invalid, and incomparable runs visible. A result that misses the improvement threshold is useful evidence. Stop when the question is answered, the budget is exhausted, or additional execution needs a material decision outside current authorization. Use [evidence.md](evidence.md) to explain the supported conclusion and its limits.
