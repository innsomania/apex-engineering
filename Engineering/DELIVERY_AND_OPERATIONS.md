# Delivery and operations

## Reproducible builds and dependencies

Use declared build commands, lockfiles, SDK/toolchain versions, and existing CI definitions. Record what ran and with which relevant environment. Do not upgrade dependencies or rewrite pipelines as a side effect. When changing a dependency, inspect the specific API, license, compatibility, and relevant advisories for the chosen version.

Keep build artifacts, generated files, test fixtures, and secrets distinct. A clean build must not depend on an undocumented workstation state. For packaging changes, check the artifact consumed by users, not merely source tests.

## Delivery design

For an authorized release change, identify artifact identity, configuration injection, environment differences, secrets, compatibility, and rollback limits. Determine whether staged rollout, feature flags, or migration sequencing is warranted. Avoid claiming rollback is safe when persistent data or external effects cannot be reversed.

Respect the user's Git and publishing restrictions. Local completion does not imply authorization to commit, push, merge, deploy, or publish. Existing CI commands may publish or mutate infrastructure; inspect them before running.

## Observability and reliability

Choose logs, metrics, and traces that answer a real operational question. Define correlation and useful error context without logging credentials or sensitive payloads. Bound metric cardinality and log volume. Link alerts to user impact, ownership, and an actionable response.

For reliability tasks, define service indicators and objectives, dependencies, capacity assumptions, and recovery goals. Verify backups by restoration evidence when that is in scope. Process uptime alone does not establish a healthy application.

## Incidents and debugging

Establish impact, timeline, recent changes, reproduction evidence, and the hypothesis under investigation. Separate mitigation from root-cause correction. Prefer reversible mitigations within authorization. Preserve evidence and avoid destructive cleanup. Stop when required infrastructure is unavailable under the user's environment policy.

A post-incident record should describe causes, contributing conditions, and concrete prevention or detection work. Do not assign blame or turn a scoped fix into an unsolicited operational redesign.

## Maintenance and handover

Update directly affected setup instructions, contracts, and examples. Record important limitations and ownership. For deprecation or technical debt, identify the consequence and trigger for future action instead of adding unrelated cleanup to the current task.

Use the [Docker playbook](Integrations/DOCKER_AND_OBSIDIAN.md) when containers serve the requested outcome. The presence of Docker does not justify creating new infrastructure.
