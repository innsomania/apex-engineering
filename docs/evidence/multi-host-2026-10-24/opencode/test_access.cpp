#include "access.hpp"
#include <cassert>
int main() {
    assert(can_read(true, 7, 10, {7, 10}));
    assert(!can_read(true, 8, 10, {7, 10}));
    assert(!can_read(false, 7, 10, {7, 10}));
    assert(!can_read(true, 7, 2, {7, 1}));
    assert(!can_read(true, 7, 10, {7, 99}));
}
