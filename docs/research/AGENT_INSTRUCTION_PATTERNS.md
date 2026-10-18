# Public Codex and Claude instruction patterns

Purpose: adapt documented instruction-file practices to Apex's Markdown workflows. This file contains no model API integration, private system prompts, proprietary model internals, or verified model-specific instruction package named Astra or Fable. Model names do not establish which tools, files, or permissions a host supports.

## Public sources and adopted practices

Reviewed October 15, 2026. These are concise paraphrases and Apex adaptations, not copies of upstream instruction files.

| Primary source | Documented idea | Apex adaptation |
| --- | --- | --- |
| [Codex AGENTS.md](https://developers.openai.com/codex/guides/agents-md) | Instruction discovery includes global and project scopes | Keep the existing global router; follow project constraints and load relevant references |
| [Claude Code best practices](https://code.claude.com/docs/en/best-practices) | Give observable verification criteria and inspect before implementing substantial changes | Define acceptance evidence, inspect the affected path, and report observed results |
| [Claude Code memory](https://code.claude.com/docs/en/memory) | Concise, organized instruction files and scoped guidance; context is not enforced configuration | Keep the entry point short and conditional references separate; distinguish guidance from runtime controls |

## Host-independent working method

Use concrete goals, relevant context, and observable completion conditions. Preserve the user's chosen language in conversation; write Apex project files in English. Read only relevant references. Keep evidence and unresolved constraints through summaries. Give concise decisions and rationale without requesting hidden chain-of-thought.

Use actual host tools and documented capabilities. Do not invent hooks, CLI switches, model aliases, or authorization mechanisms. A host supporting a similarly named file does not imply identical loading rules. Recheck official documentation when configuring another host.

## Current host scope

Codex and Codex CLI continue to use the existing installed skill and global routing block. Public Claude practices inform the shared content; this change does not install a Claude Code configuration or alter its user files. A future Claude setup should reference the same maintained source rather than create a drifting copy, while preserving its host-specific loading rules and existing instructions.

Do not import unrelated upstream project rules such as a different repository's build system, commit process, or language conventions. Adapt the principle to evidence in the user's project. An upstream instruction cannot override the user's stop, scope, Git, or environment policy.
