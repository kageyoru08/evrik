# Research Lab

A native Codex plugin for literature research and traceable local experiments. One skill guides the investigation; a Python runner records committed experiments and saved evidence. Opt-in native hooks capture supported public web responses and check a declared saved-content readback. Codex provides the conversation, tools, optional subagents, and artifact viewing.

Research Lab is an original implementation inspired by the experiment and evidence workflow of [OpenResearch](https://github.com/alphaXiv/OpenResearch). It has no OpenResearch runtime dependency and does not include its source code.

## Install in Codex

Use a Codex version with the native plugin marketplace and hook interfaces, plus Python 3.11 or newer (`python3` on POSIX, `python` on Windows). Git is needed for experiments, while literature evidence storage works without it. No additional Python packages are required. The commands below use the public repository:

```sh
codex plugin marketplace add kageyoru08/research-lab
codex plugin add research-lab@research-lab
```

Start a new Codex task after installation and review Research Lab's two hook definitions in `/hooks` before trusting them. Installation alone does not trust new or changed hooks. Invoke `$research` or select **Research Lab** in the skill picker; matching research requests may select it naturally. The skill and runner do not edit global Codex configuration or install a model provider; Codex's own trust interface persists the choices you make there.

Example requests:

> Use $research to assess recent evidence for this method. Read primary sources, distinguish full-text evidence from abstracts, and explain the unresolved questions.

> Use $research in this project to compare our baseline with one candidate. Agree on the metric, split, seeds, and run budget before executing, then report the result with its run evidence.

> Use $research to resume this investigation. Inspect saved runs before launching anything and explain what the existing evidence supports.

> Use $research to hold a peer meeting on this research decision. Have participants exchange evidence and objections, then review and explicitly accept the same final decision or preserve what remains unresolved.

## Refresh an existing installation

For an installed plugin from this Git marketplace, refresh only Research Lab:

```sh
codex plugin marketplace upgrade research-lab --json
```

On the tested Codex CLI **0.153.4**, this command updated both the marketplace snapshot and the installed cached skill when its contents changed while the plugin version stayed **1.0.0**. This behavior has not been validated on other CLI versions.

Check that the response has no errors, then start a new Codex task and select **Research Lab**. An existing task may retain previously loaded skill instructions. For a reissue that keeps version **1.0.0**, identify the intended revision by its Git commit and compare the installed runner and skill file hashes with that commit; the version number alone cannot distinguish revisions.

## What is included

| Component | Responsibility |
| --- | --- |
| `research` skill | Research questions, source assessment, protocols, decisions, and reports |
| Conditional references | Literature, local experiments, evidence, and peer-meeting guidance loaded only when needed |
| Python runner | Source archives, input identities, durable records, one launch per run ID, validation, and numerical comparison |
| Native evidence hooks | Explicit session capture on supported public web calls and exact saved-reader response matching |
| Small regression example | A complete local baseline/candidate exercise with an isolated Git project |

The skill uses available native tools. No specific model, connector, external consultation, or other skill is required. Delegation is optional; a subagent does not automatically receive a Git worktree.

For a requested collective decision, the [peer-meeting guidance](plugins/research-lab/skills/research/references/parallelism.md) gives participants their own initial positions, reciprocal critique and explicit review of the same saved decision. The facilitator manages the record and routing with equal substantive standing. Direct native messages are preferred; a necessary relay preserves complete attributed content and is labeled. Unresolved material objections or missing acceptance leave a provisional or blocked result. These instructions add no scheduler or service, and consensus does not prove correctness or complete defect discovery.

For supported native root sessions, declare the report/checkpoint paths with
`evidence activate`, use `--public-web --record CHECKPOINT` for authorized public
source capture and its declared working record, and add `--experiment` to attach
real reconciled run state. `evidence sources` returns saved source responses;
the next supported web call and ordinary close require its matched native
response and retained receipt references in that working record. This checks
source-reading steps and references, not the meaning of the evidence notes.
`evidence readback`
returns the declared saved text; `check` detects relevant changes and `close`
requires fresh evidence before disabling capture. Use the exact reader
invocation returned by activation. These commands need an existing directory,
not a Git repository or a fake protocol for literature.

Records distinguish helper emission from a matched native response. Neither
proves comprehension, narrative completeness, full-page access or scientific
acceptance. Unsupported routes, disabled/untrusted hooks, worker inheritance
and omitted activation are outside automatic capture; inactive sessions do
not retain bodies. Registered hooks may still receive matching-event input
before filtering. There is no automatic Stop enforcement. The skill retains
manual capture/readback fallbacks and an explicit incomplete close when a
required native check is unavailable.

## Try the local example

Clone the repository and run the example from its root:

```sh
git clone https://github.com/kageyoru08/research-lab.git
cd research-lab
python examples/run_demo.py --workspace ../research-lab-demo
```

Choose an empty or nonexistent demo directory. The example creates a tiny Git project, prepares and runs a baseline and a linear candidate, checks their comparison, and writes a report in that workspace. It uses local computation and needs no model API key. The fixture exercises bookkeeping and comparison behavior; it is not a claim about performance on real research workloads.

Run the repository checks with:

```sh
python -m unittest discover -s tests -v
```

See [native agent behavior validation](BEHAVIOR.md) for the observed use of the installed plugin in a separate Codex task, beyond the scripted example and runner tests.

## Use the runner directly

From this repository, inspect its commands with:

```sh
python plugins/research-lab/skills/research/scripts/research.py --help
```

When invoked by the installed skill, Codex resolves the runner from that skill's own directory. It does not depend on this repository's checkout location.

The command sequence is `init`, `reconcile`, `prepare`, `run`, `inspect`, and `compare`; each returns JSON. The project must be an existing Git repository root. `init --project PATH` creates `.research/protocol.json` without overwriting an existing protocol and reports the inherited-material entry status. Establish that decision before experimental edits or launches. Review the generated protocol, ignore `.research/`, and commit the intended source before preparing a run. The runner does not edit `.gitignore` for you and rejects a dirty checkout.

For inherited work, `reconcile --project PATH --note NOTE_PATH` registers
selected existing notes and returns their complete source-bound review units
with saved runner state. Record explicit dispositions and use `verify` for
runner-computed reference/current/HEAD content comparisons. If no inherited
material applies, explicitly record the caller's rationale with
`reconcile --project PATH --no-inherited-notes --rationale TEXT`. This assertion
is not machine verification, and no absence decision is made automatically.
New preparation and launch require an entry decision; selected-note reviews
are checked automatically for pending, unresolved, failed or stale prerequisites. Earlier notes
and decisions remain available, and prepared runs retain their own review
receipts. The runner does not decide whether every relevant note was selected
or correctly interpreted, that an absence assertion is true, or that the final
checkpoint retains every resolution. Direct shell actions are outside this
gate. The [experiment guidance](plugins/research-lab/skills/research/references/experiments.md)
describes commands, classifications and snapshot behavior.

Old never-registered records remain readable, inspectable and comparable under
their existing scientific rules; uncertain/claimed executions are never
automatically retried. An old preparation without an entry receipt needs a
new attributable preparation before launch. The same applies if notes are
selected after preparing under an absence declaration. Original receipts and
budgets remain unchanged. Existing schema-1 selected reviews need no migration;
new schema-2 entry records require the repaired runner rather than mixed older
writers. Later entry cannot retroactively establish pre-edit review.

Prepared runs retain their recorded protocol. Before launching, the active protocol's execution budget must still match the prepared run's `max_runs` and `timeout_seconds`. If either limit changes, prepare a new run under the desired budget; an older prepared run cannot bypass that change. This check applies before launch and does not supervise later edits during an existing execution.

The protocol defines the evaluator command, primary metric and direction, improvement threshold, declared data paths, comparison conditions, and run/time budget. Declared data paths refer to committed files in the snapshot. The command is an argument array with `{python}` and `{result}` substitutions; it is executed without implicit shell parsing. The evaluator writes its configured primary metric as a finite JSON number; any additional metrics must also be finite numbers:

```json
{"metrics": {"mse": 0.125}}
```

JSON object keys must be unique, including inside metrics. Conflicting duplicate keys are invalid evidence; the runner does not silently choose the last value. Protocols, manifests, and the launch ledger follow the same rule.

See [experiment guidance](plugins/research-lab/skills/research/references/experiments.md) for the full workflow and [the skill](plugins/research-lab/skills/research/SKILL.md) for research behavior.

Run records live in `.research/runs/`. Preparation captures committed code through `git archive` and records declared input identities. Identical inputs and applicable reconciliation evidence return an eligible existing run record unless `--replicate` is explicitly requested; inspect its state before deciding what to do next. Each run ID permits one launch attempt, including failed or interrupted attempts. A launch claim conservatively consumes budget before process creation.

The runner checks the ledger against recorded runs. A missing claim for a launched run or a claim without its run manifest is an integrity error that blocks further execution and comparison. Preserve the remaining files and reconcile the missing evidence; do not reset the ledger to regain budget. A claim with a still-prepared manifest remains an unresolved possible interruption between the two durable writes. Unsupported manifest versions and invalid recorded states are rejected with a JSON error.

The evaluator must stay in the foreground, wait for its workers, and finish writing its result before returning. Detached jobs are unsupported. Source snapshots contain no Git repository; a runner-created `.git` boundary marker makes Git discovery fail explicitly, and inherited `GIT_*` settings are cleared. This also works when the project name contains a path-list separator. Evaluators needing source identity can read `RESEARCH_SOURCE_COMMIT` and `RESEARCH_SOURCE_ROOT` from their environment. A Git-dependent evaluator must adapt to this contract instead of reading the live checkout.

Inspect saved records before resuming. A `launching` or `running` record may represent unresolved execution; failed executions, timeouts, and interruptions also require reconciliation even when the direct child was reaped. A failing foreground evaluator may leave workers behind. Cleanup records describe attempted termination and observed process facts, not guaranteed containment of every descendant. A `launch_failed` record can be resolved when no child was created. The runner does not infer completion from a persisted PID or retry a claimed run automatically. Preserve the evidence and establish what happened before choosing a separate replicated run.

## Interpretation and limits

Execution success, valid evidence, and scientific acceptance are separate decisions. Comparison requires matching full protocols, declared data identities, and recorded runtime environments, then checks positive improvement against an absolute threshold. Even a change to the run budget makes the protocols incomparable. The runner does not prove significance, absence of leakage, correct seed use, or generalization. Those decisions require an appropriate protocol and evaluation code. Negative and null results remain useful outcomes.

Integer-only metric arithmetic remains exact. Floating-point metrics use Python's binary floating-point arithmetic; there is no hidden tolerance. Mixed integer/float comparisons reject integers that cannot be represented exactly as a float, and nonfinite arithmetic is rejected. Review the source diff for permitted changes; invariant evaluator files can be included in `data_paths` alongside data files so their content must also match.

Source snapshots do not capture every external input or recreate the host environment. This version rejects snapshots containing symlinks or Git submodules. Declare relevant local data and record dependencies, hardware, and external services when they affect interpretation. The runner executes the project's command with the caller's permissions; neither it nor a Git worktree is a security sandbox.

Version 1 provides local synchronous execution. It includes no SSH or cloud adapter, hosted dashboard, durable job supervisor, or model API client. A skill prompt cannot guarantee always-on jobs after Codex or the host exits. Codex usage and any computation selected by the user can still incur costs.

## License

MIT, copyright Kageyoru. See [LICENSE](LICENSE).
