# Application engineering

## User-visible behavior

Map the relevant user journey and its loading, empty, success, error, offline, and cancellation states. Preserve focus, keyboard navigation, labels, contrast, localization, and assistive technology semantics where the changed UI touches them. Match the existing design system. Validate visible changes in the actual UI when the host makes that possible; code inspection alone does not establish appearance or usability.

## Web and React

Identify state ownership and distinguish server data from local interaction state. Check rendering boundaries, effect cleanup, stale closures, request races, and error recovery. Avoid synchronizing duplicated state without a reason. Inspect authorization on the server, not merely UI visibility. Use [React guidance](../Coding/react/GUIDE.md) for implementation.

## Mobile and native applications

Account for lifecycle transitions, permission denial, offline operation, background limits, and persistence across process termination. Test navigation and deep links against authentication state. Treat device credentials, notifications, file access, and native bridges as platform-specific boundaries.

For React Native, distinguish JavaScript behavior from Android/iOS integration. For Flutter, consider widget/state lifecycle and platform channels. For SwiftUI, inspect state identity, observation, and concurrency isolation using the project's toolchain. Use the [technology map](KNOWLEDGE_MAP.md) rather than applying browser assumptions to mobile.

## Backend and native systems

For .NET, inspect async cancellation, dependency lifetimes, resource disposal, serialization contracts, and storage boundaries relevant to the change. For C++, establish object lifetimes, ownership, error paths, undefined behavior risks, and the actual compiler/build configuration. Use existing framework conventions; version-specific APIs require source verification.

## Performance engineering

Define a user- or system-visible objective, representative workload, and baseline before optimization. Measure the relevant latency distribution, throughput, memory, startup, frame time, allocation, or energy metric. Locate the bottleneck before changing architecture. Explain warm/cold conditions and measurement limits.

Inspect CPU, I/O, locks, database access, network requests, rendering, or serialization according to evidence. Preserve correctness and cancellation while optimizing. Repeat only the measurement that tests the hypothesis. A benchmark improvement on synthetic input is not proof of production improvement.

## Compatibility and quality

Check supported OS/browser/runtime versions, API consumers, file formats, accessibility behavior, and build variants affected by the patch. Design tests around observable behavior and failure recovery. Keep security and privacy checks proportional to touched boundaries; follow [Security](../Security/WORKFLOW.md) and [Test](../Test/WORKFLOW.md).
