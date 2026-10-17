- **Engineering:** Preserved the endpoint and contract; added checks before mutation in the required order.
- **Coding:** Changed only `OrderService.cs` and `VisibleTests.cs`. Tenant mismatch returns 404; revision mismatch returns 409.
- **Test:** Regression reproduced the cross-tenant defect before the fix. `dotnet run --project Fixture.csproj` now passes, covering rejection precedence, unchanged rejected state, valid updates, and stale edits.
- **Security:** Enforces tenant isolation and prevents stale overwrites within the fixture’s single-process contract. No runtime integration claimed.

A CSSM diagnostic appeared during execution but did not block verification; left untouched.