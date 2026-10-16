# Analysis and decisions

## Understand the problem

Extract the desired outcome, current behavior, users, affected boundary, constraints, and observable success. Distinguish requirements from the user's proposed implementation. If the implementation conflicts with the outcome, explain the concrete tradeoff and recommend a direction. Ask only questions whose answers materially change behavior, risk, or scope; inspect available evidence first.

For a defect, capture the input, expected/actual result, environment, and smallest reproducible path. For a feature, identify valid states and important invalid transitions. Consider measurable latency, availability, accessibility, privacy, compatibility, and cost only where relevant. Do not convert an ordinary task into a requirements ceremony.

## Understand the system

Start at the relevant entry point and follow callers, data transformations, persistence, and external effects. Inspect manifests, tests, configuration, and generated-code boundaries. Map ownership and dependencies using file/symbol evidence. Distinguish static references from dynamic wiring and runtime observations.

Identify the change surface: direct consumers, public contracts, migrations, asynchronous workers, platform-specific paths, and release coupling. An uninspected dependency remains uncertain. Use semantic tools when available, but inspect their results against source and build context.

## Decide

For a meaningful choice, compare the smallest viable options against the task's actual constraints. Include keeping the current design when it can satisfy the requirement. Evaluate correctness, complexity, operability, security, performance, compatibility, and ongoing maintenance. Avoid arbitrary numeric scoring without measured inputs.

Prefer a reversible decision when uncertainty is high. Name what observation would invalidate the recommendation. An ADR is useful for consequential long-lived decisions; a short conversation record suffices for routine work. Do not invent benchmarks or claim that a pattern is universally best.

## Plan and hand off

Define each task by intended behavior, allowed files/components, dependencies, non-goals, and acceptance evidence. Separate Engineering decisions from Coding implementation, Test verification, and Security abuse cases. A role handoff is not permission to spawn agents or expand access. Preserve applicable delegation restrictions.

Order work so that uncertain contracts are resolved before dependent implementation. Keep a task small enough to review but large enough to deliver a coherent outcome. Revise the plan only when evidence warrants it. Respect existing authorization rather than repeatedly requesting it.

## Compact working record

Use only fields that matter; keep the record in the conversation unless a durable artifact is justified.

| Field | Content |
| --- | --- |
| Outcome and scope | Required behavior, protected boundaries, explicit non-goals |
| Evidence | Relevant source locations, observed behavior, versions |
| Unknowns | Material unanswered questions and assumptions |
| Decision | Selected approach, tradeoffs, rejected relevant alternatives |
| Work | Bounded steps and ownership |
| Verification | Observable acceptance and narrow commands/checks |
| State | Active, blocked, stopped, or complete; last verified result |

At completion report changes, evidence, and remaining limitations. Stop after the requested outcome and relevant verification are satisfied.
