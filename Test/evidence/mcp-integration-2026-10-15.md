# Engineering MCP integration verification — 2026-10-15

- Host: macOS x86_64; Codex CLI 0.162.0; global `~/.codex/config.toml`.
- Configured names: `playwright`, `microsoft-learn`, `openai-developer-docs`, `context7`, `github-readonly`, `markitdown`.
- Live CLI calls passed: Playwright public-page navigation and TodoMVC interaction; Microsoft Learn .NET search; OpenAI Codex documentation search/fetch; Context7 React resolve/query; GitHub public README read; MarkItDown HTML data URI conversion.
- GitHub MCP 2.0.2 archive SHA-256 matched the official release checksums: `7ac4d549e0bf37ad9efee7be7913cae4ad50cea8d9d5be1afa9a6dbcee9d1f2c`.
- A temporary read-only CLI test mode denied the first browser MCP call because the host approval policy was `never`. The normal configured permission mode completed the same call. This is a CLI permission-mode observation, not evidence that a read-only MCP server is unavailable.
- On 2026-10-16, the current desktop chat discovered the newly configured Microsoft Learn and OpenAI Docs tools. A direct `microsoft_docs_search` call for the Microsoft Learn MCP server succeeded. The newly added local STDIO servers were absent from this chat's available tool list, so desktop Playwright, GitHub, Context7, and MarkItDown calls remain unverified here. A direct `cua_repl` attempt in the prior turn failed to start its Node runtime; it is separate from the verified Playwright MCP path.
- Raw read-only public-content traces: [navigation](mcp-playwright-live-2026-10-15.jsonl), [documentation and GitHub](mcp-core-live-2026-10-15.jsonl), [conversion and browser interaction](mcp-document-browser-live-2026-10-15.jsonl).
- Evidence traces were checked for common token-like prefixes; none were found. No project-specific authenticated browsing, cloud-resource operation, GitHub write, or desktop UI call was exercised.
