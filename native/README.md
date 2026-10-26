# Native Apex prototype

A C++17 launcher for existing Codex, Claude Code, and OpenCode CLIs on macOS
and Linux. It does not run a local LLM. It passes the task and Apex guidance to
the selected CLI without a shell and starts it in the requested project.

Build from the Apex checkout, using an existing compiler:

```sh
c++ -std=c++17 -Wall -Wextra -Wpedantic native/apex.cpp -o /tmp/apex-native
/tmp/apex-native --apex-root "$PWD" --project /absolute/path/to/project \
  --host codex --task 'Fix the specified bug' --dry-run
```

Remove `--dry-run` to start the host. Optional native host arguments follow `--`.
For example, use `--host claude --task 'Fix the specified bug' -- -p` alongside
the required root and project options. Existing host authentication and permission
settings are used; this launcher installs or changes none of them.

The host replaces the launcher process, preserving its exit status and normal
terminal signal handling. This first prototype does not supervise an agent loop,
intercept individual tool calls, impose a timeout, or provide its own sandbox.
The project path is a working directory and prompt instruction, not an enforced
filesystem boundary. Existing host permissions and installed Apex hooks remain
responsible for enforcement. Host arguments can override host behavior, including
the working directory; supply only arguments intended for that task.

Focused verification (fake host executables; no model calls):

```sh
python3 -m pytest -q tests/test_native_apex.py
```
