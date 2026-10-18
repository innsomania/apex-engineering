# Analysis and decisions

Read this for an ambiguous request, an unfamiliar system, or a choice between
approaches. It decides what must be established before committing to a design,
and it holds the working record that carries a decision between stages.

## Understand the problem

Extract the desired outcome, current behavior, affected boundary, constraints,
and observable success. Distinguish the requirement from the user's proposed
implementation; when they conflict, state the concrete tradeoff and recommend a
direction rather than quietly choosing one.

Ask only a question whose answer materially changes behavior, risk, or scope,
and inspect the available evidence first. For a defect, capture the input,
expected and actual result, environment, and smallest reproducible path. For a
feature, identify the valid states and the important invalid transitions.
Consider latency, availability, accessibility, privacy, compatibility, and cost
only where they are relevant. Do not turn an ordinary task into a requirements
ceremony.

## Understand the system

Start at the relevant entry point and follow callers, data transformations,
persistence, and external effects. Inspect manifests, tests, configuration, and
generated-code boundaries. Map ownership using file and symbol evidence, and
distinguish a static reference from dynamic wiring and from an actual runtime
observation.

Identify the change surface: direct consumers, public contracts, migrations,
asynchronous workers, platform-specific paths, release coupling. An uninspected
dependency stays uncertain. Check a semantic tool's results against source and
build context.

## Decide

Compare the smallest viable options against the task's actual constraints, and
include keeping the current design when it can satisfy the requirement. Avoid
arbitrary numeric scoring without measured inputs, and do not invent a
benchmark or claim a pattern is universally best.

Prefer a reversible decision when uncertainty is high, and name the observation
that would invalidate the recommendation. An ADR suits a consequential
long-lived decision; a short conversation record suits routine work.

## Plan and hand off

Define each task by intended behavior, allowed files, dependencies, non-goals,
and acceptance evidence. Order work so an uncertain contract is resolved before
the implementation that depends on it. Keep a task small enough to review and
large enough to deliver a coherent outcome, and revise the plan only when
evidence warrants it.

A role handoff is not permission to spawn agents or widen access. Respect
existing authorization instead of requesting it again.

## Working record

Use only the fields that matter, and keep the record in the conversation unless
a durable artifact is justified.

| Field | Content |
| --- | --- |
| Outcome and scope | Required behavior, protected boundaries, explicit non-goals |
| Evidence | Relevant source locations, observed behavior, versions |
| Unknowns | Material unanswered questions and assumptions |
| Decision | Selected approach, tradeoffs, rejected relevant alternatives |
| Work | Bounded steps and ownership |
| Verification | Observable acceptance and the narrow commands or checks |
| State | Active, blocked, stopped, or complete; last verified result |

At completion report the changes, the evidence, and the remaining limitations.
Stop once the requested outcome and its relevant verification are satisfied.
