# Needs and stack

Read this in the Idea stage of a new project, a new feature area, or a request
that needs a technology the project does not already use. It decides what the
user needs and which technology meets it. Skip it for small work and for changes
inside an existing stack.

## Needs brief

Write it in at most eight lines, from the request and the project evidence:

- **Who and why:** who uses it and the problem it solves.
- **Must have:** the behaviors without which it is not done.
- **Nice to have:** what can wait; leave it out of the first plan.
- **Constraints:** platform, hosting, budget, deadline, existing systems, data
  and privacy rules.
- **Done when:** the observable checks that end the work.

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
