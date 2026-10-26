# Compact Apex execution — 2026-10-24

A live Codex CLI 0.164.0 run used `run_apex.py` command construction on the
same bounded C++ tenant-authorization task as the earlier local runs.

| Metric | Initial run | Shorter guidance | Compact session |
| --- | ---: | ---: | ---: |
| Cumulative input tokens | 124103 | 146894 | 83467 |
| Cached input tokens | 103552 | 127744 | 75392 |
| Uncached input tokens | 20551 | 19150 | 8075 |
| Output tokens | 730 | 857 | 625 |
| Independent access cases passed | 32 | 32 | 32 |

Compared with the initial observation, cumulative input fell 32.7%, uncached
input fell 60.7%, and output fell 14.4%. These are observed counts, not a billing
estimate or a controlled causal benchmark. Model defaults and caching were not
pinned; instructions and session routing both changed. One successful task does
not prove universal reliability or savings on other tasks or hosts.

The original implementation failed the independent oracle. The final source
passed all 32 access combinations; agent-added regression tests passed. Fixture
instructions were preserved and no unexpected top-level files remained. The
agent's one failing command reproduced the defect before the fix.

The compact session explicitly loaded Apex, omitted the automatic skills
catalog, and stopped after its focused verification. Global settings, host
permissions, and project rules were not changed. This is not a test of hook
containment, user-stop interruption, or Claude/OpenCode execution.

See [machine-readable results](../evidence/compact-codex-2026-10-24/result.json),
[agent report](../evidence/compact-codex-2026-10-24/agent-result.md), and
[fixed source](../evidence/compact-codex-2026-10-24/access.hpp).

Reproduce: `python3 tests/run_behavior_eval.py --output /tmp/apex-evaluation`.
The run needs existing Codex authentication and a C++ compiler; it does not
repair missing prerequisites.
