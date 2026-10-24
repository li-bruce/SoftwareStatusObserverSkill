# VibeLens rename acceptance

Requested on 2026-10-24. Local checks passed; publication checks are pending.

## Scope

The public product name, Skill folder/invocation, current documentation,
introduction and GitHub repository become VibeLens. Runtime code, protocol and
schema identities, project graph IDs and saved-view namespaces retain their
existing behavior. The installer gains explicit backup-based migration from
`business-observer` and a selectable agent skills directory.

Raw historical transcripts, logs, screenshots and application ZIPs remain
unchanged. Fifteen source links in rendered historical reports are pinned to
their original paths under `v0.7.0`; the surrounding statements stay unchanged.

## Local results

| Check | Result and evidence |
| --- | --- |
| Skill metadata | The standard Skill validator passed with `name: vibelens` and `$vibelens` in the agent prompt. |
| Package integrity | [Package check](package.log): references resolve and 104 copied runtime modules match. |
| Installation and migration | [Six regression tests](installation.log): fresh install, overwrite refusal, explicit legacy backup, custom files and layouts retained, custom skills directory, copy failure safety and final-move rollback. |
| Runtime compatibility | [Archive manifest](../release-v0.7.1/manifest.json): all 137 runtime/script/asset files retain their original bytes. |
| Executable source | [92 Python modules](python-equivalence.json) and [20 JavaScript modules](javascript-equivalence.json) retain equivalent executable syntax compared with `v0.7.0`. This check does not claim arbitrary semantic equivalence. |
| Historical evidence | All 1,850 original non-Markdown review/assessment/release files retain their Git content identity. [Fifteen source-navigation links](historical-links.json) are pinned to `v0.7.0`; other report bytes, including line endings, are retained. |
| Delivery example | [Verification](examples/delivery-verification.log) passes after a new change, source inspection and candidate-bound review. Business expectations are unchanged. |
| Team archive example | [Verification](examples/team-archive-verification.log) passes through the same existing change gates, including independent application tests. |
| Introduction | [Actual Chrome result](site-local/result.json): renamed brand and install prompt, seven views in both languages, language switch, 390px layout, and recording/replay in the separate walkthrough; no page errors. |
| Installable release | The [Skill ZIP](../release-v0.7.1/archives/vibelens-v0.7.1-skill.zip) contains all 172 files. Every entry was read back and checked against its source SHA-256. |

The first validator attempt used a Python environment without the optional YAML
reader. Validation passed using the available Python environment with PyYAML.
The JavaScript example setup needed its existing `BO_ADAPTER_HOME` configuration.
A Windows test subprocess initially decoded UTF-8 output using the default console
encoding; the test launcher now requests UTF-8 explicitly. These setup issues did
not require changing runtime logic or weakening a check.

## Publication

The GitHub repository is now `li-bruce/VibeLens`, retaining repository ID
`1425417229`. The current checkout's `origin` uses the new URL. The local Codex
installation was migrated with a full backup outside the active skills directory.

The complete repository suite will run in the existing GitHub matrix (Windows and
Linux, Python 3.11 and 3.13), alongside live database checks. New Pages asset
identity, deployed-browser checks, release SHA-256 and a public fresh-install
receipt will be added after publication. The previous release remains unchanged.
