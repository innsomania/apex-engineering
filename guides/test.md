# Test and verification

Derive verification from the Engineering acceptance condition. Check behavior at the narrowest boundary that can detect the relevant failure. A unit test can prove a pure rule; it cannot prove a database transaction, native permission flow, or service integration actually works.

## Select coverage

- Logic change: focused unit tests for expected behavior and relevant boundary/failure cases.
- Bug fix: regression test using the original trigger when practical; establish failure before the fix when the environment allows it.
- Contract change: relevant caller/provider or integration coverage, using the existing test facilities.
- UI change: user-visible interaction coverage plus visual inspection when layout is part of the requirement.
- Configuration or prose: inspect the changed values and direct effect; do not invent a broad test suite.

Use existing fixtures and test tools. Add deterministic assertions on outputs and side effects rather than implementation details. Avoid arbitrary sleeps, real external services in unit tests, blanket mocks that hide the defect, and snapshot updates that merely accept a regression. Use controlled clocks or existing synchronization tools for asynchronous behavior.

## Execute and interpret

Run the affected test or test project first, using the stack guide's selection and the repository's real command. Broaden only when a concrete uncovered risk or required project gate warrants it. Capture the command, result, and relevant failure evidence.

Classify failures before changing anything: product defect, test defect, or environment blocker. For a missing database, SDK, credential, port, or external service, stop and report the prerequisite under the user's environment rules. Never report a skipped test as passing. Do not weaken assertions or alter unrelated code merely to obtain green output.

After the requested behavior and relevant verification pass, stop. Report what was verified and any specific limitation. For Apex itself, installation tests validate packaging and preservation; they do not prove engineering expertise or model behavior. Behavioral evaluation requires observing a real task, its decisions, and its resulting artifacts.
