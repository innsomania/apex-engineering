I fixed the leak: `can_read` now allows a read only when the caller is authenticated, in the same tenant as the document, and is the document's owner. The new regression assertions fail on the old code and pass on the fix.

**What changed**
- **`access.hpp`:** `can_read` previously compared only `user_id` with `doc.owner_id`. It now also requires `tenant_id == doc.tenant_id`. The signature is unchanged.
- **`test_access.cpp`:** I kept the two existing assertions and added three:
  - Same user ID, different current tenant: denied.
  - Same user ID, document in a different tenant: denied.
  - Unauthenticated caller who would otherwise match: denied.

**What I verified**
- **Before the fix:** compiling with `c++ -std=c++17 test_access.cpp -o test_access` and running `./test_access` aborted on the new assertion `!can_read(true, 7, 20, {7, 10})` (exit 134).
- **After the fix:** the same compile and run exited 0, so all five assertions pass.

The only check I ran was this test binary. I did not read the C++ or security reference guides, since the change was a single added condition.