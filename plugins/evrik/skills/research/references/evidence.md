# Evidence and decisions

Make the chain from question to conclusion recoverable without relying on conversation history. Use the project's existing record format; introduce only the files needed for the investigation.

## Scope a review without duplicating history

Maintain one current checkpoint and a compact evidence manifest, which may be
a table inside it. For each reused material claim, retain the original path,
SHA-256, reviewed claim/scope, review identity, source/input/protocol/comparator
bindings, limitations and unresolved obligations. Keep full original artifacts
and receipts at their existing locations. Do not copy an ancestor's full text
or manifest into every descendant. A shorter checkpoint must not erase a
failure, budget breach, dissent, missing proof or sealed-test restriction.

Check referenced bytes and the bindings that make prior review applicable.
Semantic review covers new or changed claims and their dependency impacts;
follow original evidence for any unreviewed, changed, stale or disputed claim.
If the old review did not cover the new use, review that use before relying on
it. Hash verification only establishes identity. It cannot create native proof,
prove source access, discharge a scientific obligation, or grant new attempts.
Metadata access failures remain errors; they cannot stand for missing evidence,
an empty record history, or an absent preflight requirement.
An unreadable receipt directory cannot count as an empty successful capture.

Declare the actual current deliverables and necessary new evidence for native
review. An immutable historical source already reviewed for the same use can
remain a checked reference; this is not native delivery in a new activation.
Every declared artifact and the complete attached runner companion still use
the full readback below. Do not omit a required artifact or choose a fallback
merely to reduce page count. Existing activations keep their requirements;
scope changes use explicit `revise` and retain their original records.

Administrative edits and retrospective workflow maintenance alone require
ordinary saved-content review and appropriate local checks, not a new research
activation or experiment. Preserve any existing pending research obligations.
When research is paused, such maintenance does not resume it.

## Activate and close a native evidence session

Resolve `scripts/research.py` from this installed skill. Its `evidence` commands
need Python 3.11+ and an existing project directory, including for literature
without Git. Declare the actual report and working checkpoint paths relative
to that directory; do not create a fake experiment protocol for literature.

```text
evidence activate --project ROOT --artifact REPORT --artifact CHECKPOINT --public-web --record CHECKPOINT --hook-root NATIVE_WORKSPACE
evidence sources --project ROOT
evidence next --project ROOT
evidence check --project ROOT
evidence close --project ROOT
```

Add `--experiment` after establishing the real runner's `reconcile` entry;
it attaches existing obligations, comparisons, claims and run state. Omit
`--public-web` when public source capture is outside the task. The CLI derives
the native session and thread IDs from its two named runtime values; missing
identity is not repaired by inventing an ID. Initial support is the activated
root actor. Worker capture and other tool routes are not implied.
For public web, `--hook-root` is the native chat workspace where the hook runs;
it defaults to the activation command's working directory. A stream activation
binds that workspace to this project for the native session. There is one active
public-web destination per owner/workspace. Reader calls diagnose a mismatching
hook root; they cannot grant a normal close while that binding is wrong.
If the root web hook cannot read or validate its route/session binding, it
blocks the operation. A refusal before retrieval creates no capture attempt;
restore the binding before submitting the intended operation. A failure after
retrieval preserves any pending attempt and grants no source credit.

Before activation, enumerate every project-relative text artifact required
for final review, including the shared decision, participant responses and
any additional API or refusal ledger. Declare those paths with repeated
`--artifact` options even if the files will be written later. `--experiment`
attaches runner state; it does not discover arbitrary collaboration files.
New activations use `stream-v2`. If scope changes, use
`evidence revise --project ROOT --artifact REPORT --artifact CHECKPOINT --artifact NEW --reason TEXT`
with the **complete** intended scope, including retained files. The previous
scope record and all receipts remain immutable. The new scope needs a fresh
manifest read. An interrupted publication may consume a scope version; a
corrected revision uses the next unused version and retains the original files.
Unchanged artifact units can reuse validated native page proofs
from this same activation. Changed units need new reads. Removing a file is
explicitly recorded and does not prove that its obligation was resolved.
Legacy `pages-v1` and `stream-v1` generations retain their original rules; close
them honestly before a new streaming activation. Handler changes require a
new activation and do not inherit native credit from the previous handler.
Prefer correcting or revising the existing active scope over creating another
generation for bookkeeping. This does not reopen an already closed activation.

Identify the loaded revision by its handler SHA-256 and payload hashes, not
version 1.0.0 alone. Start a fresh native task after a payload refresh and verify
skill/hook discovery; an existing chat can retain old instructions.
Activation records intent and exact deliverable paths. Native hooks must also
be discovered, enabled and trusted through Codex's `/hooks` interface. They
do not change host permissions or trust themselves. A registered hook can
receive matching-event input even while inactive; inactive sessions retain
no response body and create no review obligation. Close the session before
unrelated work. Ordinary single-fact answers do not activate this workflow.

For public-web capture, `--record` selects the working record from the declared
artifacts. A request may combine supported `search_query`, `open` and `find`
groups; each group must be valid. Capture retains the whole request and response
without inventing associations between individual queries and returned sources.
After each captured operation, run the literal source-reader
invocation returned by activation as its own native command and return each
complete output page. Follow its literal `next_command` until all pages of
that receipt have been exposed and inspected. It reads saved source evidence without needing the final
report to exist. Inspect the actual request, returned text, source identities
and capture date; retain the generated receipt references in the working
record with your coverage, selection and material evidence notes. Copy the
bundle's exact standalone `record_reference` token for each required capture,
or all of that capture's emitted `capture.receipts[*].path` strings. Never
reconstruct hashed references from memory. The bundle's `missing_record_refs`
lists saved receipt paths lacking either reference form in its named `record`
when that bundle was created. Retain a valid reference with the source notes,
then check the current state; this list does not report a source access or
capture failure. A reference cannot substitute for inspecting and matching
the complete source-reader response. Complete any remaining pending reads
before another source operation.

The next supported web call waits for the matched source-reader response and
current record references. A local prerequisite refusal occurs before web
execution; satisfy that local requirement before submitting the intended
operation. Invalid request shapes are also refused before retrieval without
creating capture receipts; correct only the local request. A capture failure
after retrieval remains a separate incomplete operation whose
surviving evidence must be preserved. Ordinary close rechecks the references
so a rewritten checkpoint cannot silently discard them. Exact response and
reference checks do not assess the scientific meaning of the notes, source
access, version relevance or citation accuracy. Arbitrary writes and chat
are outside this prerequisite.

Activation's `resume_command`, `readback_command` and `sources_command` are shell
commands for the existing native execution tool, not separately named reader
tools. Prefer the returned string, preserving its executable, script, flags
and project. `stream-v2` also accepts safe literal quoting and OS-equivalent
path separators/case for those same absolute paths. Shell expressions,
compound commands and aliases remain unsupported. Older transports require
their original literal spelling. Successful emission alone is not a match.
For final artifacts, prefer the same generated `resume_command` (`evidence next`)
on each call: it selects the first unmatched part, resumes the same immutable
receipt after interruption. While pages remain, it reads that pinned snapshot;
after completion it checks current bytes before reusing or replacing the manifest.
Use explicit `readback` to refresh a changed, unfinished snapshot.
`check` supplies `resume_functions_exec_source`, progress, size including companion
metadata, and unmet conditions. It never silently closes, retries a retrieval,
dispatches a reviewer, or treats emission as native matching.

The streaming reader returns bounded JSON frames of saved UTF-8 artifact bytes,
the scope manifest and complete companion metadata. In `stream-v2`, repeated
large companion values are stored once with explicit field-path references;
all units must reconstruct the exact original companion bytes and hash. This
does not summarize or remove failures, obligations or run state. Identical units
can reuse validated proof only within the same activation and handler.
`page.part` identifies the
unit, byte offset and chunk hash. There is no aggregate 256 KiB limit. It hashes
and copies file chunks without loading the full artifact corpus into memory;
manifests and runner metadata still use memory proportional to their size.
The source reader retains its bounded capture contract below. Return each
complete frame through a separate native call, then follow its exact
`next_command`; do not combine all pages into one tool output. Requested
output capacity must cover every initial, continuation and recovery frame,
up to 16,384 UTF-8 bytes including the newline, through the native execution
tool and any outer result wrapper. Do not reuse a summary-sized output cap.
For a token-based limit, request at least 16,384 output tokens when supported;
bytes and tokens are different units, so this conservative allowance is not
a delivery guarantee. Output budgets can be capped by the native platform, so
a larger request does not guarantee complete delivery.
When a reader call uses `functions.exec`, put the first-line directive
`// @exec: {"max_output_tokens": 16384}` on that wrapper and also set
`max_output_tokens` to at least 16384 on the nested native execution call.
The nested setting does not raise the wrapper's default. Apply both settings
to every initial, continuation and correction page, and expose the full result.
Activation and status also provide `readback_functions_exec_source` and
`sources_functions_exec_source`. When using `functions.exec`, submit the
corresponding source directly: it preserves the literal command, sets both
output limits and exposes the complete native output for one page. New sessions'
frames provide `next_functions_exec_source` for the next page, or null when done.
Status provides the same template beside each pending command, including
`next_readback_functions_exec_source`. Inspect each returned page before using
the next template; do not batch or loop over templates. These call templates
are a convenience, not proof of delivery or review, and do not run check or close.
Stop following page commands when `next_command` is null, then run `check`
and `close`; do not add a complete `check` between every page. Reserve at least
the reported `remaining_pages` plus final check/close within the existing
budget, and account separately for source reads, corrections and failures.
An insufficient reserve is a visible incomplete result, not permission to
refill attempts or discard required evidence.
The helper reads every declared UTF-8 file and saves immutable hash-addressed
parts under `.research/evidence/`. Missing, unsafe, non-text artifacts or
metadata that cannot fit a frame remain incomplete; no heading filter or silent
truncation substitutes for the declared contents. Read every segment in its unit
context and assess that bundle against
the question and retained sources. The generated obligation/run view is a
closure companion; carry its material state into the actual checkpoint.

For `stream-v2`, each page and its hook validate the immutable snapshot and
exact page response without rescanning current deliverables or run archives.
The frame explicitly reports current evidence as not checked. `check` and
ordinary `close` perform full current source/dependency/scope/handler and native
proof validation outside the hook's five-second window. A snapshot MATCH does
not attest freshness at each page or transient changes between those boundaries.
New activations add a derived page index and resumable cursor. A compact
reader-state cache avoids loading full activation history and artifact scope
on every page; session/scope file changes invalidate it. The index, cursor,
file stamps and progress markers are scheduling hints, never native credit.
Missing state/cursor caches recover from authoritative records; invalid or
missing page descriptors fail closed. Emission alone does not advance the
cursor. PostToolUse saves the native proof and marker; the next reader invocation
advances the cursor from those durable markers. The cursor may therefore lag
the final delivered page, including after closure; completion comes from full
proof validation, not the cursor value. A lost cursor update is recoverable.
At `check`/`close`, the complete saved manifest, unit/blob identities, original
Pre/Post bindings and current evidence are independently validated without
trusting these caches. New `page-cache-v2` indexes store at most 32 descriptors
per immutable file, using the same atomic flush/fsync/replace writer and publishing
the header only after every group is durable. Readers validate one group at a
time; an oversize-file check precedes parsing. This reduces creation flushes but
reads more metadata per page. Interrupted creation preserves completed groups;
conflicting contents and missing/malformed published groups fail closed.
Within one locked `next` invocation, cursor advancement and frame construction
reuse a single fully validated group, bound to its path and complete header.
Crossing a group boundary replaces that entry; every new invocation reads again.
This memory-only cache adds no durable state. Hooks and full `check`/`close`
remain independent of it.
Existing `page-cache-v1` indexes retain individual files, and activations without
an index retain their original path. Changed handlers still require a fresh
activation; grouping never migrates historical native credit. Linear pagination
measurements apply to one snapshot; history/reuse and full boundary validation
still depend on their evidence volume.

`check` compares current deliverables and attached evidence with that
readback. Relevant changes require another readback; never mix pages from
different receipts. Each page needs its exact native request/response match,
and the complete unique page set must cover the manifest and verify every unit hash before
the reader is acknowledged. Page delivery order is not an acceptance rule;
missing pages and duplicate reads cannot satisfy coverage. Count every page
and failed call within the task's existing budget, reserving final review
and correction work. A helper emission and a
matching native response are separate observations; neither proves model
comprehension or that outer code exposed all text. Ordinary close requires
fresh required records, supported native reader matches and retained source
references, and then disables capture. It does not label the research
scientifically complete.

After closure, explicit `check` and repeated `close` still inspect current
evidence. Their `status: closed` describes the historical session;
`current_evidence` reports whether the saved review remains current. An
ordinary repeated close refuses changed or incomplete evidence without
rewriting the original close. Readers and capture stay inactive. Further
native review requires a deliberate new activation; do not rewrite the
reviewed checkpoint merely to add the later close result. Report that
execution tail separately.
Use the existing close receipt or one short tail record as the terminal
administrative record. Do not recursively read back closures of closures.
This rule never suppresses a material correction or an unmet review obligation.

While active, `check` and a refused ordinary close name the unmet conditions and return the
literal reader commands and pending-page progress. If the latest readback
has no native match, use `next_readback_command`; for pending sources use
the source status's `next_command`. Run it alone, expose the complete output
and inspect the saved contents;
then check or close in a separate call. A continuation reads the same
immutable receipt. Legacy transports refuse changed current evidence at each
page; `stream-v2` detects stale current evidence at check/close. Truncated or
unmatched pages remain incomplete; no automatic retry, manual hook invocation
or hash-only substitute is supported. A missing match does not establish
that the native route is unavailable. `semantic_review_verified: false` is
expected: semantic judgment is outside machine proof and does not prevent
ordinary close.

`check.diagnostics` reports routed hook events, recognition, saved attempts,
response type/byte count, matching stage and the first failure. It never stores
the raw hook envelope or private session fields. No observed event means only
that no event was recorded for this activation; it does not prove that hooks
are absent. Diagnostic counts are operational telemetry, not evidence credit.
Generated reader commands route to their explicitly activated project even
when the native hook runs at a parent workspace. Unsupported shell forms remain
unmatched and are diagnosed when the activation can be located.
Reader-intent diagnostics look for separate `evidence readback`, `evidence sources`
or `evidence next` arguments after a Python script in a literal Python invocation.
Management operations and quoted filename/prose references remain neutral. This
limited lexical hint does not resolve shell variables, wrappers or expressions,
and grants no native credit; historical failures stay intact.

Supported public text blocks may retain their `annotations` and `_meta`
wrappers. When an otherwise unsupported response can be safely serialized
within the capture cap, diagnostics retain its body path and hash for manual
recovery. The original operation stays incomplete and receives no native source
credit. Private-shaped, oversized or absent bodies are not saved; do not repeat
a retrieval merely to replace a failed receipt or imply recovery is guaranteed.

## Supported capture boundaries

| Route | Capture and verification | Boundary |
| --- | --- | --- |
| Root native generated reader | Pre/Post request, response bytes and part hashes; full current scope at check/close | Does not attest comprehension, outer display or continuous freshness |
| Root native `webrun` search/open/find | Bounded request/returned text, source reader and record references | Explicit hook-workspace route for stream sessions; supported text only, 256 KiB capture and source bundle limits |
| Exa or another source tool | `record source` imports an already saved ordinary response and explicit identity metadata | Not automatic native capture; do not retrieve again just to fill a receipt |
| Worker ordinary output | `record save`, or `record review` bound to a frozen packet | Caller-reported identity; no private sessions, implied routing, or model attestation |
| Scientific acceptance | Human/agent judgment against the declared protocol | Neither MATCH, exit 0, result `valid`, nor collected votes establishes it |

Separate capability **specified**, **installed**, **ready**, and **verified in
this environment**. Record host/version, observed probe and any unavailable
reason only when that capability matters. A listed tool or trusted hook is
not proof that its execution succeeded.

## Version working records and recover reviews

Use these optional commands when a document or review needs durable identity:

```text
record save --project ROOT --key checkpoint --input CHECKPOINT
record freeze --project ROOT --key final-review --artifact REPORT --artifact CHECKPOINT --reviewer ROOT_ID --reviewer PEER_ID
record review --project ROOT --key peer-invitation --packet PACKET_HASH --reviewer PEER_ID --status failed --input SAVED_FAILURE --model ACTUAL_MODEL
record review --project ROOT --key peer-vote --packet PACKET_HASH --reviewer PEER_ID --status completed --decision accept --input SAVED_VOTE --model ACTUAL_MODEL
record withdraw --project ROOT --key correction --target VOTE_RECORD_HASH --reason TEXT
status --project ROOT
status --project ROOT --since STATUS_HASH
```

Records preserve exclusively created copies and hashes of the actual bytes,
including LF/CRLF differences. Input bytes are copied into a separate staging
file, flushed and validated before exclusive publication. This uses a hard link
from staging to the final name on the same filesystem, then removes staging;
the saved object does not share the input file's inode. Filesystems without
hard-link support report an error. Failed staging files may remain for diagnosis
but carry no record credit and do not block a later save of unchanged input.
Existing final objects, including historical corruption, are never overwritten.
Repeating the same
event is idempotent. A withdrawal appends a record; it never edits the vote.
A frozen packet declares required reviewer identities. Failed or missing
invitations remain unresolved; recovering a review uses those saved artifacts,
not another experiment or an invented approval. Inspect the current native
inventory and actual returned actor ID before any authorized invitation.
Recording a status does not dispatch, queue, cancel or attest an actor.

`status` separates execution, saved-artifact integrity, scientific assessability,
review decisions, and native verification. A review of changed packet bytes is
stale. An accepted review packet is still not scientific qualification. The
delta view suppresses unchanged facets. Administration reports only measured
local preflight time and record counts; model tokens, other administrative time
and cost stay unknown. Do not claim a saving percentage from those counters.

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
