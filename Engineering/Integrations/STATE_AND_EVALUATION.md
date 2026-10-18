# State and evaluation integration playbook

Read this when choosing a library for state, evaluation, or input filtering.
It decides which candidate is appropriate and what boundary each still
requires.

| Candidate | Appropriate role | Required boundary |
| --- | --- | --- |
| [Pydantic](https://github.com/pydantic/pydantic) | Validate task/action/evidence records in a future Python runtime | Well-formed data is not permission or truth |
| [LangGraph](https://github.com/langchain-ai/langgraph) | Durable state and interruptions when Apex owns the workflow | Does not control the host's internal agent loop |
| [promptfoo](https://github.com/promptfoo/promptfoo) | Repeatable behavioral evaluations and comparisons | Model/provider use needs actual configured access; no API assumed here |
| [NeMo Guardrails](https://github.com/NVIDIA-NeMo/Guardrails) | Supplementary input/output or dialogue checks | No replacement for protected action authorization |
| [Presidio](https://github.com/data-privacy-stack/presidio) | PII detection/redaction in relevant data flows | Detection is incomplete; do not equate it with all-secret protection |
| [garak](https://github.com/NVIDIA/garak) | Scoped adversarial model evaluation | Measure findings against the chosen model/configuration |
| [LLM Guard](https://github.com/protectai/llm-guard) | Excluded from new core adoption | Archived in the research snapshot; retained only for traceability |

## State design

Keep task identity, scope, evidence, selected decision, action state, and verification results explicit. Validate inputs at boundaries, reject ambiguous state transitions, and preserve cancellation state across retries/resumption. Persist only what the task needs. Distinguish trusted user events from model-generated fields.

Start with the smallest state representation that supports the workflow. Add durable orchestration when recovery/resumption requirements justify it. Do not introduce a second autonomous loop merely to use a framework.

## Evaluation design

Derive cases from user-visible outcomes and abuse paths, not instruction wording. Use legitimate and adversarial fixtures. Track incorrect scope expansion, unnecessary questions, unsupported claims, failed stopping, and quality of the resulting code/evidence. Preserve the input, relevant environment/version, actual output, and grading basis.

Use deterministic observation for side effects, denial, and file integrity. LLM judges can assist subjective review but cannot prove enforcement. Compare like-for-like model settings and tasks where possible. Redact sensitive evaluation data and distinguish local tooling from paid providers.

The [Engineering behavior scenarios](../../docs/evaluations/ENGINEERING_SCENARIOS.md) are a manual evaluation specification, not a report of passing runs. Do not mark them passed without executing and inspecting the stated evidence.
