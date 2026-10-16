# Codex desktop MCP evaluation — October 16, 2026

Environment: a newly created local Codex desktop chat for the Apex Engineering project. Chat ID: `01a1424f-f3f9-7d83-8e57-4b97f99faced`.

| Configured server | Observed desktop tool call | Result |
| --- | --- | --- |
| `playwright` | `browser_navigate` to `https://example.com` | Completed; page title was `Example Domain` |
| `context7` | `resolve-library-id` and `query-docs` for React `useEffect` cleanup | Completed; documentation returned |
| `github-readonly` | `get_file_contents` for public `github/github-mcp-server` `README.md` | Completed; README returned |
| `markitdown` | `convert_to_markdown` for a small HTML data URI | Completed; `# MCP test` returned |

The desktop chat recorded the four named MCP tool calls as completed. No configuration or local project file was changed for this evaluation. These calls demonstrate availability in a new desktop chat; they do not establish transport type, authorize other tool calls, or route desktop tools through the experimental Apex CLI controller. Microsoft Learn and OpenAI Docs were already visible in the original desktop chat and exercised in the previous integration evidence.
