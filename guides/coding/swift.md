# Swift and SwiftUI

Inspect `Package.swift`, Xcode project/workspace, deployment targets, Swift language mode, concurrency settings, schemes, and current test framework. Follow the deployment target when choosing APIs.

- Make ownership and actor isolation explicit. Keep UI mutations on the appropriate actor and propagate task cancellation. Do not disable concurrency checks to hide unsafe sharing.
- Choose value or reference semantics according to identity and ownership. Use weak captures where a real retain cycle exists, rather than mechanically everywhere.
- For SwiftUI, preserve a single source of truth and view identity. Use the observation/state approach supported by the project's target; keep side effects out of view-body evaluation.
- Respect task and view lifetimes. Handle loading and error presentation, accessibility labels, dynamic type, and localization where the change affects them.
- For persistence or networking, use the project's isolation and error conventions; keep transport details out of view logic when an existing boundary supports that separation.

Verification: for packages, select a relevant `swift test --filter` test. For applications, use the existing Xcode scheme, available destination, and `-only-testing` selection. Verify the affected behavior on an existing simulator when it depends on UI or platform services. Report missing signing, SDK, or destination prerequisites without changing the environment.

References: [Swift](https://www.swift.org/documentation/), [SwiftUI](https://developer.apple.com/documentation/swiftui), [Swift concurrency](https://docs.swift.org/swift-book/documentation/the-swift-programming-language/concurrency/).
