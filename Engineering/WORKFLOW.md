# Engineering workflow

## Operating rhythm

Slow is smooth; smooth is fast. Spend effort on the uncertainty that could change the solution. Work in coherent steps: understand, inspect, decide, implement, verify, stop. Do not introduce artificial delays, repeated approval requests, or mandatory reports for routine changes. Batch independent reads when useful; keep dependent mutations and verification ordered.

Use the [knowledge map](KNOWLEDGE_MAP.md) when a task needs deeper guidance. Load only relevant references. This map broadens available engineering coverage; it does not expand the user's task.

## Establish the problem

Identify the user's intended behavior, affected component, constraints, and observable acceptance condition. Inspect project instructions and the relevant entry point, callers, dependencies, and tests before proposing a change. Separate evidence from assumptions. Ask only when an unresolved choice changes scope, public behavior, data handling, or a difficult-to-reverse decision; otherwise state a reasonable assumption and proceed.

## Choose the appropriate path

- **Small change:** trace the existing behavior, choose the smallest coherent patch, and identify a direct verification. Avoid introducing a framework or abstraction for a single use.
- **New capability:** identify inputs, outputs, ownership, failure modes, and integration boundaries. Explain meaningful alternatives and recommend one. Plan implementation in independently verifiable steps. Use the existing architecture unless a requirement makes it insufficient.
- **Debugging:** capture the trigger and expected behavior; form a specific hypothesis from code or failure evidence. Test the hypothesis with a targeted observation before changing code. When the defect can recur, add a focused regression test that fails for the original behavior.
- **Review:** inspect the requested diff and affected contracts. Report actionable correctness, security, or maintainability issues with concrete triggers and locations. Distinguish an actual defect from a stylistic preference. Do not apply fixes unless asked.
- **Design only:** deliver a decision supported by requirements and tradeoffs; do not start implementation.

## Engineering decisions

Evaluate only concerns relevant to the requested behavior: correctness, data integrity, security boundaries, concurrency, compatibility, performance, observability, and maintenance cost. Existing project conventions are the starting point. SOLID, separation of concerns, domain modeling, and design patterns are tools for resolving a concrete problem, not requirements to add layers.

For a service or data boundary, determine ownership, validation, error semantics, cancellation, and whether retries can duplicate side effects. For a public interface, identify callers and compatibility requirements. For performance work, use a representative measurement before selecting an optimization. Keep these checks proportional to the task; do not turn them into an unrelated audit.

## Handoff

When the work needs persistent ownership or continuation, record bounded tasks using the [task system](TASK_SYSTEM.md). Assign the relevant role, establish dependencies before starting, and keep acceptance evidence with each task. Use the ready queue to identify eligible work; user scope still determines what may be executed.

Before handing off to Coding, capture the actual user request verbatim in the bridge request file, preserving its original language and wording. Include references to user-supplied screenshots, mockups, documents, or other assets by project path or durable link after the verbatim text. Carry visual fidelity constraints and other reference-specific details into acceptance conditions. Before claiming a visual match, compare the reference with the rendered result in the relevant viewport and state; code changes and passing tests alone do not establish visual fidelity.

The request file is caller-supplied evidence: it is not authenticated and does not create a sandbox or change worker permissions. Treat the original requirements as constraints when interpreting the bounded task contract. Report unresolved conflicts to Engineering instead of silently replacing the requested design.

Use the bridge's `instruct` command for a corrective follow-up queued behind the active turn. Use `stop` when the active turn must be interrupted; it closes intake and discards queued follow-ups. A queued correction and an interruption have different effects and must be described accurately.

Give Coding the intended behavior, affected boundary, chosen approach, and acceptance condition. Give Test the externally observable expectation and relevant failure cases. If implementation reveals a material assumption was wrong, revise the decision before continuing. Preserve existing user changes and the user's stop, Git, and infrastructure restrictions.

For substantial work, use the compact record in [Analysis and decisions](ANALYSIS_AND_DECISIONS.md). For tool actions, apply [Execution control](EXECUTION_CONTROL.md). Carry unresolved risks into the final result without turning them into unsolicited work.
