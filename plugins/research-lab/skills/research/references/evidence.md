# Evidence and decisions

Make the chain from question to conclusion recoverable without relying on conversation history. Use the project's existing record format; introduce only the files needed for the investigation.

## Preserve distinctions

- **Observed:** a source says something, a command produced an output, or an evaluator emitted a metric.
- **Assessed:** evidence passes specified quality or comparability checks.
- **Inferred:** a conclusion follows under stated assumptions and has stated limits.
- **Proposed:** a hypothesis or next action has not yet been established.

Name the relevant source or run when moving between these levels. A successful process exit is not a valid metric; a valid metric is not proof of improvement. The local runner's comparison applies the configured numerical threshold after its metadata checks. It does not establish statistical significance, causal validity, or generalization.

## Record enough to resume

For literature, retain bibliographic identifiers, access level, material evidence notes, and the claim each source supports. For experiments, use the run ID and runner records as the execution reference, then explain scientific decisions in the project research notes. Keep log excerpts in the conversation and full logs in files.

When a decision changes, record the reason, the evidence available at that time, and its effect on the original question. Clearly label exploratory analyses added after outcomes were visible. Preserve the previous protocol and results through their existing run records; do not overwrite them to make a later comparison appear predeclared.

The runner captures declared local inputs and committed code. External services, undeclared files, mutable dependencies, nondeterminism, and hardware differences may remain outside those records. State which of these matter to the conclusion rather than claiming complete reproducibility from a source hash.

## Report an answer that can be checked

Scale the report to the work. Cover the research question, method and comparison conditions, decisive evidence with citations or run paths, outcome against the original criteria, limitations, and any necessary next step. Identify failed or incomplete measurements that materially affect interpretation. Include negative results and results that miss the acceptance threshold.

For uncertainty or stability claims, show the actual supporting design and analysis: for example, paired seeds, repeated trials, confidence intervals, or disjoint evaluation data when the protocol requires them. Do not invent uncertainty estimates from one aggregate number.

An interrupted run stays unresolved until its actual execution is established. Read existing manifests and logs before continuing, preserve the uncertainty in project notes, and do not infer process identity from a reused PID. A paused conversation does not provide durable job supervision.
