# MVP 0.1.0 Verification

Date: October 15, 2026.

## Resolved defects

Direct appending during installation could leave an incomplete Apex block. Direct writing during removal could truncate user instructions. Both operations now use a temporary file in the same directory, content synchronization, and atomic replacement. Failures clean up the temporary file and preserve previous contents. Existing file permissions are retained.

## Checks performed

| Check | Result |
| --- | --- |
| Installation and integrity tests | 20/20 passed |
| Partial write, synchronization, and publication failures | Previous instructions preserved |
| CLI install/remove, repeated operations, custom directory, paths with spaces | Passed |
| Existing instructions, permissions, conflicting links | Preserved |
| Local Markdown references | Passed |
| Skill format | Passed official quick_validate.py |
| Global installation | skill=linked, instructions=present, override=absent |
| Live user text and permissions | Matched pre-installation values |

The validator's PyYAML dependency was installed in a disposable virtual environment, which was removed afterward. The package runtime uses the Python standard library.

## Behavioral evaluation

`run_behavior_eval.py` created a temporary C++17 fixture with an access-control defect: overlapping user IDs across tenants could expose documents. The original code failed the independent access test.

A new Codex CLI session used the installed `apex-engineering` skill. Command records showed successful reads of Engineering/WORKFLOW, Coding/WORKFLOW, Coding/cpp/GUIDE, Security/WORKFLOW, and Test/WORKFLOW. The agent preserved the public signature, added tenant checking, and wrote and ran regression tests.

After the agent finished, a separately compiled independent test passed all 32 combinations of authentication, user, current tenant, owner, and document tenant. The agent's tests were also compiled and passed independently.

- [Machine-readable result](evidence/cpp-authorization/result.json)
- [Agent result message](evidence/cpp-authorization/agent-result.md)
- [Fixed C++ code](evidence/cpp-authorization/access.hpp)
- [Agent regression tests](evidence/cpp-authorization/test_access.cpp)
- [CLI event log](evidence/cpp-authorization/codex-events.jsonl)

## Verification limits

These results verify installation and one C++ development task. They do not measure comprehensive expertise across all technologies, remote service integration, or deployment. Global instructions were installed for the desktop app, and the updated AGENTS.md context in this chat included Apex routing. Actual code generation was exercised through the CLI. Installation supports one process at a time; concurrent editing of global instructions is unsupported.

This evaluation did not test mandatory model containment, tool-policy enforcement, prompt-injection resistance, or hard stop guarantees. Those are requirements for the proposed Engineering brain phase, not proven properties of MVP 0.1.0.
