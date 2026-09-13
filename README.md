# Research Lab

A native Codex plugin for literature research and traceable local experiments. One skill guides the investigation; a small Python runner records committed source, declared inputs, execution logs, metrics, and comparisons. Codex provides the conversation, tools, optional subagents, and artifact viewing.

Research Lab is an original implementation inspired by the experiment and evidence workflow of [OpenResearch](https://github.com/alphaXiv/OpenResearch). It has no OpenResearch runtime dependency and does not include its source code.

## Install in Codex

Use a Codex version with the native plugin marketplace commands, plus Git and Python 3.11 or newer for experiments. No additional Python packages are required. The commands below use the public repository:

```sh
codex plugin marketplace add kageyoru08/research-lab
codex plugin add research-lab@research-lab
```

Start a new Codex task after installation and invoke `$research` or select **Research Lab** in the skill picker. The skill can also be selected automatically for matching research requests. The skill and runner do not edit global Codex configuration or install a model provider.

Example requests:

> Use $research to assess recent evidence for this method. Read primary sources, distinguish full-text evidence from abstracts, and explain the unresolved questions.

> Use $research in this project to compare our baseline with one candidate. Agree on the metric, split, seeds, and run budget before executing, then report the result with its run evidence.

> Use $research to resume this investigation. Inspect saved runs before launching anything and explain what the existing evidence supports.

## What is included

| Component | Responsibility |
| --- | --- |
| `research` skill | Research questions, source assessment, protocols, decisions, and reports |
| Conditional references | Literature, local experiments, and evidence guidance loaded only when needed |
| Python runner | Source archives, input identities, durable records, one launch per run ID, validation, and numerical comparison |
| Small regression example | A complete local baseline/candidate exercise with an isolated Git project |

The skill uses available native tools. No specific model, connector, external consultation, or other skill is required. Delegation is optional; a subagent does not automatically receive a Git worktree.

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

## Use the runner directly

From this repository, inspect its commands with:

```sh
python plugins/research-lab/skills/research/scripts/research.py --help
```

When invoked by the installed skill, Codex resolves the runner from that skill's own directory. It does not depend on this repository's checkout location.

The command sequence is `init`, `prepare`, `run`, `inspect`, and `compare`; each returns JSON. The project must be an existing Git repository root. `init --project PATH` creates `.research/protocol.json` without overwriting an existing protocol. Review the generated protocol, ignore `.research/` in the project's Git configuration, and commit the intended source before preparing a run. The runner does not edit `.gitignore` for you and rejects a dirty checkout.

The protocol defines the evaluator command, primary metric and direction, improvement threshold, declared data paths, comparison conditions, and run/time budget. Declared data paths refer to committed files in the snapshot. The command is an argument array with `{python}` and `{result}` substitutions; it is executed without implicit shell parsing. The evaluator writes its configured primary metric as a finite JSON number; any additional metrics must also be finite numbers:

```json
{"metrics": {"mse": 0.125}}
```

See [experiment guidance](plugins/research-lab/skills/research/references/experiments.md) for the full workflow and [the skill](plugins/research-lab/skills/research/SKILL.md) for research behavior.

Run records live in `.research/runs/`. Preparation captures committed code through `git archive` and records declared input identities. Identical inputs return the existing run record unless `--replicate` is explicitly requested; inspect its state before deciding what to do next. Each run ID permits one launch attempt, including failed or interrupted attempts. A launch claim conservatively consumes budget before process creation.

The evaluator must stay in the foreground, wait for its workers, and finish writing its result before returning. Detached jobs are unsupported. Source snapshots contain no Git repository; upward Git discovery is bounded and inherited `GIT_*` settings are cleared. Evaluators needing source identity can read `RESEARCH_SOURCE_COMMIT` and `RESEARCH_SOURCE_ROOT` from their environment. A Git-dependent evaluator must adapt to this contract instead of reading the live checkout.

Inspect saved records before resuming. A `launching` or `running` record may represent unresolved execution; timeout and interruption also require reconciliation even when the direct child was reaped. Cleanup records describe attempted termination and observed process facts, not guaranteed containment of every descendant. The runner does not infer completion from a persisted PID or retry a claimed run automatically. Preserve the evidence and establish what happened before choosing a separate replicated run.

## Interpretation and limits

Execution success, valid evidence, and scientific acceptance are separate decisions. Comparison requires matching full protocols, declared data identities, and recorded runtime environments, then checks positive improvement against an absolute threshold. Even a change to the run budget makes the protocols incomparable. The runner does not prove significance, absence of leakage, correct seed use, or generalization. Those decisions require an appropriate protocol and evaluation code. Negative and null results remain useful outcomes.

Integer-only metric arithmetic remains exact. Floating-point metrics use Python's binary floating-point arithmetic; there is no hidden tolerance. Mixed integer/float comparisons reject integers that cannot be represented exactly as a float, and nonfinite arithmetic is rejected. Review the source diff for permitted changes; invariant evaluator files can be included in `data_paths` alongside data files so their content must also match.

Source snapshots do not capture every external input or recreate the host environment. This version rejects snapshots containing symlinks or Git submodules. Declare relevant local data and record dependencies, hardware, and external services when they affect interpretation. The runner executes the project's command with the caller's permissions; neither it nor a Git worktree is a security sandbox.

Version 1 provides local synchronous execution. It includes no SSH or cloud adapter, hosted dashboard, durable job supervisor, or model API client. A skill prompt cannot guarantee always-on jobs after Codex or the host exits. Codex usage and any computation selected by the user can still incur costs.

## License

MIT, copyright Kageyoru. See [LICENSE](LICENSE).
