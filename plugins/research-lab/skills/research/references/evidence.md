# Evidence and decisions

Make the chain from question to conclusion recoverable without relying on conversation history. Use the project's existing record format; introduce only the files needed for the investigation.

## Activate and close a native evidence session

Resolve `scripts/research.py` from this installed skill. Its `evidence` commands
need Python 3.11+ and an existing project directory, including for literature
without Git. Declare the actual report and working checkpoint paths relative
to that directory; do not create a fake experiment protocol for literature.

```text
evidence activate --project ROOT --artifact REPORT --artifact CHECKPOINT --public-web --record CHECKPOINT
evidence sources --project ROOT
evidence readback --project ROOT
evidence check --project ROOT
evidence close --project ROOT
```

Add `--experiment` after establishing the real runner's `reconcile` entry;
it attaches existing obligations, comparisons, claims and run state. Omit
`--public-web` when public source capture is outside the task. The CLI derives
the native session and thread IDs from its two named runtime values; missing
identity is not repaired by inventing an ID. Initial support is the activated
root actor. Worker capture and other tool routes are not implied.

Activation records intent and exact deliverable paths. Native hooks must also
be discovered, enabled and trusted through Codex's `/hooks` interface. They
do not change host permissions or trust themselves. A registered hook can
receive matching-event input even while inactive; inactive sessions retain
no response body and create no review obligation. Close the session before
unrelated work. Ordinary single-fact answers do not activate this workflow.

For public-web capture, `--record` selects the working record from the declared
artifacts. After each captured operation, run the literal source-reader
invocation returned by activation as its own native command and return its
complete output. It reads saved source evidence without needing the final
report to exist. Inspect the actual request, returned text, source identities
and capture date; retain the generated receipt references in the working
record with your coverage, selection and material evidence notes. Complete
any remaining pending reads before another source operation.

The next supported web call waits for the matched source-reader response and
current record references. A local prerequisite refusal occurs before web
execution; satisfy that local requirement before submitting the intended
operation. A capture failure remains a separate incomplete operation whose
surviving evidence must be preserved. Ordinary close rechecks the references
so a rewritten checkpoint cannot silently discard them. Exact response and
reference checks do not assess the scientific meaning of the notes, source
access, version relevance or citation accuracy. Arbitrary writes and chat
are outside this prerequisite.

Use the literal platform invocation returned by activation for readback.
Return its complete output through the native tool, with an adequate output
budget. The helper reads every declared small UTF-8 file and saves an
immutable bundle under `.research/evidence/`. Missing, unsafe, oversized or
non-text artifacts are incomplete; no heading filter or silent truncation
substitutes for the declared contents. Read and assess that bundle against
the question and retained sources. The generated obligation/run view is a
closure companion; carry its material state into the actual checkpoint.

`check` compares current deliverables and attached evidence with that
readback. Relevant changes require another readback. A helper emission and a
matching native response are separate observations; neither proves model
comprehension or that outer code exposed all text. Ordinary close requires
fresh required records, supported native reader matches and retained source
references, and then disables capture. It does not label the research
scientifically complete.

`check` and a refused ordinary close name the unmet conditions and return the
literal reader commands. If the latest readback has no native match, run its
command alone, expose the complete output and inspect the saved contents;
then check or close in a separate call. A missing match does not establish
that the native route is unavailable. `semantic_review_verified: false` is
expected: semantic judgment is outside machine proof and does not prevent
ordinary close.

When a required capability remains unavailable, preserve the concrete cause
with `evidence close --project ROOT --incomplete --reason TEXT`. That closes
capture without converting missing review or source evidence into success.
The explicit commands do not intercept chat completion: omitting activation
or close remains possible, and no Stop enforcement is claimed.

If native identity, hooks or the exact reader route are unavailable, use
ordinary authorized file tools to save and read the deliverables and state
the unavailable automatic checks. The literature reference provides a
bounded capture fallback. Do not install a provider, change global safety or
invent a native receipt to hide that limitation.

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

For a completed bundled-runner run with valid result evidence, the run directory contains `manifest.json`, `source.zip`, `result.json`, and `run.log`. Verify the paths you cite against the files you inspected.

For uncertainty or stability claims, show the actual supporting design and analysis: for example, paired seeds, repeated trials, confidence intervals, or disjoint evaluation data when the protocol requires them. Do not invent uncertainty estimates from one aggregate number.

A failed, interrupted, or timed-out execution stays unresolved until its actual execution is established; its workers may outlive the evaluator. Read existing manifests and logs before continuing, preserve the uncertainty in project notes, and do not infer process identity from a reused PID. A paused conversation does not provide durable job supervision.
