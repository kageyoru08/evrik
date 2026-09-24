# Evrik release qualification and development record

This record preserves the qualified research behavior and its limits across the rename from Research Lab to Evrik. The original ten plugin payload files were frozen at `9fbe661436d3b7e7819f62ee5da0485ccfc81bda`, manifest version `1.0.0`. The subsequent documentation/package release at `d27a243e52effcdee344a5adb03f614554bee608` preserved those ten hashes. Evrik 1.0.0 changes the plugin identity, metadata, paths and one snapshot marker string; it does not claim byte identity with the older payload. The authoritative installed identity is version plus exact Git commit and payload hashes. The maintainer explicitly reissued `v1.0.0` for Evrik; its previous target `5966d77744030c4cdd1470588c16452d0ce78b8b` remains in Git history.

The synchronous standard-library runner supports trusted foreground local Git experiments on Windows and Ubuntu with Python 3.11 and 3.14. The package supplies research guidance, exact source snapshots, conservative launch accounting, reconciliation and supported native source/evidence reading. It is not a security sandbox or durable process supervisor. Scientific acceptance remains separate from execution and evidence validity.

## Accepted pre-rename verification

CI run [35818855390](https://github.com/kageyoru08/evrik/actions/runs/35818855390), attempt 1, reports all six jobs successful for the frozen payload commit: four runner OS/Python combinations and native distribution lifecycle checks on Windows and Ubuntu. Independent review accepted all 134 downloaded evidence files, including 104 passed fault/collision reports and 79 tests in each runner combination; one Windows skip and two Ubuntu skips are platform-specific. Development-branch public-origin steps are skipped and do not count as public release verification.

The existing configured Git marketplace was refreshed to the frozen payload commit through native CLI 0.155.1. All ten installed payload hashes match Git blobs; only the marketplace ref changed in the host configuration. A zero-turn listing observed an enabled skill, both trusted hooks, current GPT-6 Astra/Sol and supported efforts, no loader errors and normal native closure. That CI's distribution jobs used CLI 0.156.1. These are observed versions, not a claim about every CLI release.

## Fresh H01 observations

The four required tasks passed on the same frozen installed payload. Their sources were authored after the freeze, with the autonomous first outcome accepted before companion source authoring. Each first outcome was preserved and independently graded. The failed statistical predecessor remains visible alongside its prospectively repaired, unseen replacement; there was no coaching or favorable unchanged retry.

| Task | Observed native configuration | Required axes | Shared time cap | Result |
| --- | --- | --- | --- | --- |
| H01-AUTONOMOUS-MESH6 | Astra GPT-6 high; one Sol GPT-6 medium peer | 7 | 2,400 s | PASS (7/7; ROOT accepted) |
| H01-RECOVERY-BRIDGE6 | Astra GPT-6 medium | 6 | 900 s | PASS (6/6; honest incomplete recovery close; ROOT accepted) |
| H01-LITERATURE-BRIDGE6 | Sol GPT-6 medium | 13 | 1,800 s | PASS (13/13; source-bounded synthesis; ROOT accepted) |
| H01-STATISTICAL-BRIDGE6 | Sol GPT-6 medium; one Astra GPT-6 medium peer | 7 | 1,800 s | FAIL (5 PASS; A3 UNKNOWN, A5 FAIL), retained development evidence |
| H01-STATISTICAL-BRIDGE7 | Sol GPT-6 medium; one Astra GPT-6 medium peer | 7 | 1,800 s | PASS (7/7; valid negative scientific result; ROOT accepted) |

Effort and participant count reflect task difficulty and independent work that benefits the decision. Configured native receipts establish requested selection, not backend attestation. Historical medium and older-model results retain their actual identities and bounded evidence; they are not relabeled as this cohort. Model diversity and agreement are not proof of correctness or demonstrated cost savings.

QUEUE6 and RENDER6 remain preserved failed first outcomes; valid synthetic science alone did not satisfy every evidence, checkpoint and peer obligation. CACHE6 also remains a preserved failed first outcome: its original all-PASS report has a separate A4 FAIL correction because the peer discarded a returned command exit and marked it external-only. R4 changes one reference to put exact guidance paths and complete command-result forwarding in the initial peer packet before its first tool. Prior saved-byte association and message-order guidance remain. MESH6 and STATISTICAL-BRIDGE7 supply current native behavioral evidence for that guidance; local diagnostics alone do not qualify actor behavior.

STATISTICAL-BRIDGE7 completed normally in 937.186 seconds of its 1,800-second cap, including live Git review. Exactly two real runs used two of four global slots. Twenty independent pairs gave A=915, B=885 and gain=30, clearing the numerical threshold of 25. The exact one-sided sign tail was 392313/524288, above 1/16, so retaining A was the correct scientific decision. The replacement contract separates an immutable checkpoint snapshot from later native closure evidence and requires a visible finding for each readback page. Sixteen complete pages, sixteen ordered findings and one current receipt were independently matched. The predecessor's conflicting checkpoint contract and missing page findings remain failures, rather than being retrospectively waived.

## Distribution verification

The final documentation/package revision receives its own six-job [Verify workflow](https://github.com/kageyoru08/evrik/actions/workflows/ci.yml) and independent package review. Public distribution requires the main-branch run for the exact published commit to pass the `Verify published commit through the public marketplace origin` step on both Windows and Ubuntu. A successful development-branch run alone is insufficient. Final host verification binds the native Git marketplace ref and installed hashes to that same public commit. The external release record binds the resulting commit, CI artifacts, host receipts and recoverable cleanup, avoiding a self-referential commit hash in this file.

Supported cross-platform claims cover the runner and native distribution lifecycle. The model-driven observations here ran on Windows; Ubuntu model execution is not claimed. Qualification means the declared scope and gates passed, not a universal absence of bugs.

## Retained coverage and interpretation

The release matrix reuses earlier evidence only where the changed guidance does not affect the measured requirement. Reuse is explicit; earlier model identities, failures and evidence limits remain part of the record.

| Requirement | Retained observation and boundary |
| --- | --- |
| Autonomous investigation and checkpoint (A01/G01) | ADEV-LUNA-R1 supplies the older Luna investigation's valid science/history predicates. Its overall grade remains FAIL (5/7); incomplete final operational reconciliation and reader-delivery failures are preserved. MESH6 supplies the fresh Astra investigation and current mandatory behavior; STATISTICAL-BRIDGE7 supplies the fresh statistical checkpoint and native closure tail. |
| Interrupted-record recovery (A02) | Historic Astra A02a and Luna A02b-r2 inspect real fault-produced states without refund, automatic retry, invented completion or persisted-PID action. The latter has a disclosed interpreter-directory lookup; original A02b memory attribution remains unresolved. RECOVERY-BRIDGE6 adds fresh R4 recovery evidence. |
| Actual compaction (A03) | Two retained native compaction-completed events have correct later turns in their respective same threads; one preserves unresolved execution. A change of thread or connection is excluded. These are historical Astra/Luna continuations, not new Sol executions or fresh independent trials. |
| Routing and authority (G02) | Retained explicit/natural loading, simple-fact non-trigger, literature without Git, delegation-unavailable handling and lower-trust instruction refusal combine with current mixed-family integration. An earlier initial-handoff association limit applies only to that already-associated material. |
| Literature and adverse sources (L01/L02) | The earlier Astra LDEV-SOURCES-M1 13/13 pass and current Sol LITERATURE-BRIDGE6 13/13 pass each use three primary-source families. Simulated access failure, abstract-only content, misleading secondary claims and injection are labeled and treated separately from actual live access. |
| Statistical reasoning (S01/G01) | Historic Astra S01a retains a valid negative paired-data result and its infrastructure interruption; it spans an administrative continuation and is not an uninterrupted mission. Fresh Sol/Astra STATISTICAL-BRIDGE7 independently passes all seven current axes with a separate valid negative decision. |

Record hashes and explicit independent dispositions bind this retained evidence in the final release matrix. Scope uncertainty in historical cases is not converted into universal scope compliance. No historical outcome occupies one of the four fresh H01 slots.

## Efficient verification

Cheap source/interface and argument checks precede native model work. Targeted controls distinguish fixture or harness faults from product faults, and actual failures remain preserved. Unchanged source mechanisms and unaffected matrix rows are reused, while changed agent-facing guidance receives fresh behavioral cases. Source, control and setup checks receive scoped independent review; each model case receives a separate first-outcome grade. Only the failed statistical slot was replaced after its prospective contract repair; the other three accepted cases were retained on identical payload bytes. Documentation-only packaging receives package and CI checks without another model cohort. Routine solo work stays solo; consequential collaboration uses one participant from each current Astra/Sol family, with effort matched to difficulty.

The observations do not establish a causal accuracy gain from the model pairing, a controlled effort comparison or a monetary saving. Per-task native counters are descriptive and are not summed across parent/child tasks because their aggregation relation is unknown. Synthetic-case success qualifies the recorded behavior and scope, not general research accuracy.

## Historical frozen payload SHA-256

| Path beneath `plugins/research-lab` | SHA-256 |
| --- | --- |
| `.codex-plugin/plugin.json` | `58d3c65697897d23610ee9f3003a9b6380fe1f9452d01f2ba4c1a8e0eaa50723` |
| `LICENSE` | `bf0ba223fa49236c638a4807a856242228f631869f53993a44b582377d59b0cd` |
| `hooks/hooks.json` | `da32979685e9d19c7c68f9574fd613d834133ef0e68197ead6645aac3a199edc` |
| `skills/research/SKILL.md` | `831567ab592c1135765e278e06e5157a221a186ff852b3fd351992f6e765735c` |
| `skills/research/agents/openai.yaml` | `0a677418309dff1666dc7040c6073f4fef7777a499fb1f0a48ad162646f1729a` |
| `skills/research/references/evidence.md` | `d3373c590688da64d9af259d7dcc6157096503cafeae32c07186849b2a2c1f0a` |
| `skills/research/references/experiments.md` | `633121c73ee9734ff1e9d212fec24b39932dbf203fdeb43a6817a202e8cd90eb` |
| `skills/research/references/literature.md` | `58f7f7f1eacdf2c727346cf44b237514b1aa03cc182c90b8c1ca63debc1ee85d` |
| `skills/research/references/parallelism.md` | `c5afc4d6d9161b010058de2d30910ae5152334195595752bf07e0f93f3efd9d7` |
| `skills/research/scripts/research.py` | `99b9347e79049a38211c1b87f61ec70868b2ab5d046dc06fddfb734429d0db14` |

## Public acceptance and maintenance

The final pre-rename public-main run [35843506721](https://github.com/kageyoru08/evrik/actions/runs/35843506721), attempt 1, completed all six jobs at `d27a243e52effcdee344a5adb03f614554bee608`. Its collected evidence contains 144 files, 104 passed fault reports and 79 tests per Windows/Ubuntu × Python 3.11/3.14 combination, with skips 1/1/2/2. Both operating systems installed the exact commit from the public origin. P01, the independent P02 public-artifact review and ROOT acceptance completed; a 24 September read-only audit rechecked the 35 final matrix bindings and 18 cleanup-gate bindings. The four accepted fresh model cases and preserved failures above keep their original attribution and scientific limits.

Maintenance retained the complete historical evidence in a verified archive (29,845 files), copied 524 active evidence files byte for byte, and removed 73 obsolete work/cache copies. The later owned-project cleanup removed exactly 61 fixture directories (5,188 files; 17,273,432 logical bytes) and 61 project trust keys, with 20 recovery ZIPs and 5,597 archived members retained. Private configuration backups are kept outside this repository. These are logical file counts and sizes, not a claim about physical disk allocation or model cost savings.

## Evrik 1.0.0 rename boundary

The current marketplace, plugin identifier, display name, repository URL and plugin directory are `evrik`, `evrik@evrik`, **Evrik**, `kageyoru08/evrik` and `plugins/evrik`. The functional skill name `research`, `.research/` data, evidence formats and `RESEARCH_*` environment contracts remain compatible. References to the former name in migration instructions, the frozen table and the test's historical baseline are intentional provenance, not active registrations.

Seven payload files remain byte-identical to the accepted release. The three changed files are the manifest (name, URL and display name), skill display metadata, and the runner's human-readable snapshot marker. Runner logic, research instructions, references and hook definitions are unchanged. Existing scientific evidence therefore remains bounded evidence for those mechanisms; the rename is not a fresh model qualification or a claim that every future result will be identical.

The adapted native distribution check installs the exact historical package, explicitly uninstalls it, removes its marketplace, installs Evrik, verifies refresh/failure retention and uninstall/reinstall, and checks that unrelated configuration, canary hooks and existing `.research/` records survive. Public-origin installation remains a separate Windows/Ubuntu gate. These checks send zero model turns and do not claim hook execution. Exact rename commit, terminal CI artifacts, host installation and cleanup receipts are bound in the external rename acceptance record.

The first rename candidate used 1.0.1 at `3a7f91a92431c80c6705cbf94369ba60cce84a2c`. Its [six-job CI run 36008565927](https://github.com/kageyoru08/evrik/actions/runs/36008565927) passed with 148 artifact files, 104 fault reports and 79 tests per runner combination (skips 1/1/2/2). The maintainer then selected 1.0.0. That correction changes only the manifest version within the payload. Its distribution and host-installation checks use the final version and exact commit; the unchanged runner's existing tests are reused. A manual `distribution_only` workflow input supports this bounded check without repeating the four runner jobs. Ordinary push and pull-request runs still use the full matrix. No additional model cohort is needed for the version correction.

### Payload before logo adoption (85bce2a)

| Path beneath `plugins/evrik` | SHA-256 |
| --- | --- |
| `.codex-plugin/plugin.json` | `ba10aa0b594a4ae34708ad30dabb2fe095d6c92e57b901a211ef56b89a6dba83` |
| `hooks/hooks.json` | `da32979685e9d19c7c68f9574fd613d834133ef0e68197ead6645aac3a199edc` |
| `LICENSE` | `bf0ba223fa49236c638a4807a856242228f631869f53993a44b582377d59b0cd` |
| `skills/research/agents/openai.yaml` | `200e948b26a7109ab1eabe1d873fb73b891b5aed8017f4b97328d5c9da1a2013` |
| `skills/research/references/evidence.md` | `d3373c590688da64d9af259d7dcc6157096503cafeae32c07186849b2a2c1f0a` |
| `skills/research/references/experiments.md` | `633121c73ee9734ff1e9d212fec24b39932dbf203fdeb43a6817a202e8cd90eb` |
| `skills/research/references/literature.md` | `58f7f7f1eacdf2c727346cf44b237514b1aa03cc182c90b8c1ca63debc1ee85d` |
| `skills/research/references/parallelism.md` | `c5afc4d6d9161b010058de2d30910ae5152334195595752bf07e0f93f3efd9d7` |
| `skills/research/scripts/research.py` | `b6a0941bdd297e52c30e9f63e382b512bbedb56ccc660a64a5159c1dcb1ec164` |
| `skills/research/SKILL.md` | `831567ab592c1135765e278e06e5157a221a186ff852b3fd351992f6e765735c` |

## Dark logo maintenance

The selected logo is a manually drawn white E on a dark background, supplied as SVG and a 512 px PNG. The plugin interface, skill icons and README share these assets. The maintenance version remains 1.0.0. Relative to `85bce2a05c26da3ec8ec70e61398c9e6fe186279`, only the manifest and skill display metadata change among the ten existing payload files; two logo assets are added. The other eight files, including the runner, research instructions, references and hooks, are byte-identical.

The package audit keeps the historical ten-file baseline separate from the current twelve-file inventory. Distribution checks cover the changed package and native asset metadata; accepted runner tests and research observations are reused within their existing limits. The logo does not provide new scientific or model-behavior evidence.

### Current payload SHA-256

| Path beneath `plugins/evrik` | SHA-256 |
| --- | --- |
| `.codex-plugin/plugin.json` | `53456c449dbe193bc5cfb53ef9218927ed3cecba66052f7cb9ed5db93fac5078` |
| `LICENSE` | `bf0ba223fa49236c638a4807a856242228f631869f53993a44b582377d59b0cd` |
| `hooks/hooks.json` | `da32979685e9d19c7c68f9574fd613d834133ef0e68197ead6645aac3a199edc` |
| `skills/research/SKILL.md` | `831567ab592c1135765e278e06e5157a221a186ff852b3fd351992f6e765735c` |
| `skills/research/agents/openai.yaml` | `2cc82df1686f3fa541499518b474e1a58747b5be89e4778edf5b6137e2df563f` |
| `skills/research/assets/logo-dark.png` | `2982edad8e2f2d3ba921045c7e45af2d0edb3521a95c921822170476bacd225e` |
| `skills/research/assets/logo-dark.svg` | `076e8bb5289253434ed245a35980c71f243cc2a8023cc51ecc2430a7f3d16d0a` |
| `skills/research/references/evidence.md` | `d3373c590688da64d9af259d7dcc6157096503cafeae32c07186849b2a2c1f0a` |
| `skills/research/references/experiments.md` | `633121c73ee9734ff1e9d212fec24b39932dbf203fdeb43a6817a202e8cd90eb` |
| `skills/research/references/literature.md` | `58f7f7f1eacdf2c727346cf44b237514b1aa03cc182c90b8c1ca63debc1ee85d` |
| `skills/research/references/parallelism.md` | `c5afc4d6d9161b010058de2d30910ae5152334195595752bf07e0f93f3efd9d7` |
| `skills/research/scripts/research.py` | `b6a0941bdd297e52c30e9f63e382b512bbedb56ccc660a64a5159c1dcb1ec164` |
