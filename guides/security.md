# Security engineering

For an explicit security review, assess the requested component. During ordinary development, assess the security boundaries touched by the change. Do not expand a local fix into a repository-wide audit.

## Model the relevant boundary

Identify assets, actors, untrusted inputs, privileged operations, and the trust boundary crossed by the feature. Trace attacker-controlled values from entry point to sensitive operation. Separate a demonstrated vulnerability from a hypothesis and state what evidence would resolve the hypothesis.

## Apply the relevant checks

- **Identity and access:** distinguish authentication from authorization. Verify access to each protected operation and object on the trusted side, including tenant ownership. Client-side visibility is not an authorization check. Follow the existing session and token validation mechanisms.
- **Input and execution:** use structured or parameterized interfaces for database queries and process execution. Validate paths against the intended root, including traversal and symlink behavior when relevant. Apply output encoding for the destination context. For URL fetching, examine scheme, redirect, and destination restrictions where server-side requests are exposed.
- **Secrets and data:** use the project's secret storage, redact logs, limit returned fields, and preserve data retention/access rules. Never put credentials into source or generated examples. Prefer established cryptographic libraries and protocols; do not design custom cryptography.
- **Browser and API boundaries:** evaluate relevant injection, CSRF, CORS, cookie, upload, and rate-control behavior according to the actual deployment and authentication model. CORS is not authorization.
- **Mobile and native code:** inspect permission scope, secure storage, exposed deep links or IPC, and relevant memory/lifetime risks. Device storage and client code are not trusted authorization boundaries.
- **Dependencies:** assess affected dependencies and versions when a task changes them or requests an audit. Use existing scanners where appropriate; corroborate a report against the deployed version and reachable code. Do not perform unrelated upgrades.

## Verify and report

Give Test a concrete abuse case and the expected denial or safe behavior: for example, user B cannot read user A's record, a traversal path cannot escape the allowed directory, or unauthenticated requests cannot trigger a protected action. Include a legitimate case to detect accidental denial of valid behavior.

Use local fixtures or authorized test systems. Do not probe external systems without authorization. Report each finding with affected location, trigger, impact, evidence, and a minimal remediation. A clean review or scanner result is not a security guarantee. If a dependency advisory or protocol behavior is uncertain, verify it against current authoritative sources before making a claim.

References for task-specific lookup: [OWASP ASVS](https://owasp.org/www-project-application-security-verification-standard/), [OWASP Cheat Sheet Series](https://cheatsheetseries.owasp.org/), [CWE](https://cwe.mitre.org/). Use the framework's official security documentation for implementation details.
