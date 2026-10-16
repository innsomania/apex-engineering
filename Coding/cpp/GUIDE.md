# C++

Inspect the build system, compiler, C++ standard, supported platforms, dependency management, and existing test targets. Preserve ABI requirements and local exception/RTTI policies.

- Express ownership with RAII and the project's owning types. Keep non-owning pointers, references, spans, and views within the lifetime of their storage.
- Examine bounds, integer conversion, iterator invalidation, and moved-from state where the change touches them. Do not rely on undefined behavior.
- Define synchronization and object lifetime for shared state. Check lock ordering and avoid callbacks under locks when they could re-enter.
- Preserve exception guarantees and resource cleanup. Use move semantics based on ownership needs; avoid unmeasured low-level optimizations.
- For public headers or binary boundaries, check layout, symbol visibility, and downstream compile implications relevant to the change.

Verification: build the affected target using the existing preset/build directory and run its specific test selection, for example an anchored `ctest -R` filter when the project uses CTest. Use an existing sanitizer configuration for a memory/lifetime defect where available. A compiler warning suppression is not evidence that the defect is fixed. Do not reconfigure the toolchain or install native dependencies to bypass a blocker.

References: [ISO C++ resources](https://isocpp.org/), [C++ Core Guidelines](https://isocpp.github.io/CppCoreGuidelines/CppCoreGuidelines), [CMake](https://cmake.org/documentation/). Check the actual compiler's documentation for compiler-specific behavior.
