#include "access.hpp"
#include <cassert>
int main() {
    assert(can_read(true, 7, 10, {7, 10}));
    assert(!can_read(true, 8, 10, {7, 10}));
    // Same user ID in a different tenant must not grant access.
    assert(!can_read(true, 7, 20, {7, 10}));
    assert(!can_read(true, 7, 10, {7, 20}));
    // Unauthenticated callers are always denied.
    assert(!can_read(false, 7, 10, {7, 10}));
}
