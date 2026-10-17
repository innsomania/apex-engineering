Updated `access.hpp` to require authentication, matching owner ID, and matching current tenant ID. Public signature preserved.

Added focused regression coverage for overlapping user IDs across tenants and unauthenticated access. Confirmed the cross-tenant test failed before the fix.

Verified: `c++ -std=c++17 test_access.cpp -o test_access && ./test_access` passed all assertions.