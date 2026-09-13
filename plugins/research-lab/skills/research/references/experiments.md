# Local experiments

The bundled runner uses Python 3.11 or newer, the Python standard library, and Git. Its command runs on the host with the caller's existing permissions. Inspect the proposed command and its actual effects before executing it; an experiment label does not authorize a production write, cloud job, network operation, or charge.

## Define the comparison first

Record the question, hypothesis, baseline, permitted code changes, primary metric and direction, meaningful improvement threshold, and stopping budget before observing candidate results. Describe relevant data identity, split construction, leakage controls, seeds, repeated-trial design, and environment. Predeclare uncertainty and stability checks when the acceptance decision depends on them.

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

## Prepare attributable source

Use an existing Git repository root. Initialize with `init --project PATH`; ensure `.research/` is ignored before preparation. The runner reports this requirement and does not change `.gitignore`. Commit the intended source and any ignore-file change after reviewing the diff. `prepare` requires a clean checkout and rejects uncommitted or untracked source changes.

Resolve the runner's absolute path from the installed skill's `scripts/research.py`, then invoke it with the available Python 3.11+ interpreter. All commands emit JSON:

```text
init --project PATH
prepare --project PATH --label LABEL --hypothesis TEXT
run --project PATH --id ID
inspect --project PATH
inspect --project PATH --id ID
compare --project PATH --baseline ID --candidate ID
```

`prepare` snapshots committed code using `git archive` and records the protocol, declared data identities, and execution identity in `.research/runs/`. Identical inputs return an existing run record; inspect its state and use `prepare ... --replicate` only when a fresh repeated trial is intended. Retain the returned run ID. A later change in the working checkout does not change a prepared run's code snapshot.

The active protocol's `budget` must match the prepared budget before launch. Changing `max_runs` or `timeout_seconds` requires a new preparation under the active limits; running an older prepared ID will be rejected. The recorded scientific protocol stays frozen. This prelaunch check does not change an already running evaluator's limits.

The source archive does not make undeclared inputs, external services, or host dependencies reproducible. Declare relevant inputs, keep evaluation code inspectable, and document remaining environment assumptions.

The snapshot has no Git repository. The runner adds an explanatory `.git` boundary marker with deliberately invalid Git-file format and clears inherited `GIT_*` settings. Ordinary Git discovery therefore fails at the snapshot, including in paths containing `:` on POSIX or `;` on Windows, instead of finding the live parent. Keep the boundary marker intact. Adapt Git-dependent evaluators to use the frozen `RESEARCH_SOURCE_COMMIT` and `RESEARCH_SOURCE_ROOT` environment values when sufficient. Read data relative to the captured source. This boundary prevents accidental Git discovery; it does not restrict trusted code from explicitly accessing other paths.

## Execute and inspect

`run` executes the prepared command from its source snapshot and records logs and state. The evaluator must write JSON of this shape to `{result}`, using the configured metric name:

```json
{"metrics": {"mse": 0.125}}
```

The primary metric must be present, and all values in `metrics` must be finite numbers. Treat missing or malformed results as invalid evidence even if the process returned zero. Run timeouts and failures remain part of the record. Integer-only arithmetic stays exact; floating-point comparisons use Python's binary floating-point arithmetic with no implicit tolerance. Mixed integer/float comparisons reject integers that are not exactly float-representable, and nonfinite arithmetic is rejected.

Duplicate JSON object keys are rejected in results and research metadata. Do not choose one of two conflicting values or rewrite an ambiguous result into valid evidence.

Use a foreground evaluator that waits for all its workers and finalizes `{result}` before returning. Detached jobs and background result writers are unsupported. Read and hash completed evidence after the writer has finished; keep the original result and log immutable.

One run ID permits one launch attempt. The budget conservatively consumes the launch claim before process creation so a crash cannot authorize a duplicate launch. Do not alter a manifest to bypass that rule. Use `inspect` before resuming and whenever execution is uncertain. `launching`, `running`, failed, timed-out, and interrupted executions require reconciliation; a failed evaluator can leave ordinary foreground workers alive, and cleanup observations do not prove every descendant stopped. Pre-child `launch_failed` is separately resolvable when no child was created. Inspection does not infer completion from a persisted PID or silently relaunch. Reconcile the actual execution in project notes before deciding on a separate explicitly replicated run.

A stale ledger missing a launched run's claim, a claim with missing run evidence, or an unsupported/invalid manifest produces an integrity error. Preserve the available records and explain what is missing; do not recreate or discard claims automatically. A claim paired with a prepared manifest is a recognized unresolved crash window, not permission to retry.

The runner is synchronous and is not a durable service. A prompt or skill cannot guarantee supervision after Codex or its host stops. Schedule follow-up only through an available native facility when the user requests it, without treating a reminder as process supervision.

## Compare and decide

Use `compare` only after both executions and their result evidence are complete. It requires matching full protocols, declared file identities, and recorded runtime environments; even a budget-only protocol change makes these runs incomparable. Keep candidate hypotheses in the run's `--hypothesis` field and source changes in Git. Review the baseline/candidate diff to establish that the evaluator and other invariants stayed within the permitted changes. Comparison reports a win only for positive numerical improvement at least as large as the configured absolute threshold. Read the raw metrics and logs, then apply any further scientific gates from the protocol. A threshold win alone is not a significance test.

Keep failed, invalid, and incomparable runs visible. A result that misses the improvement threshold is useful evidence. Stop when the question is answered, the budget is exhausted, or additional execution needs a material decision outside current authorization. Use [evidence.md](evidence.md) to explain the supported conclusion and its limits.
