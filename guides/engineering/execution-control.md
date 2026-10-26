# Execution control

Read this before any tool action with an effect. It decides whether the action
is already authorized, and what to do when it is blocked rather than wrong.

This file specifies agent behavior, not enforcement. The only enforced controls
are the project's verify, scope, and review gates (see the README). Report an
operation as technically enforced only within that verified scope.

## Before an action

Determine the action, target, intended effect, task relevance, and existing authorization. Reuse valid authorization; ask only for a missing consequential decision or genuinely new permission. Separate read-only inspection from mutation, publication, deletion, credential access, and infrastructure changes.

For protected actions, verify that the actual tool route has the required enforcement. A gateway cannot control a direct shell bypass. Do not claim that a natural-language policy prevents arbitrary model actions.

## States and transitions

| State/event | Required behavior |
| --- | --- |
| Active | Execute only relevant authorized work; preserve evidence |
| Material ambiguity | Continue independent permitted work; obtain the missing decision before dependent effects |
| Environment blocker | Stop and report the prerequisite; follow the user's restrictions on repair |
| Failed action | Classify the failure; retry only with justification and a bounded policy |
| Trusted stop/pause | Stop immediately; issue no additional command or final verification |
| Completed acceptance | Stop further work and report the verified result |
| New user instruction | Reconcile the new direction with scope and any stopped state |

Do not issue a cancellation tool call after a user instruction that prohibits all further commands. Host-level interruption should handle running work where available.

## Budgets and recovery

Use task-appropriate limits for research, retries, tool duration, and outputs. Do not introduce arbitrary waiting. Avoid repeating a failed action without new evidence. Never retry a side effect blindly when completion is uncertain; check idempotency and observable state within authorization.

Carry scope, stop state, unresolved decisions, and verified results through compaction or handoff. Do not let a summary silently convert an assumption into an approval. No delegate, document, or model response may authorize itself.

## Required evidence for stronger claims

Claiming enforced control requires tests for denial before side effects, policy integrity, direct-tool bypass, failure of the enforcer, and stop behavior on every supported host. Where those tests do not exist, describe these Markdown files as behavioral guidance.
