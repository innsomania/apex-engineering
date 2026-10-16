# Experimental execution controller

Status: experimental opt-in CLI. Existing live fixture evidence references Codex CLI 0.162.0; that does not certify other versions or desktop sessions. **Not enabled as a global control boundary.** The Codex desktop app does not route its existing tools through this adapter.

## Implemented boundary

[control.py](control.py) implements a UTF-8 file broker. A trusted caller supplies a root and exact, independent read/write permission lists. The broker copies these lists, rejects unknown operations and extra fields, and provides no policy mutation or resume operation. Path traversal, symbolic links, hard links, special files, excessive file sizes, and exhausted call budgets are rejected. Writes replace complete files atomically. Existing parent directories are required; deletion, shell execution, network requests, and directory creation are not offered.

The caller must keep its policy and controller outside writable files. The broker is not protection against another process running as the same OS user, direct Python access to its private fields, or concurrent malicious directory renames by an external process. It needs an independently contained host before use against untrusted models on real projects.

[codex_control.py](codex_control.py) starts a separate stdio App Server using the existing Codex login. It pins the tested CLI version, sets `environments: []`, requests read-only/no-network sandboxing and no approval escalation, disables selected native tool features and configured MCP servers, checks the effective restrictions and returned sandbox, and exposes `apex_file`. It rejects unknown client requests, unexpected tool identities, and replayed call IDs. Startup failure, disconnection, timeout, and normal termination close the broker to further dispatch. It does not modify global configuration or require a new model API account.

[controlled_cli.py](controlled_cli.py) is the explicit, opt-in one-turn entrypoint. It requires a project root, one or more repeated `--allow-write RELATIVE_PATH` arguments, an optional repeated `--allow-read RELATIVE_PATH` list, and `--prompt`. Paths must be canonical relative file paths and unique within each list. Invalid paths and roots are rejected before the App Server or model turn starts. Read and write lists are independent; a file is readable only when listed with `--allow-read` and writable only when listed with `--allow-write`.

[apex_host.py](apex_host.py) is the opt-in interactive entrypoint. It uses the same policy arguments, accepts an optional `--prompt` for the first turn, then asks for later prompts in the terminal, and runs successive turns on one controlled Codex thread. Type `:quit` or `:stop` between turns to close the session. Ctrl+C during a model turn closes broker admission and requests `turn/interrupt`; Ctrl+C at the prompt closes the session. Malformed or unexpected App Server messages stop the session and close broker admission. Completed writes are not undone. Example:

```sh
python3 Engineering/apex_host.py \
  --project-root /absolute/path/to/project \
  --allow-read README.md \
  --allow-write README.md \
  --prompt 'Update the introduction in README.md.'
```

At either entrypoint, paths must be canonical relative file paths and unique within each permission list. Read and write lists are independent; a file is readable only when listed with `--allow-read` and writable only when listed with `--allow-write`. The interactive host accepts non-empty prompts until the session is stopped or standard input closes. It never grants whole-project file access by default.

One-turn example:

```sh
python3 Engineering/controlled_cli.py \
  --project-root /absolute/path/to/project \
  --allow-read README.md \
  --allow-write README.md \
  --prompt 'Update the introduction in README.md.'
```

The interactive host's supported file writes are routed through the exact allowlist broker. Calls for other dynamic tools are denied and recorded. A command or tool outside the broker is not converted into a brokered write by policy text; its containment depends on the isolated App Server restrictions and the tested routes described below.

## Protected and uncovered routes

| Route | Enforced behavior | Coverage limit |
| --- | --- | --- |
| `apex_file` read | The broker reads only exact paths in `--allow-read`, under the selected project root; traversal, links, special files, and byte-budget violations are denied. | This protects broker reads only. It does not stop an OS process or unverified native host tool from reading other files available to that process. The App Server sandbox is read-only, which limits writes but does not establish read confidentiality. |
| `apex_file` write | The broker writes only exact paths in `--allow-write`; it rejects traversal, links, special files, excess bytes/calls, and operations after trusted stop. | Already completed writes remain. No delete, directory creation, shell, process, network, policy-change, or resume operation is exposed by the broker. |
| MCP and browser tools | Configured MCP servers and selected native browser features are disabled in this adapter. | They are not routed through the broker or exposed by this host. Add them only through an explicitly controlled route; normal desktop MCP and browser tools remain outside this host. |
| Other App Server / native host routes | The adapter sets feature overrides, disables configured MCP servers, verifies effective settings and the read-only/no-network thread sandbox, and denies unexpected client requests or non-`apex_file` dynamic-tool calls. The live evaluator passes its direct-write probe only when it observes a matching native command item, a nonzero command exit code, and an unchanged canary. | This is not a complete host-route matrix or universal bypass certification. Native reads are not contained; the read-only sandbox restricts writes, not reads. External tools and routes outside the configured adapter path are not contained. Native shell/command execution, undocumented protocol paths, nested processes, and any route not exercised by the probe remain uncovered. A model refusal or an unchanged canary without an observed command failure is inconclusive, not evidence of denial. |
| Codex desktop app | None. | Desktop sessions do not pass through this CLI, App Server adapter, or broker. No desktop containment claim is made. |

The broker does not contain other processes running as the same OS user (same UID), direct Python access to its private fields, or concurrent malicious directory renames by an external process. The desktop app is outside this route and receives no containment from this feature. Keep this feature opt-in and use it only where these limits are acceptable.

## Stop semantics

The trusted supervisor observes a stop event, marks the broker stopped, and requests `turn/interrupt`. File dispatch and broker stop are serialized. No new operation is admitted after the broker stop event; an already admitted operation may finish. Completed writes are not rolled back. A stopped broker cannot resume; a trusted caller must explicitly establish a new session.

An external event is polled at intervals up to 50 ms while awaiting protocol messages. This is not an instantaneous OS kill guarantee. The live test injects a trusted stop at the write request boundary, observes interrupt acknowledgement and `interrupted`, and independently checks that the file remained unchanged. It does not prove cancellation of arbitrary subprocess trees or stop behavior in an ordinary desktop chat.

## Verification

Focused broker, adapter-routing, and host policy tests:

```sh
python3 -m unittest Test.test_control -v
python3 -m unittest Test.test_apex_host -v
```

Opt-in real model fixture evaluation (uses the existing account and model configuration):

```sh
python3 Test/run_control_eval.py --output /absolute/path/to/new-evidence.json
```

The evaluator refuses an existing evidence destination and creates only temporary fixture files plus the requested evidence file. Its authorized edit uses the opt-in CLI entrypoint, followed by a stop-before-write scenario and one direct native command write probe. The probe is inconclusive unless the adapter observes the command item targeting the canary, sees a nonzero exit code, and confirms the canary is unchanged; model refusal alone does not pass. It is not a universal bypass certification. Ctrl+C requests interruption and does not automatically start the next fixture or publish evidence afterward.

See the [current observed results](../Test/CONTROL_EVALUATION_2026-10-16.md) and [earlier fixture results](../Test/CONTROL_EVALUATION_2026-10-15.md). Mandatory host control remains incomplete until the uncovered host routes are verified. Keep protected production operations disabled in this adapter.

## Protocol sources

- Installed `codex app-server generate-json-schema --experimental` output for version 0.162.0.
- [Official App Server protocol](https://developers.openai.com/codex/app-server): dynamic tools, stdio lifecycle, and `turn/interrupt`.
- [Official sandboxing documentation](https://learn.chatgpt.com/docs/sandboxing).
