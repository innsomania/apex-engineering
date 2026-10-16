# MCP Capability Registry and Audit

This file documents the bounded diagnostic route for six global Codex MCP server names. The doctor reads the user-level Codex configuration (or `CODEX_HOME/config.toml`) but emits only allowlisted names and safe status codes.

| Capability | MCP server | Expected discovery tools |
| --- | --- | --- |
| Browser testing | `playwright` | `browser_navigate`, `browser_snapshot` |
| Microsoft documentation | `microsoft-learn` | `microsoft_docs_search` |
| OpenAI documentation | `openai-developer-docs` | `search_openai_docs`, `fetch_openai_doc` |
| Library documentation | `context7` | `resolve-library-id`, `query-docs` |
| Repository context | `github-readonly` | `get_file_contents` |
| Document conversion | `markitdown` | `convert_to_markdown` |

## Probe

Run:

```sh
uvx --python 3.13 --with mcp==2.3.0 python Engineering/mcp_doctor.py probe
```

The doctor uses the official MCP Python SDK to connect to configured allowlisted servers and list tools. It never invokes a listed tool. It reports `available`, `degraded` (expected tools missing), `disabled`, `unconfigured`, or `unavailable`; output contains no raw configuration, credentials, transport errors, schemas, or server-provided tool names outside the registry. Use `--server NAME` to probe a subset and `--timeout SECONDS` to set a bounded per-server timeout.

Capability routes are available with `python3 Engineering/mcp_doctor.py routes`. The registry is diagnostic and does not enforce which tools Codex or another host can use. It is not a gateway or a host security boundary.

## Audit

Run:

```sh
python3 Engineering/mcp_doctor.py audit \
  --task-id APX-<32-lowercase-hex> \
  --input path/to/codex-exec-events.jsonl
```

The audit command parses Codex CLI JSONL MCP call events and emits the task ID, registered server, tool, status, and SHA-256 digest of each result value. It does not persist or emit arguments, result content, errors, credentials, or raw malformed lines. It counts failed events, malformed lines, and calls from unregistered servers; input is bounded by line length and line count. Omit `--input` or pass `-` to read JSONL from standard input.

The digest identifies result content without storing it. Treat the audit output as task-linked metadata, not as proof of host-wide enforcement or as a substitute for reviewing the original task context.
