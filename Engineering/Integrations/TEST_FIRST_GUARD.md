# Test-first guard playbook

Apex's `verify.json` runs the project's tests when a turn ends. That catches a broken result, but
it says nothing about the order the work was done in: an implementation written first and a test
written afterwards to match it passes the same gate. This playbook covers the component selected
to enforce the order.

| Field | Value |
| --- | --- |
| Component | [tdd-guard](https://github.com/nizos/tdd-guard) (`tdd-guard` on npm) |
| Version observed | 1.7.0 |
| License | MIT |
| Decision mechanism | a model call, not parsing |
| Status on this host | installed globally and enabled, but **enforcing nothing here** (no reporter) |

## What it does

It runs before an edit and judges whether the change respects test-first order: a failing test
before the implementation that satisfies it. Test results reach it through reporters it ships for
vitest, jest and storybook.

## Verified behavior

Evidence: [test-first-guard-2026-10-16.log](../../Test/evidence/test-first-guard-2026-10-16.log).
The model endpoint was pointed at an unreachable local address, so no prompt content left the
machine and no model was billed.

| Case | Observed |
| --- | --- |
| Write an implementation file, model unreachable | `{"decision":"block","reason":"Error during validation: Connection error."}` |
| Write a test file adding exactly one test | allowed, with no model call at all |

The first case is the important one: it **fails closed**. A validation error denies the edit rather
than waving it through. Its own test suite covers that path.

## The limit that decides how it is used

The decision comes from a model (`src/validation/validator.ts`), so it is a judgment, not a
calculation. The same edit can be decided differently on two runs. This is the opposite profile
from the [execution guard](EXECUTION_GUARD.md), which parses the command and has no model call.

Consequences to accept before enabling it:

- **It can be wrong in both directions.** Expect occasional refusals of legitimate work and
  occasional approval of work that is not test-first.
- **It needs the model on every implementation edit.** Latency and, depending on configuration,
  cost. Upstream warns that a present `ANTHROPIC_API_KEY` can bill the API instead of using the
  Claude Code subscription.
- **A malformed hook payload is allowed, not denied.** Only the validation step fails closed.

## Relation to the Apex hooks

Its matchers overlap Apex's: `PreToolUse` on `Write|Edit|MultiEdit|TodoWrite`, plus
`UserPromptSubmit` and `SessionStart`. Claude Code runs every matching hook and any denial stops
the call, so they compose and neither weakens the other.

| Concern | Owner |
| --- | --- |
| Was the test written first | tdd-guard |
| Do the tests pass before the turn ends | Apex `verify.json` |
| May this file be edited at all | Apex `scope.json` |
| Does the work match what the user asked | Apex `review.json` |

**Friction to expect.** Apex's first rule is to do exactly what the user asked. When the user asks
for a change that is not test-first, tdd-guard denies the edit and Apex must stop and report the
conflict rather than inventing a test to get past the gate. Writing a test purely to satisfy the
guard is a deviation from the user's instruction and the reviewer should treat it as one.

## Installation

Installed as a user-scope Claude Code plugin, enabled for every project. Evidence:
[global-install-2026-10-16.log](../../Test/evidence/global-install-2026-10-16.log).

```bash
claude plugin marketplace add nizos/tdd-guard
claude plugin install tdd-guard@tdd-guard --scope user
```

The plugin wraps `npx tdd-guard@latest`, so each call may resolve a newly published release.

**It needs an authenticated Claude Code CLI, not just the desktop application.** It reaches the
model through the CLI's own credentials. Measured here: with the CLI signed out, every edit came
back `{"decision":"block","reason":"Error during validation: Not logged in · Please run /login"}` —
the fail-closed path, not a TDD judgement. Work stopped until `claude auth login` was run. If that
happens again:

```bash
claude auth status                        # loggedIn should be true
claude plugin disable tdd-guard@tdd-guard # or turn it off entirely
```

Sending `tdd-guard off` as a message disables it for the session without uninstalling.

**It enforces nothing in this repository.** Re-measured after signing in: editing an implementation
file with no failing test was **allowed**. Its data directory holds only `modifications.json` and
no test results, because it reads test state from a reporter and ships them for vitest, jest,
storybook and pytest, while this suite is `unittest` with no pytest configuration. Installed,
authenticated and running is therefore not the same as enforcing: making it real here means adding
pytest and tdd-guard's reporter to this project's test setup.
