# Apex Engineering — MVP Design

> **Status: historical record.** This describes the original Codex-only MVP scope. Claude Code support, the verification, scope, and review hooks, the task ledger, and the integration playbooks all landed after it was written, so its "Initial exclusions" no longer hold. For current behavior read [SKILL.md](../SKILL.md) and [docs/INSTALL.md](INSTALL.md).

## Purpose

Apex Engineering is a software engineering agent configuration for global use in Codex and Codex CLI. It supports development tasks from understanding the request through implementation and verification. Initial technology coverage includes C#, .NET, React, React Native, Dart, Swift, SwiftUI, and C++. It provides expertise references and workflows on top of existing Codex tools.

## Structure

The repository has four main directories:

- `Engineering/`: requirements, system analysis, design decisions, implementation planning, code review, and delivery assessment.
- `Coding/`: implementation guidance with separate modules for C#/.NET, React, React Native, Dart, Swift/SwiftUI, and C++.
- `Test/`: risk-based test selection, test implementation, focused execution, and result assessment.
- `Security/`: affected trust boundaries, authentication, authorization, data protection, and abuse cases.

Root-level entry files describe identity, routing, and installation. One agent moves between these areas according to the task.

## Task flow

1. Identify the requested outcome and scope boundary.
2. Inspect relevant code, project rules, dependencies, and existing tests.
3. Select the necessary Engineering and Coding references; explain significant design decisions.
4. Implement the changes within scope. For changes affecting trust boundaries, Security identifies relevant risks and abuse cases to verify.
5. Use Test to perform the narrowest meaningful verification and distinguish product, test, and environment failures.
6. Report changes, observed verification results, and remaining blockers.

The task determines which stages are needed. A small defect does not require a heavy architecture process; a new subsystem needs design and planning. User and project constraints can narrow the workflow.

## Expertise approach

Technology modules describe relevant project evidence, when to consult current official documentation, important design considerations, and appropriate focused verification. Expertise is demonstrated through supported decisions and working results. Unverified claims must not be presented as established facts.

## Codex integration

Source files remain in this repository. `install.py` links `skills/apex-engineering` in the Codex user directory to the source directory and adds a marked routing block to the global `AGENTS.md`. The default directory is `CODEX_HOME` or `~/.codex`. Existing user text is preserved. `uninstall` removes only the owned link and routing block. Repeated installation is idempotent; conflicting installations and override files are not automatically replaced.

## Initial acceptance criteria

- Codex and Codex CLI can access the global Apex Engineering entry point.
- The four working areas have clear responsibilities without duplicated guidance.
- The listed technology areas have accessible implementation references.
- A development task demonstrates relevant module selection and focused verification.
- Installation preserves existing instructions and supports removal.

These criteria cover the original MVP. They do not establish mandatory model containment. The next phase is described in [Engineering/BRAIN_DESIGN.md](../Engineering/BRAIN_DESIGN.md).

## Initial exclusions

The first version does not include model training, a new IDE, automated deployment infrastructure, or Claude Code integration. Those require separate decisions.
