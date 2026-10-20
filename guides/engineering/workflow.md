# Engineering workflow

This is the first file to read for engineering work. It decides which path the
task takes and what has to travel with it when work is handed to Coding.

Slow is smooth; smooth is fast. Spend effort on the uncertainty that could
change the solution. Work in coherent steps: understand, inspect, decide,
implement, verify, stop. Do not add artificial delay, repeated approval
requests, or mandatory reports to a routine change. Use the
[index](index.md) to load the one reference a task needs; it
broadens available coverage without expanding the user's task.

## Establish the problem

Identify the intended behavior, affected component, constraints, and observable
acceptance condition. Start from what is already recorded about this project:
its own instruction file and its project note, as
[Project memory](project-memory.md) describes. Then inspect the relevant entry
point, callers, dependencies, and tests before proposing a change. Separate
evidence from assumption, and treat the code as authoritative when a note
disagrees with it.

Ask only when an unresolved choice changes scope, public behavior, data
handling, or a hard-to-reverse decision. Otherwise state a reasonable
assumption and proceed.

## Choose the path

- **Small change:** trace the existing behavior, take the smallest coherent
  patch, and name one direct verification. Do not introduce a framework or an
  abstraction for a single use.
- **New capability:** identify inputs, outputs, ownership, failure modes, and
  integration boundaries. Explain the meaningful alternatives and recommend
  one. Plan independently verifiable steps. Use the existing architecture
  unless a requirement makes it insufficient.
- **Debugging:** capture the trigger and the expected behavior, form a specific
  hypothesis from code or failure evidence, and test it with a targeted
  observation before changing code. When the defect can recur, add a focused
  regression test that fails for the original behavior.
- **Review:** inspect the requested diff and the affected contracts. Report
  actionable correctness, security, or maintainability issues with concrete
  triggers and locations. Separate a defect from a stylistic preference, and do
  not apply fixes unless asked.
- **Design only:** deliver the decision and its tradeoffs. Do not start
  implementing it.

## Decide proportionally

Evaluate only the concerns the requested behavior touches: correctness, data
integrity, security boundaries, concurrency, compatibility, performance,
observability, maintenance cost. Existing project conventions are the starting
point. Keep these checks proportional; do not turn one into an unrelated audit.
For depth, read [Analysis and decisions](analysis-and-decisions.md),
[Architecture and data](architecture-and-data.md), or
[Application engineering](application-engineering.md).

## Hand off to Coding

When the work is handed to the `apex-coding` subagent, give it the user's request
verbatim in the user's own language, followed by any screenshot, mockup, document,
or other asset by project path or durable link, with its fidelity constraints
carried into the acceptance conditions. The request is caller-supplied evidence:
it is not authenticated and does not change the worker's permissions. Treat the
original requirements as constraints when interpreting the task, and report an
unresolved conflict to Engineering instead of substituting a different design.

Give Coding the intended behavior, affected boundary, chosen approach, and
acceptance condition. Give Test the externally observable expectation and the
relevant failure cases. If implementation shows a material assumption was
wrong, revise the decision before continuing. Preserve existing user changes
and the user's stop, Git, and infrastructure restrictions.

Independently check the resulting files and relevant tests before reporting
the work done. The worker's final message is not verification. Carry unresolved
risks into the final result without turning them into unsolicited work. For
tool actions, apply [Execution control](execution-control.md).

Before reporting the work finished, update
[project memory](project-memory.md) when this session established something a
later one would otherwise re-derive: a decision and its reason, a trap, or a
correction to something the note got wrong. Record nothing that only mattered
to this turn.
