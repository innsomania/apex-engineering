# Delivery and operations

Read this when a change touches a build, a dependency, a release, an alert, or
an incident. It decides one thing above all: that finishing the work locally
does not authorize shipping it.

## Builds and dependencies

- Use the declared build commands, lockfiles, toolchain versions, and existing
  CI definitions. Record what ran and in which environment.
- Do not upgrade a dependency or rewrite a pipeline as a side effect of
  something else. When changing one deliberately, inspect that version's API,
  license, compatibility, and advisories.
- A clean build must not depend on undocumented workstation state. Keep
  artifacts, generated files, fixtures, and secrets distinct.
- For a packaging change, check the artifact users consume, not only that
  source tests pass.

## Release

- Local completion does not imply authorization to commit, push, merge, deploy,
  or publish. Respect the user's Git and publishing restrictions.
- Existing CI commands may publish or mutate infrastructure. Inspect one before
  running it.
- For an authorized release change, identify artifact identity, configuration
  injection, environment differences, secrets, compatibility, and rollback
  limits.
- Do not call a rollback safe when persistent data or external effects cannot
  be reversed.

## Observability

- Choose logs, metrics, and traces that answer a real operational question.
  Bound metric cardinality and log volume.
- Provide correlation and error context without logging credentials or
  sensitive payloads.
- Link an alert to user impact, ownership, and an actionable response.
- Process uptime does not establish a healthy application. Verify a backup by
  restoration evidence when that is in scope.

## Incidents

- Establish impact, timeline, recent changes, reproduction evidence, and the
  hypothesis under investigation.
- Separate mitigation from root-cause correction, and prefer a reversible
  mitigation within authorization.
- Preserve evidence; avoid destructive cleanup. Stop and report when required
  infrastructure is unavailable under the user's environment policy.
- A post-incident record describes causes, contributing conditions, and
  concrete prevention. It does not assign blame, and a scoped fix does not
  become an operational redesign.

## Maintenance

Update the setup instructions, contracts, and examples the change directly
affects, and record important limitations and ownership. For deprecation or
technical debt, name the consequence and the trigger for future action instead
of adding unrelated cleanup to the current task. Introduce a container only
when it serves the requested outcome; Docker being installed does not justify
new infrastructure.
