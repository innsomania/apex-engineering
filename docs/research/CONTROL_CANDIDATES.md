# Control integration playbook

## Selection

| Candidate | When to use | Required distinction |
| --- | --- | --- |
| [Codex](https://github.com/openai/codex) | Determine supported host permissions and extension points | A global skill is guidance; CLI and desktop tool boundaries require separate verification |
| [sandbox-runtime](https://github.com/anthropics/sandbox-runtime) | Constrain local tool processes where a wrapper is appropriate | Only wrapped processes are covered; protect sensitive reads as well as writes |
| [OPA](https://github.com/open-policy-agent/opa) | Evaluate normalized task/action policy | Decision output requires a trusted dispatcher that enforces it |
| [Cedar](https://github.com/cedar-policy/cedar) | Alternative principal/action/resource permission model | Select instead of duplicating the primary decision engine |
| [agentgateway](https://github.com/agentgateway/agentgateway) | Mediate MCP traffic with tool authorization | Direct tools and direct network paths need their own enforced boundary |
| [ContextForge](https://github.com/IBM/mcp-context-forge) | Registry/admin/plugin needs justify a broader gateway | Additional services require explicit operational ownership |

## Future connection procedure

Enumerate all paths to the protected effect. Locate the policy outside model-writable state. Normalize action arguments and canonical targets; evaluate before dispatch. Bind approval to the action, target, and task, rather than trusting an approval string supplied by the model. Deny on unavailable or malformed authorization results.

For a gateway, verify identity and authorization on calls as well as discovery. Check session/route isolation and the security advisory documented in the [research report](GITHUB_RESEARCH_2026-10-15.md). For a process wrapper, test child-process coverage, filesystem escape paths, sensitive reads, and network egress on the selected OS/release.

Observe actual denied side effects and independent state, not a model statement that it complied. Include the allowed case so overblocking is visible. Keep stop handling on a trusted path. Do not present this recipe as an implemented dispatcher.

## Completion evidence

Record the pinned versions, host, protected operations, uncovered routes, positive/negative results, and cancellation limits. No universal containment claim is justified by a single MCP test or by the presence of Docker.
