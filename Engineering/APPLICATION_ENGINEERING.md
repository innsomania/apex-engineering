# Application engineering

Read this when a change is visible to a user or specific to a platform. It
decides what counts as evidence that the change actually works, which is rarely
what the code shows.

## User-visible behavior

- Cover the loading, empty, success, error, offline, and cancellation states of
  the journey the change touches.
- Preserve focus, keyboard navigation, labels, contrast, localization, and
  assistive-technology semantics where the changed UI touches them.
- Match the existing design system rather than introducing a second one.
- Validate a visible change in the actual UI when the host allows it. Code
  inspection and passing tests do not establish appearance or usability. Before
  claiming a visual match, compare the reference with the rendered result in
  the relevant viewport and state.

## Web and React

- Distinguish server data from local interaction state, and do not synchronize
  duplicated state without a reason.
- Check rendering boundaries, effect cleanup, stale closures, request races,
  and error recovery.
- Inspect authorization on the server. UI visibility is not access control.
- Use [React guidance](../Coding/react/GUIDE.md) for implementation.

## Mobile and native

- Account for lifecycle transitions, permission denial, offline operation,
  background limits, and persistence across process termination.
- Test navigation and deep links against authentication state.
- Treat device credentials, notifications, file access, and native bridges as
  platform-specific boundaries.
- Do not apply browser assumptions to mobile. React Native separates
  JavaScript behavior from Android and iOS integration; Flutter, widget and
  state lifecycle from platform channels; SwiftUI, state identity, observation,
  and concurrency isolation.

## Backend and native systems

- For .NET, inspect async cancellation, dependency lifetimes, resource
  disposal, serialization contracts, and the storage boundary the change
  touches.
- For C++, establish object lifetimes, ownership, error paths, undefined
  behavior risks, and the actual compiler and build configuration.
- Follow existing framework conventions. A version-specific API needs source
  verification, not recall.

## Performance

- Define a user- or system-visible objective, a representative workload, and a
  baseline before optimizing.
- Locate the bottleneck before changing architecture, and repeat only the
  measurement that tests the hypothesis.
- Preserve correctness and cancellation while optimizing.
- A benchmark improvement on synthetic input is not proof of a production
  improvement. State warm and cold conditions and measurement limits.

## Compatibility

Check the supported OS, browser, and runtime versions, API consumers, file
formats, and build variants the patch affects. Keep security and privacy checks
proportional to the boundaries touched; follow
[Security](../Security/WORKFLOW.md) and [Test](../Test/WORKFLOW.md).
