# Browser and research integration playbook

Read this when the task needs a live page or web evidence. It decides which
browser or research tool fits, and what its output may be treated as.

## Browser selection

- [Playwright MCP](https://github.com/microsoft/playwright-mcp): use for stateful inspection through an available controlled MCP route.
- [Playwright CLI](https://github.com/microsoft/playwright-cli): consider when a verified shell route is suitable for bounded browser tasks.
- [Playwright engine](https://github.com/microsoft/playwright): use as the underlying automation library when implementing an adapter, not as another reasoning layer.
- [Browser Use](https://github.com/browser-use/browser-use): consider only when a separate browser agent's autonomy is needed and can be constrained.

Before browsing, identify the relevant destination, profile/session, read versus mutation permissions, and evidence to capture. Inspect actual UI state before interacting. Verify the resulting page/state before reporting success. Keep user account state separate from disposable automation profiles.

On this host, the global `playwright` MCP server uses pinned `@playwright/mcp@0.0.83` with `--headless --isolated`. A Codex CLI session navigated to `https://example.com` and observed the title, then used a separate public TodoMVC page to add a todo and read its visible text. See the [capability catalog](MCP_CATALOG.md) and [live evidence](../../docs/evaluations/evidence/mcp-document-browser-live-2026-10-15.jsonl). Confirm the tool is present in each new session; the existing desktop `cua_repl` route was not verified by these CLI checks.

Playwright MCP does not provide a security boundary; its origin controls are insufficient as a general network restriction. Check the [research caveats](../../docs/research/GITHUB_RESEARCH_2026-10-15.md) and enforce required network restrictions outside the browser tool.

## Research selection

| Candidate | Intended role | Decision condition |
| --- | --- | --- |
| [Crawl4AI](https://github.com/unclecode/crawl4ai) | Local web extraction | Primary extraction candidate; resolve pinned-release license/attribution details |
| [Firecrawl](https://github.com/firecrawl/firecrawl) | Service-based extraction | Alternative; review AGPL/deployment and hosted service terms |
| [SearXNG](https://github.com/searxng/searxng) | Self-hosted metasearch | Choose when independence justifies maintaining it |
| [Tavily MCP](https://github.com/tavily-ai/tavily-mcp) | Hosted search/extraction connector | Requires separately authorized service access and data handling |
| [GPT Researcher](https://github.com/assafelovic/gpt-researcher) | Autonomous research worker | Optional bounded workflow; no automatic model API setup |

Prefer an existing suitable search tool before adding a backend. Define the research question and page/time/output budget. Preserve source URLs, version context, retrieval time, and conflicting evidence. Deduplicate repeated sources; do not confuse multiple copies with independent corroboration.

## Verification for a future connection

Use a known public page to verify extraction and citations. Use a controlled fixture for redirects, unavailable pages, malformed content, embedded instructions, and forbidden destinations. Confirm that extraction failures are reported rather than replaced by guessed content. Check the user's scope before following links or submitting forms. Stop once the question is answered with sufficient evidence.
