The skill and relevant guides are loaded. Plan: reproduce with the current tests, then apply the minimal tenant-scoped fix in `access.hpp` and add focused regression coverage in `test_access.cpp`, then compile and run.

Baseline first:

Baseline passes (confirming the existing cases are green, so the regression coverage can stay strict).

**Plan:** (1) fix `can_read` to require tenant match, (2) add regression tests for cross-tenant overlap, tenant mismatch, and unauthenticated access, (3) compile and run.

Applying the minimal fix:

Now compile and run the focused tests:

Tests pass with the fix. To prove the regression coverage actually catches the original defect, let me temporarily restore the old logic and confirm the new tests fail, then re-apply:

Confirmed — with the old logic, the new regression test fails (`!can_read(true, 7, 2, {7, 1})` fires), reproducing the cross-tenant leak. Re-applying the fix and running final verification:

Final inspection of the two changed files:

Done. Task complete — stopping here per the stop behavior.

## What changed

- **`access.hpp`**: `can_read` now requires `tenant_id == doc.tenant_id` in addition to authentication and ownership:
  ```cpp
  return authenticated && user_id == doc.owner_id && tenant_id == doc.tenant_id;
  ```
  The public signature was kept unchanged.
- **`test_access.cpp`**: added focused regression coverage — unauthenticated access denied, and cross-tenant access denied (including the overlapping-user-ID case: user 7 in tenant 2 cannot read a doc owned by user 7 in tenant 1).

## What was verified

- Baseline: original two assertions compiled and passed against the original code.
- Regression proof: temporarily restored the old logic and ran the updated suite — it **failed** with `Assertion failed: (!can_read(true, 7, 2, {7, 1}))` (exit 134), reproducing the cross-tenant leak. Then the fix was re-applied.
- Final state: `c++ -std=c++17 test_access.cpp -o test_access && ./test_access` → **passed** (all assertions green, including legitimate own-document access).

## Notes

- Only the two permitted files (`access.hpp`, `test_access.cpp`) were edited; no other files touched.
- The fix addresses the leak by treating user IDs as tenant-scoped, so a user can only read documents in their current tenant that they own.
- Limitation: verification was at the pure-function level only — no DB/auth integration was exercised, per the bounded fixture's compile-and-run setup.