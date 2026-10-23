# Confirm the user's intended business graph

Use this during initial setup or when behavior requirements change. Express the user's current understanding as task, business, and state networks, then confirm that understanding in conversation. Do not infer a comprehensive business process, recommend business policies, or expand the user's scope.

## State the current understanding

Read the request, previous answers, and adopted project rules. Identify the stated goal, actors, business objects, triggers, actions, and effects. Present short sentences and a focused graph. Preserve stated concurrency, dependencies, shared resources, loops, and multiple entry points. Do not add approval, compensation, or recovery mechanisms from a generic business template.

Every top-level node represents a supplied behavior or condition and will map to real states, core functions, and parameters. Distinguish user statements, project rules, inferences, and unanswered questions by source. Leave missing information unspecified or pending; do not guess a definitive rule or claim business completeness.

## Ask only to confirm meaning

Keep necessary clarifications and counterexamples. A counterexample tests whether the current interpretation matches the request; it does not discover additional requirements. Identify the statement or graph relation behind the question and how the answer changes the graph. A merely conceivable situation is insufficient reason to ask.

| Existing context | Appropriate clarification |
|---|---|
| Several checks are described, but “download after the check passes” is ambiguous | Which existing check controls download? |
| Several runs coexist and the user says “cancel this task” | Does this mean one run or all runs of that task? |
| A new statement directly contradicts a confirmed relation | Does the new statement replace the previous rule? |

Do not ask again when an answer is explicit, follows directly from adopted rules, or concerns an ordinary reversible implementation choice. Present alternative interpretations and their consequences without recommending a business option. Usually ask only 1–3 necessary questions per round; do not interrogate the user through a checklist of permissions, concurrency, cancellation, and other topics.

The user answers in the development conversation. Web only displays the discussed graph. Copy, layout, and behavior-preserving refactors need only reconciliation with the existing graph. End confirmation when the current request is represented consistently; do not require an additional requirements-document approval.

A recommendation, preselected option, silence, or elapsed time is not an answer. An explicitly delegated choice may be recorded as `delegated_choice`, with its authorization scope and rationale. Permission to decide implementation details does not authorize changing business meaning. Do not solicit delegation to bypass confirmation.

## Update the same graph

Use confirmed changes to update triggers, prior states, conditions, parameters, next states, effects, and stated waiting/recovery behavior. Preserve stable node IDs. Reconcile source mappings, execution declarations, and scenarios for those rules. Clarification counterexamples test understanding; validation counterexamples test adopted rules. Neither automatically creates requirements.

A partial answer resolves only the answered part. Keep the previous decision and change source when a rule changes. Do not mark contradictory meanings as simultaneously confirmed. Approval of a graph region does not approve assumptions outside it or all implementation outcomes.

The user or another Skill may refine business rules and hand them back. Record document/conversation location, author, and confirmation status. Adopted rules may be `project_rule`; unconfirmed external suggestions remain candidates, never fabricated `user_answer`. Update affected nodes, bindings, and checks without weakening source, runtime, or business gates.

## Minimum checkable record

Maintain `discovery.json`. Record supplied behavior and necessary understanding checks. `decisions` may be empty when nothing is unresolved. Scripts validate records and references; they do not discover every missing business rule. See the [example](../assets/discovery.example.json).

- `sources`: `id`, `kind` (`user/project_rule/inference/assistant`), original `text`, and `locator`. Label simulated replies as test evidence, not human feedback.
- `networks`: `id`, `title`, `actors`, `trigger`, `outcome`, `nodes`, `edges`. Nodes have `id/label/kind/source_refs`; edges have `id/from/to/relation/label/source_refs` and optional `decision_refs`. Loops are supported. Shared meaning may reuse sources across networks; node identities remain unique.
- `decisions`: `id/topic/question/why/affects/blocking/status/source_refs`; optional `priority` (1 first), `depends_on`, 2–3 `options` with `id/label/effect`, and `asked_in` pointing to an actual assistant question.
- Status is `open/resolved/assumed/deferred`. Only `resolved` resolves a blocking ambiguity. `resolution` contains `kind` (`user_answer/existing_rule/delegated_choice`), `text`, and `source_refs`; delegated choices also need `rationale`. Use `note` for assumptions and deferred scope. Do not hide a blocking question by marking it nonblocking.
- After implementation, `model_nodes` references original graph IDs. External unimplemented nodes need `outside_reason`. Important decisions link `requirements/model_nodes/checks` to real requirements, graph nodes, and acceptance items.
- Changed decisions require `changes` entries with `id/decision/previous/source_refs/reason`; `previous` is the complete old decision. Compare using `--previous` or change checks; never silently erase an answer.

```text
python SKILL/scripts/requirements_dialogue.py validate --file discovery.json
python SKILL/scripts/requirements_dialogue.py questions --file discovery.json
python SKILL/scripts/requirements_dialogue.py check --file discovery.json
```

`questions` selects from recorded open decisions. Already asked questions appear under `awaiting_answers` instead of being asked repeatedly. It does not discover every ambiguity in natural language. Reconcile the graph after changes; an empty question list is not proof of complete rules.

New projects add `"discovery": "discovery.json"` to `sync.json`, making it part of `change_sync verify/check`. Check implemented mappings with:

```text
python SKILL/scripts/requirements_dialogue.py check --file discovery.json --intent intent.json --model behavior.json --acceptance acceptance.json
```

Unresolved blocking questions, unsupported answers, missing business-node mappings, or missing requirement/check links fail delivery. Record and script changes invalidate old candidate evidence. Legacy projects without `discovery` retain compatibility behavior; disclose that this check is not connected.

Compare the user's words and feedback to judge intent alignment. JSON validation cannot establish that alignment or exhaustive business coverage. Existing strict definition, source mapping, and runtime checks remain required.
