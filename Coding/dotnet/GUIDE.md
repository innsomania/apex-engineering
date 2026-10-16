# C# and .NET

Inspect `global.json`, project target frameworks, nullable settings, package versions, solution structure, and the existing test framework. Detect ASP.NET Core, desktop, library, or worker workloads before choosing conventions.

- Preserve dependency injection lifetimes; avoid retaining scoped services in singletons. Follow existing configuration and options validation.
- Keep asynchronous flows asynchronous. Propagate cancellation across I/O and avoid blocking waits on tasks. Make disposable resource ownership explicit.
- For HTTP endpoints, follow existing validation, authorization, status codes, and error contracts. Do not expose internal exceptions to clients.
- For EF Core, check query translation, tracking needs, result size, and existing transaction boundaries. Avoid unintended materialization or extra round trips. Schema migrations require the user's authorization.
- Treat nullable annotations as a contract; do not silence warnings with `!` without proving the invariant. Keep domain invariants out of transport-only validation.

Verification: select the affected test project and an existing test filter, such as `dotnet test path/to/tests.csproj --filter FullyQualifiedName~AffectedTests`. Use the project's configured SDK and test runner; adapt the command to its actual capabilities. Build the affected project only when compile coverage is otherwise missing. If SDK, restore access, or database prerequisites are unavailable, report the blocker.

Version-sensitive references: [C#](https://learn.microsoft.com/dotnet/csharp/), [.NET](https://learn.microsoft.com/dotnet/), [ASP.NET Core](https://learn.microsoft.com/aspnet/core/), [EF Core](https://learn.microsoft.com/ef/core/).
