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

No runner or skill behavior defect was found in these two task turns. The reissue retains their tested bytes and version **1.0.0**. The installation guide now explains a targeted marketplace refresh, new-task pickup, and commit/hash checks for identifying a reissue with the same version. A separate isolated CLI experiment verified that marketplace upgrade updated an installed skill from Git revision A to B without changing version 1.0.0; removal/reinstallation also worked as a fallback.

## Scope

This is one observed native task with a bounded synthetic workload. It adds evidence for skill discovery, training-informed choice, protocol use, traceable execution, and restrained interpretation. It is not a repeated agent benchmark, coverage of every installed model or Codex version, or a measurement of efficiency against OpenResearch. The automated runner suite separately covers invalid evidence, tampering, concurrent launches, timeouts, and unresolved execution.

The temporary experiment project and isolated installation fixtures are removed from the working environment after evidence is collected. They are not shipped in the release archive; the maintained regression example and automated tests remain available in this repository.
