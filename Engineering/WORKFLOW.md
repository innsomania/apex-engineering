# Engineering workflow

This is the first file to read for engineering work. It decides which path the
task takes and what has to travel with it when work is handed to Coding.

Slow is smooth; smooth is fast. Spend effort on the uncertainty that could
change the solution. Work in coherent steps: understand, inspect, decide,
implement, verify, stop. Do not add artificial delay, repeated approval
requests, or mandatory reports to a routine change. Use the
[knowledge map](KNOWLEDGE_MAP.md) to load the one reference a task needs; it
broadens available coverage without expanding the user's task.

## Establish the problem

Identify the intended behavior, affected component, constraints, and observable
acceptance condition. Inspect the project's instructions and the relevant entry
point, callers, dependencies, and tests before proposing a change. Separate
evidence from assumption.

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
For depth, read [Analysis and decisions](ANALYSIS_AND_DECISIONS.md),
[Architecture and data](ARCHITECTURE_AND_DATA.md), or
[Application engineering](APPLICATION_ENGINEERING.md).

## Hand off to Coding

When work needs persistent ownership or continuation, record bounded tasks in
the [task system](TASK_SYSTEM.md): assign the role, establish dependencies
before starting, and keep acceptance evidence with each task.

Capture the user's request verbatim in the bridge request file, preserving its
original language and wording. After the verbatim text, reference any
screenshot, mockup, document, or other asset by project path or durable link,
and carry its fidelity constraints into the acceptance conditions.

The request file is caller-supplied evidence. It is not authenticated, it
creates no sandbox, and it does not change the worker's permissions. Treat the
original requirements as constraints when interpreting the task contract, and
report an unresolved conflict to Engineering instead of substituting a
different design.

Use the bridge's `instruct` command for a corrective follow-up queued behind
the active turn, and `stop` to interrupt it. They differ: `stop` closes intake
and discards queued follow-ups. Describe which one was used accurately.

Give Coding the intended behavior, affected boundary, chosen approach, and
acceptance condition. Give Test the externally observable expectation and the
relevant failure cases. If implementation shows a material assumption was
wrong, revise the decision before continuing. Preserve existing user changes
and the user's stop, Git, and infrastructure restrictions.

Independently check the resulting files and relevant tests before recording
acceptance. The worker's final message is not verification. Carry unresolved
risks into the final result without turning them into unsolicited work. For
tool actions, apply [Execution control](EXECUTION_CONTROL.md).
