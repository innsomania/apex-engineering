# React web

Inspect `package.json`, the lockfile, TypeScript configuration, build framework, routing, state conventions, and test scripts. Determine client versus server rendering and component boundaries from the project.

- Keep derived values derived; avoid duplicated state and effects that only synchronize one state value with another.
- Effects should synchronize with external systems and clean up subscriptions or requests. Respect dependency semantics; do not suppress lint rules to hide stale closures.
- Preserve stable component identity and meaningful list keys. Avoid premature memoization without an observed rendering cost.
- Follow the framework's server/client data boundary. Keep credentials and server-only operations out of browser bundles.
- Handle relevant loading, empty, error, and success states. Use semantic controls, labels, keyboard behavior, and focus management for the changed interaction.
- Reuse existing state and data-fetching libraries; add a dependency only for an actual requirement.

Verification: use the repository's configured runner and a targeted component or behavior test. Test user-visible outcomes instead of component internals. Use existing browser automation for changed navigation or interactions when it adds necessary coverage. Do not substitute a successful build for an interaction test.

References: [React](https://react.dev/learn), [TypeScript](https://www.typescriptlang.org/docs/). Consult the detected framework's official documentation for routing and rendering APIs.
