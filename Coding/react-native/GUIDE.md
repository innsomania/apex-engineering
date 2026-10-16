# React Native

Inspect React Native and React versions, Expo versus bare workflow, supported platforms, navigation, native modules, and existing test commands. Consult the React reference for shared component/state concerns without importing browser DOM assumptions.

- Use native primitives and platform accessibility properties. Account for keyboard, safe areas, dynamic text, and screen size in the changed screen.
- Treat app lifecycle, permissions, and connectivity as relevant states. Clean up listeners and background work.
- Keep credentials in the project's supported secure storage mechanism. Do not treat ordinary local storage as a secret store.
- For long lists or animations, inspect actual rendering and thread costs before optimizing. Preserve stable item identities.
- Verify native-module compatibility with the installed React Native/Expo version and architecture before changing dependencies. Follow existing navigation types and deep-link contracts.

Verification: run the relevant JavaScript/component test first. A JS test cannot prove a native API, permission prompt, or device interaction; use the existing simulator/device workflow for those changes if available. State exactly which platforms were exercised. Missing SDKs or simulators are blockers, not permission to install them.

References: [React Native](https://reactnative.dev/docs/getting-started), [Expo](https://docs.expo.dev/).
