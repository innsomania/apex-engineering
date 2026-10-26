"""python3 run_host.py HOST -> runs the three tasks for one host and writes runs/HOST/summary.json."""
import json, shutil, subprocess, sys, time
from pathlib import Path

E = Path(__file__).resolve().parent
APEX = Path("/Users/canaras/Desktop/Apex Engineering/run_apex.py")
TASKS = {
    "durations": ("parse_duration(\"1h30m\") 5400 donmesi gerekirken yanlis sonuc veriyor. Duzelt.", {"durations.py"}),
    "inventory": ("inventory.py'ye --json secenegi ekle: {\"count\": ..., \"total\": ...} yazdirsin. "
                  "Mevcut cikti ayni kalsin.", {"inventory.py"}),
    "report": ("Musteri raporu cok yavas calisiyor, hizlandir.", {"report.py"}),
}
HOST_ARGS = {
    "claude": ["-p", "--permission-mode", "acceptEdits", "--allowedTools", "Bash(python3:*)", "Bash(git status:*)",
               "Bash(git diff:*)", "Bash(ls:*)", "--max-turns", "30", "--max-budget-usd", "1.5",
               "--output-format", "stream-json", "--verbose"],
    "codex": ["exec", "--json", "-s", "workspace-write", "--skip-git-repo-check"],
    "opencode": ["--format", "json"],
}


def git(project, *args):
    return subprocess.run(["git", *args], cwd=project, capture_output=True, text=True).stdout


def usage(host, stream):
    events = []
    for line in stream.splitlines():
        try:
            events.append(json.loads(line))
        except ValueError:
            pass
    if host == "claude":
        final = [e for e in events if e.get("type") == "result"]
        return {"subtype": final[-1].get("subtype"), "cost_usd": final[-1].get("total_cost_usd"),
                "usage": final[-1].get("usage", {}) and {k: v for k, v in final[-1]["usage"].items()
                                                          if k.endswith("tokens")}} if final else {"subtype": "no result"}
    if host == "codex":
        turns = [e.get("usage") for e in events if e.get("type") == "turn.completed"]
        return {"usage": turns[-1] if turns else None, "commands": sum(1 for e in events if
                e.get("type") == "item.completed" and e.get("item", {}).get("type") == "command_execution")}
    totals: dict = {}
    for e in events:
        if e.get("type") == "step_finish":
            for k, v in (e.get("part", {}).get("tokens") or {}).items():
                if isinstance(v, (int, float)):
                    totals[k] = totals.get(k, 0) + v
    return {"usage": totals or None, "steps": sum(1 for e in events if e.get("type") == "step_finish")}


host = sys.argv[1]
summary = {}
for task, (prompt, allowed) in TASKS.items():
    project = E / "runs" / host / task
    shutil.rmtree(project, ignore_errors=True)
    shutil.copytree(E / "fixtures" / task, project)
    for args in (["init", "-q"], ["config", "user.email", "t@example.com"], ["config", "user.name", "t"],
                 ["add", "."], ["commit", "-qm", "fixture"]):
        git(project, *args)
    start = time.time()
    try:
        r = subprocess.run([sys.executable, str(APEX), "--host", host, "--task", prompt, "--", *HOST_ARGS[host]],
                           cwd=project, capture_output=True, text=True, timeout=1200, stdin=subprocess.DEVNULL)
        stream, code = r.stdout, r.returncode
        (E / "runs" / host / f"{task}.stderr").write_text(r.stderr)
    except subprocess.TimeoutExpired as exc:
        stream, code = (exc.stdout or b"").decode() if isinstance(exc.stdout, bytes) else (exc.stdout or ""), "timeout"
    (E / "runs" / host / f"{task}.jsonl").write_text(stream)
    changed = [line[3:] for line in git(project, "status", "--porcelain", "-uall").splitlines()]
    unexpected = [f for f in changed if f not in allowed and not (f.startswith("test") and f.endswith(".py"))
                  and "__pycache__" not in f]
    oracle = json.loads(subprocess.run([sys.executable, str(E / "oracles/oracle.py"), task, str(project)],
                                       capture_output=True, text=True, timeout=120).stdout or "{}")
    tests = subprocess.run([sys.executable, "-m", "unittest"], cwd=project, capture_output=True, text=True, timeout=300)
    summary[task] = {"exit": code, "seconds": round(time.time() - start), "oracle": oracle,
                     "project_tests": tests.stderr.strip().splitlines()[-1] if tests.stderr.strip() else "",
                     "changed": changed, "unexpected_changes": unexpected, **usage(host, stream)}
    (E / "runs" / host / "summary.json").write_text(json.dumps(summary, indent=1, ensure_ascii=False))
print(json.dumps(summary, indent=1, ensure_ascii=False))
