# Authorization patterns: identify rules before selecting questions and tests

This checklist supports intent confirmation, source integration, and test selection. It is neither an authorization engine nor a mandatory feature list. Record actual rules, engine, and scope. Direct parent-child permission is only one example: preserve valid inheritance, but never invent inheritance for a direct-only rule.

## Rule, facts, evaluation

Define rules once for many subjects/objects. Database tuples and request context provide particular inputs. Evaluation instances reference rules, inputs, and source and expand on demand. Do not materialize every subject-operation-object combination.

Basic constructs include direct relations, same-object relation references, related-object references, unions, intersections, differences, and conditions. Preserve operators, direction, and scope, not untyped edges. [OpenFGA language](https://openfga.dev/docs/configuration-language)

Use the following only for behavior already in scope. Questions/counterexamples confirm meaning; they do not recommend mechanisms or complete the user's business process. Neither probes nor tests inherit example rules by default.

| Pattern | Clarify if ambiguous | Graph/runtime evidence | Applicable tests |
|---|---|---|---|
| Direct grants/ownership | Subject, object type, action, version binding | Actor/object/action/grant/read source | Valid grant, wrong actor/object/action, absent/revoked grant |
| Groups/nested membership | Membership rights, nesting, service accounts | Membership, authorized userset, actual path | Join/leave, nesting, similar group names, wrong type |
| Roles/custom roles | Global/tenant/resource scope and operations | Assignment, role-permission map, scope | Same role/different scope, changed role, unauthorized action |
| Direct scope/inheritance | Direction, levels, stopping boundaries | Direct facts vs derivation, path/rule identity | Direct allow, valid inheritance, undeclared inheritance denied, reparent, boundary crossing |
| Alternative paths OR | Whether any branch suffices after revocation | Branch identity, evaluated/short-circuited, aggregate | First only, second only, none, remaining alternative after revoke |
| Required conditions AND | Which qualifications are jointly required | Every operand/combination; omitted prerequisites remain boundaries | Each condition missing alone, all true, missing evidence |
| Exclusions/blocklists | Expression scope and precedence | Excluded set, query scope/completeness, operand | Add/remove deny, allow+deny, parentheses, query failure |
| Public access/subject types | Authenticated/type-specific/anonymous | Typed wildcard, identity condition | Matching/wrong type, anonymous, return to private |
| Tenant/organization/sharing | Current/owning/shared organization constraints | Ownership, memberships, current context/source | Organization switch, same ID across tenants, read sharing cannot manage |
| Time/attributes/request conditions | Clock/expiry/IP/device/parameter sources and bounds | Typed actual values/time/missing fields/result | Before/equal/after threshold, wrong type, missing field, parameter change |
| Temporary relations/delegation/approval | Grantor, redelegation, scope/expiry, self-approval | Persistent vs request-local facts, grantor/delegate/version | No reuse after request, overbroad delegation, revoke, self-approval restriction |
| Resource lifecycle | Archived/locked/deleted state restrictions | Authorization linked separately to state transition/commit | Authorized but wrong state, repeat commit, state changes after check |

Group members may be granted as a userset and roles may be object-scoped. Public relations often restrict subject type; they do not automatically bypass authentication. [Groups](https://openfga.dev/docs/modeling/user-groups), [roles](https://openfga.dev/docs/modeling/roles-and-permissions), [public access](https://openfga.dev/docs/modeling/public-access).

Organization context may constrain the same user's access differently. Contextual tuples need not be persisted. Token validity does not establish unchanged membership. [Organization context](https://openfga.dev/docs/modeling/organization-context-authorization), [token claims/contextual tuples](https://openfga.dev/docs/modeling/token-claims-contextual-tuples).

Exclusion precedence applies only where the model expresses it, not as a universal ReBAC priority. Approval, separation of duties, delegation, and lifecycle restrictions are application compositions, not implicit engine features. [Blocklists](https://openfga.dev/docs/modeling/blocklists).

## Runtime concerns for applicable patterns

| Concern | Required distinction |
|---|---|
| Rule/relation/parameter versions | Record separately; unchanged rules do not keep old results valid. Only record versions actually supplied. |
| Revocation/addition | Track query scope as well as matching grants; new denials/alternatives may change the answer. |
| Missing context/timeouts/cycles/depth | Separate deny, pending input, error, not evaluated, and capture gap. Show cycles/truncation without invented conclusions. |
| Cache/consistency | Preserve requested consistency and actual response basis; old snapshots are not current facts. |
| Check-to-commit changes | Test real transaction/version/atomicity protection. Remote authorization does not atomically protect another database's write. |
| Query/explanation | Label Check, list, read, and expansion separately. Incomplete pagination proves no absence; expansion proves no execution. |

[SpiceDB caveats](https://authzed.com/docs/spicedb/concepts/caveats) may return conditional results/missing context. Respect actual [recursion/depth limits](https://authzed.com/docs/spicedb/modeling/recursion-and-max-depth). [SpiceDB consistency tokens](https://authzed.com/docs/spicedb/concepts/consistency) and [OpenFGA consistency options](https://openfga.dev/docs/interacting/consistency) are not interchangeable database versions. Cross-service commit protection belongs to application design/tests.

## Development integration

1. Record applicable patterns/sources in discovery.json; clarify only unresolved behavioral ambiguity. Do not require groups/inheritance/delegation when absent from the request.
2. Build confirmed allow/deny/boundary/change/unknown/error scenarios. Separate types, tuples, requests, and expectations. Reuse native engine tests where suitable; [OpenFGA tests](https://openfga.dev/docs/modeling/testing) support Check/ListObjects/ListUsers assertions.
3. Bind rule definitions, database reads, functions, inputs, and effects. Capture actual boundaries, never reevaluate permission in the observer. whitebox.json checks key values/results/call identities.
4. Use meaningful mutations: AND→OR, removed exclusion, reversed inheritance, missing tenant/version, incorrect expiry boundary. Failure must come from business assertions, not just a hash change.
5. Preserve operators/rule/instance identity in focused views; unexpanded required operands remain boundaries. Test valid inheritance and forbidden inheritance.

Properties need assumptions: adding grants is generally monotone only for positive relation compositions, not exclusions, upper bounds, or conflicting duties. Define the scope of “irrelevant data” before testing invariance. Covering these patterns does not prove arbitrary policies correct.
