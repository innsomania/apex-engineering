# Needs and stack

Read this in the Idea stage of a new project, a new feature area, or a request
that needs a technology the project does not already use. It decides what the
user needs and which technology meets it. Skip it for small work and for changes
inside an existing stack.

## Clear request first

Before the brief, make sure the request is one clear goal.

1. Restate it in one sentence: what the user wants and why. If you cannot,
   the request is not clear yet.
2. If parts are ambiguous, ask about them together, once: at most five numbered
   questions, each with two or three concrete options and your recommended one.
   Do not start the plan until they are answered.
3. If the request bundles several goals, or is too large to finish and verify in
   one plan, do not accept it as one job. Split it into smaller requests, each
   with one goal and its own "done when", put them in a sensible order, and ask
   the user which to start with. Plan only that one.

## Needs brief

Make it thorough: a gap found here costs far less than one found in code.
Write it from the request and the project evidence:

- **Who and why:** who uses it and the problem it solves.
- **Must have:** the behaviors without which it is not done.
- **Nice to have:** what can wait; leave it out of the first plan.
- **Constraints:** platform, hosting, budget, deadline, existing systems, data
  and privacy rules.
- **Main scenarios:** the steps a user takes, from start to finish, for each
  must-have.
- **Edge cases and errors:** empty, invalid, too large, offline, concurrent,
  and permission cases that apply, and what should happen in each.
- **Out of scope:** what this job will not do.
- **Risks:** what could make it fail or cost more, and how the plan handles it.
- **Done when:** the observable checks that end the work, one per must-have.

Fill gaps with a stated assumption instead of a question. Ask only when the
answer changes the stack or the must-haves, and ask those questions together,
once.

## Stack choice

1. Start from what the project and the user already use. Add a technology only
   for a must-have the current stack cannot meet.
2. For a new choice, compare at most three options against the needs brief: fit,
   maintenance activity, license, platform support, and what the user can run
   and keep up.
3. Check each option's current stable version and any breaking change in its
   official documentation or release notes. Record the version, the source URL
   and the date checked. Never take a version from model memory.
4. Recommend one option and give the reason in one line. Name what would change
   the choice.

## Current technology only

- New work uses the current stable release of every technology it adds: not a
  beta or release candidate, and not an older major version from memory.
- Never introduce a deprecated library, API, or pattern, or one past its end of
  support. When the official documentation names a replacement, use it.
- In an existing project, keep the project's versions while working, so the
  change stays compatible. When a version it relies on is deprecated, past end
  of support, or a major version behind, say so in one line with the current
  version and its source, and offer the upgrade as a separate task. Do not
  upgrade unasked.

## Output

Show the brief and the stack choice with the plan, for one approval. Keep both
at the top of `PLAN.md`, so later sessions build on the same decision:

```markdown
## Needs
- Who and why: ...
- Must have: ...
- Done when: ...

## Stack
- <technology> <version> (checked <date>, <source URL>): <reason>
```
