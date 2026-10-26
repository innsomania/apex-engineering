Updated `access.hpp` to require authentication, matching ownership, and matching tenant. Public signature preserved.

Added regression coverage for overlapping user IDs across tenants and unauthenticated access. Confirmed the cross-tenant test failed before the fix.

Verified: `c++ -std=c++17 test_access.cpp -o test_access && ./test_access` passed after the fix.