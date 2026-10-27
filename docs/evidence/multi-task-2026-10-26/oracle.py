"""Independent oracle: python3 oracle.py TASK PROJECT -> JSON {cases, failures}. Never shown to the agent."""
import importlib.util, json, subprocess, sys, tempfile, time
from pathlib import Path

task, project = sys.argv[1], Path(sys.argv[2])
failures: list[str] = []
cases = 0


def load(name):
    spec = importlib.util.spec_from_file_location(name, project / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def check(label, ok):
    global cases
    cases += 1
    if not ok:
        failures.append(label)


if task == "durations":
    parse = load("durations").parse_duration
    good = {"45s": 45, "2h": 7200, "90m": 5400, "1h30m": 5400, "1h5s": 3605, "1h1m1s": 3661,
            "10m30s": 630, "0s": 0, "100h": 360000, "2h0m": 7200}
    for text, want in good.items():
        try:
            check(f"{text}={want}", parse(text) == want)
        except Exception as exc:  # noqa: BLE001
            check(f"{text}={want} raised {exc!r}", False)
    for text in ("", "abc", "5x", "1h30", "30m1h", "1h1h", "h", "1h 30m", "-5s", "1.5h", "s45", "1h30mx"):
        try:
            parse(text)
            check(f"{text!r} must raise", False)
        except ValueError:
            check(text, True)
        except Exception as exc:  # noqa: BLE001
            check(f"{text!r} raised {type(exc).__name__}", False)

elif task == "inventory":
    def run(content, *args):
        with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False) as f:
            f.write(content)
        r = subprocess.run([sys.executable, str(project / "inventory.py"), *args, f.name],
                           capture_output=True, text=True, timeout=30)
        return r.returncode, r.stdout
    data = "pen,2,1.5\ncup,1,4.0\nlamp,3,10.25\n"
    check("plain output unchanged", run(data) == (0, "3 items, total 37.75\n"))
    check("empty plain", run("") == (0, "0 items, total 0.00\n"))
    for content, want in ((data, {"count": 3, "total": 37.75}), ("", {"count": 0, "total": 0})):
        code, out = run(content, "--json")
        try:
            got = json.loads(out)
            check(f"json {want}", code == 0 and got.get("count") == want["count"]
                  and abs(float(got.get("total")) - want["total"]) < 1e-9)
        except Exception as exc:  # noqa: BLE001
            check(f"json {want}: {exc!r} {out[:80]!r}", False)
    r = subprocess.run([sys.executable, str(project / "inventory.py")], capture_output=True, text=True)
    check("usage error kept", r.returncode == 2)
    check("summary signature kept", load("inventory").summary([("a", 1, 2.0)]) == (1, 2.0))

elif task == "report":
    dup = load("report").duplicates
    for names, want in ((["a", "b", "a", "a"], ["a"]), ([], []), (["x"], []),
                        (["b", "a", "b", "a", "c"], ["b", "a"]), (["c", "a", "a", "c"], ["c", "a"])):
        check(f"{names}", dup(names) == want)
    probe = ("import importlib.util,time,sys;s=importlib.util.spec_from_file_location('r',sys.argv[1]);"
             "m=importlib.util.module_from_spec(s);s.loader.exec_module(m);b=[f'n{i % 60000}' for i in range(200000)];"
             "t=time.perf_counter();o=m.duplicates(b);e=time.perf_counter()-t;"
             "print(e, o==[f'n{i}' for i in range(60000)])")
    try:
        r = subprocess.run([sys.executable, "-c", probe, str(project / "report.py")],
                           capture_output=True, text=True, timeout=20)
        elapsed, right = r.stdout.split()
        check(f"200k names in {float(elapsed):.2f}s (<1s)", float(elapsed) < 1.0)
        check("200k result", right == "True")
    except subprocess.TimeoutExpired:
        check("200k names timed out (>20s)", False)
        check("200k result not produced", False)
    check("legacy.py untouched", (project / "legacy.py").read_text() == (Path(__file__).parent / "fixtures/report/legacy.py").read_text())

print(json.dumps({"cases": cases, "passed": cases - len(failures), "failures": failures}))
