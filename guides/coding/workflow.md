# Coding workflow

Read the project's build manifests, dependency versions, relevant local rules, and representative neighboring code. Follow its language version, formatter, naming, and error-handling conventions. Use the detected version's APIs; do not upgrade dependencies as a side effect of implementing a feature.

Translate the Engineering acceptance condition into the smallest complete change. Keep business rules testable, make ownership and effects explicit, and handle relevant failure paths. Avoid catching errors merely to suppress them or weakening validation to satisfy a test. Comments should explain non-obvious constraints or decisions.

When a change crosses boundaries, trace the actual flow: caller, input validation, domain logic, storage or remote call, and result presentation. Update the affected contract consistently. Do not create missing infrastructure or schema changes unless requested.

For a defect, reproduce it or record the strongest available evidence before fixing it. Coordinate a regression test with Test when meaningful. Reversible text or configuration edits do not automatically require a new test suite.

Use tools to apply and inspect actual changes. A proposed snippet is not an implemented change. Before handing off, inspect the affected diff for accidental edits, debug output, leaked values, incompatible API changes, and incomplete behavior. Run only the verification selected for this task.
