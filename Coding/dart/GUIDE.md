# Dart and Flutter

Inspect `pubspec.yaml`, SDK constraints, lockfile, analysis options, and test layout. Detect whether the package is pure Dart or depends on Flutter; Dart work does not automatically require a Flutter UI.

- Preserve sound null safety and explicit ownership of subscriptions, streams, and controllers.
- Model expected failures using the project's error/result conventions. Await futures whose failures affect task completion and propagate cancellation where the existing API supports it.
- In Flutter, keep build methods free of side effects. Respect widget lifecycle; avoid updating disposed state after asynchronous work.
- Follow existing state management and navigation. Use keys when preserving identity matters, and account for accessibility, layout constraints, and localization in changed widgets.
- Use isolates only for demonstrated CPU work that would otherwise block the UI; do not introduce them for ordinary asynchronous I/O.

Verification: use `dart test path/to/test.dart` for Dart or `flutter test path/to/test.dart` for Flutter, adjusted to project scripts. Choose unit, widget, or existing integration coverage according to the changed boundary. Scope analysis to affected files where supported. Do not generate platform projects or install SDKs to bypass an environment blocker.

References: [Dart](https://dart.dev/guides), [Flutter](https://docs.flutter.dev/).
