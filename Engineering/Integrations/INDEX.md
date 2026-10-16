# Integration playbooks

These playbooks integrate tool knowledge and selection procedures into the Markdown skill. The [MCP capability catalog](MCP_CATALOG.md) records which selected servers were configured and verified on this host. Neither Markdown guidance nor MCP configuration establishes a mandatory runtime control boundary.

Use only the playbook needed by the current task. Check actual availability and version before use. Do not load or activate every candidate. Alternatives remain alternatives; an excluded project must not be enabled merely because it appeared in research.

| Need | Playbook | Repositories covered |
| --- | --- | --- |
| Connected MCP capabilities and task routing | [MCP capability catalog](MCP_CATALOG.md) | Playwright, Microsoft Learn, OpenAI Developer Docs, Context7, GitHub, MarkItDown; conditional providers |
| Host boundaries, policy, gateway | [Control](CONTROL.md) | Codex, sandbox-runtime, OPA, Cedar, agentgateway, ContextForge |
| Browser and web evidence | [Browser and research](BROWSER_AND_RESEARCH.md) | Playwright MCP, CLI, engine, Browser Use, Crawl4AI, Firecrawl, SearXNG, Tavily MCP, GPT Researcher |
| Document and source-code evidence | [Documents and code](DOCUMENTS_AND_CODE.md) | Docling, Docling MCP, MarkItDown, Unstructured, Serena/SolidLSP, Tree-sitter, SCIP |
| State, evaluations, supplementary filters | [State and evaluation](STATE_AND_EVALUATION.md) | Pydantic, LangGraph, promptfoo, NeMo Guardrails, Presidio, garak; LLM Guard exclusion |
| Public agent instruction methods | [Codex and Claude patterns](AGENT_INSTRUCTION_PATTERNS.md) | Official public guidance; no private model prompts |
| Containers and knowledge notes | [Docker and Obsidian](DOCKER_AND_OBSIDIAN.md) | Existing environment and user-designated vault |

The [research report](../Research/GITHUB_RESEARCH_2026-10-15.md) contains the comparative rationale, source links, license caveats, and version snapshot for all 29 repositories. Revalidate version-dependent instructions before a future installation.

## Connection contract

When a task actually requests an executable connection, establish:

- Purpose and required capability; why existing tools are insufficient.
- Host, exact dependency version, license, transport, and declared prerequisites.
- Allowed operations, paths, destinations, and data handling.
- Authentication by the existing secret mechanism, with no secrets in Markdown.
- Expected output, error/timeout behavior, cancellation, and resource ownership.
- A narrow positive test and a relevant failure/denial test.
- Observed status: documented, available, configured, verified, or blocked. Never equate these states.

Do not install every researched repository as one bundle. Use the primary candidate for a capability; select an alternative when requirements justify it. Keep a failed or missing protected capability disabled and follow the user's environment stop rule.
