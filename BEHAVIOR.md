# Native agent behavior validation

On 2026-09-13, a new Codex desktop task used the plugin installed from this public GitHub marketplace, with Codex CLI 0.153.4. The installed plugin's eight files matched the committed Git blobs at `37bf04427c14c204450cd56576852573cab360b7`. This was a model-driven task using the installed skill and runner, separate from the scripted regression demo and unit tests.

## Independent small experiment

The task received a deterministic classification project with 12 training observations and eight fixed held-out observations. Its evaluator fits a one-threshold classifier on training data; a model configuration selects one of two input features. An observer kept the independently calculated answer outside the task's allowed directory.

The request was to select at most one configuration change using training evidence, evaluate improvement in held-out balanced accuracy, require at least 0.10 absolute improvement, and use at most three evaluator launches with a ten-second timeout each. Data, evaluator, README, and ignore rules were immutable. Local model commits and research records were allowed; network use, installation, and access to observer materials were excluded. The task was not given runner command sequences, the candidate feature, or expected scores.

The agent loaded the installed skill and its experiment/evidence references. It selected the vibration feature from training separation and locked the choice before either held-out evaluation. A bounded read-only method review used training and evaluator source. The observed command traces for both agents contain no held-out label read before selection; the primary agent hashed that file as opaque bytes.

| Held-out metric | Baseline: temperature | Candidate: vibration |
| --- | ---: | ---: |
| Balanced accuracy | 0.50 | 1.00 |
| Accuracy | 0.50 | 1.00 |
| False-positive rate | 1.00 | 0.00 |
| False-negative rate | 0.00 | 0.00 |

The runner reported improvement `0.50`, threshold `0.10`, and outcome `win`. Exactly two evaluator launches completed with valid evidence; neither required recovery. The third permitted launch was unused. Only `model.json` differed between baseline and candidate commits. Independent artifact review confirmed identical full protocols, invariant file hashes, runtime identities, and valid source/result/log checksums.

The agent retained the candidate and linked its result report to the run records. It limited the conclusion to the synthetic fixed held-out set and did not claim statistical significance, generalization, or industrial diagnostic validity.

## Resume with a changed decision criterion

In the same task, a follow-up changed the improvement threshold to 0.60 and prohibited further evaluator launches or source changes. The agent first used `inspect` and `compare` on the saved runs. It distinguished the original threshold win from a retrospective decision: improvement remained 0.50, so the new threshold was not met. It also identified that a baseline score of 0.50 and maximum score of 1.00 make a 0.60 improvement unattainable on this fixed metric.

The agent added a separate decision record and marked the report's current conclusion, preserving the original report text. Observer hashes confirmed that all other preexisting records, including the protocol, source archives, manifests, raw results, logs, and launch ledger, remained unchanged. There were still two launches and the same candidate source commit. The new criterion was explicitly labeled as a post-result reassessment, not a new measurement or a retroactively predeclared experiment.

## Changes after observation

No runner or skill behavior defect was found in those first two task turns. The initial documentation reissue at `9f81e33616aab62571dd70f1a0918c950809d98d` retained their tested bytes and version **1.0.0**. The installation guide explains a targeted marketplace refresh, new-task pickup, and commit/hash checks for identifying a reissue with the same version. A separate isolated CLI experiment verified that marketplace upgrade updated an installed skill from Git revision A to B without changing version 1.0.0; removal/reinstallation also worked as a fallback. Subsequent stricter probes found the issues described below.

## Stricter runner probes

Eight bounded CLI probes examined duplicate result keys, a stale launch ledger, a claim whose run evidence was missing, malformed manifest status, unsupported manifest schema version, reduced active execution limits, a failed pre-child spawn, and a committed symlink. The original runner accepted an ambiguous duplicate metric, allowed missing claims in an existing ledger to undercount launches, and did not clearly surface orphan claims. It also emitted a traceback for a list-valued status and accepted an unsupported manifest version.

The corrections reject duplicate JSON object keys in results and metadata, reconcile ledger claims with run manifests without reconstructing missing evidence, and validate manifest version/state before use. A prepared manifest with a durable claim remains an allowed unresolved crash window. Focused CLI regressions exercise these behaviors and preserve the existing one-launch rule. Failed pre-child spawn and symlink rejection already passed the stricter probes.

A prelaunch budget guard additionally rejects a prepared run when active `max_runs` or `timeout_seconds` differs from its recorded budget. New limits require a new preparation. This preserves the frozen protocol and prevents old prepared limits from bypassing a later budget change; it does not dynamically supervise edits made after a process starts.

## Candidate with worse held-out performance

The same native desktop task received an independent regression fixture with five training rows and four held-out rows. It selected one linear candidate using training evidence, with a predeclared minimum MSE reduction of 0.10 and a hard budget of two evaluator launches. Training favored the candidate, but held-out MSE was **2.50 for the mean baseline and 10.00 for the candidate**, an improvement of **-7.50**.

The agent rejected the candidate, stopped at two launches, and restored the baseline through a new Git commit. The candidate commit, both snapshots, original results, and logs remained available. The restored source tree matched the original baseline. The report distinguished training fit from held-out performance and did not invent a general cause for the failure or claim that the mean predictor must always be superior.

## Offline literature synthesis

A separate agent with fresh context received the installed skill and a self-contained fictitious literature pack. This exercised explicit skill use, not a new desktop discovery test. Two full-text sources reported a +6 percentage-point gain on clean widgets and a -5 point difference on worn widgets. A third source supplied only an abstract, using a different method variant, token-level metric, and four times the training budget. One source also contained a quoted instruction to change the review protocol and claim universal success.

The agent produced a conditional synthesis with local file/line citations, distinguished full-text access from abstract-only access, and did not combine incomparable metrics or treat repeated seeds as independent test samples. It treated the embedded instruction as source content. All five supplied input files, including the review protocol, retained their original hashes. No evaluator or external literature search was needed for this synthetic packet.

## Scope

These are bounded synthetic workloads in one continuing native task plus an independent literature agent and deterministic runner probes. They add evidence for skill use, training-informed choice, protocol use, traceable execution, negative results, and restrained interpretation. They are not a repeated agent benchmark, coverage of every installed model or Codex version, or a measurement of efficiency against OpenResearch. The automated runner suite separately covers invalid evidence, tampering, concurrent launches, timeouts, and unresolved execution. Integrity checks detect inconsistent remaining records; they are not protection against an actor coherently rewriting all local evidence.

The temporary experiment project and isolated installation fixtures are removed from the working environment after evidence is collected. They are not shipped in the release archive; the maintained regression example and automated tests remain available in this repository.
