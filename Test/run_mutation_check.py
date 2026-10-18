#!/usr/bin/env python3
"""Prove the live control check is not blind: break each gate, expect a failure.

run_live_control_check.py asserts that the verify, scope and review gates fire.
A check like that is only worth its result if it fails when the thing it checks
is broken, so this sabotages one gate at a time in a throwaway copy of the hook
and requires the live check to report a failure each time.

A surviving mutation means the live check does not actually cover that gate.

    python3 Test/run_mutation_check.py --output artifacts/mutations.json
"""

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from run_live_control_check import redact  # a sibling script, not a package

ROOT = Path(__file__).resolve().parents[1]
HOOK_REL = Path("Claude") / "hooks" / "apex_verify_hook.py"

# Each mutation disables one gate. `expect_step` names an observation in the
# live check that must then fail; it is the claim this mutation tests.
MUTATIONS: list[dict[str, str]] = [
    {
        "gate": "scope (edit guard)",
        "expect_step": "an out-of-scope file is refused",
        "old": "    if not in_scope(relative, allow):\n"
               "        deny(f\"{relative} is outside the approved scope",
        "new": "    if False and not in_scope(relative, allow):\n"
               "        deny(f\"{relative} is outside the approved scope",
    },
    {
        "gate": "scope (end-of-turn git sweep)",
        "expect_step": "a shell write outside the scope blocks the stop",
        "old": "        outside = [name for name in changed "
               "if not name.startswith(\".apex/\") and not in_scope(name, allow)]",
        "new": "        outside = []",
    },
    {
        "gate": "verify",
        "expect_step": "a failing verify blocks the stop and counts the attempt",
        "old": "    if code == 0:\n        finish(root, path, state, current, event)\n        return",
        "new": "    if True:\n        finish(root, path, state, current, event)\n        return",
    },
    {
        "gate": "review (is it demanded)",
        "expect_step": "a passing verify still requires the independent review",
        "old": "    if not (root / REVIEW).is_file() or "
               "(current is not None and state.get(\"reviewed\") == current):\n        return True",
        "new": "    if True:\n        return True",
    },
    {
        "gate": "review (does a FAIL verdict block)",
        "expect_step": "a failing review blocks the stop and reports the finding",
        "old": "    if current is not None and state.get(\"review_failed\") == current:",
        "new": "    if False and state.get(\"review_failed\") == current:",
    },
    {
        "gate": "question lock",
        "expect_step": "edits are locked for a question turn",
        "old": "    if lock and not claude_own_file(path):",
        "new": "    if False and not claude_own_file(path):",
    },
]


def copy_tree(destination: Path) -> None:
    """The live check only needs the hook, the project CLI and itself."""
    for relative in (HOOK_REL, Path("Claude") / "apex_project.py",
                     Path("Test") / "run_live_control_check.py"):
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative, target)


def run_live_check(tree: Path) -> tuple[bool, list[str]]:
    """Return (all observations passed, names of failed observations)."""
    output = tree / "result.json"
    subprocess.run([sys.executable, str(tree / "Test" / "run_live_control_check.py"),
                    "--output", str(output)],
                   capture_output=True, text=True, timeout=900, check=False)
    if not output.exists():
        return False, ["<live check produced no result>"]
    data = json.loads(output.read_text())
    failed = [o["step"] for o in data["observations"] if not o["passed"]]
    return data["passed"] == data["checks"], failed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    if args.output and args.output.exists():
        print(f"{args.output} already exists; choose a new path.", file=sys.stderr)
        return 2

    source = (ROOT / HOOK_REL).read_text(encoding="utf-8")
    results: list[dict[str, object]] = []

    print("0. Saglam hook: canli kontrol gecmeli")
    with tempfile.TemporaryDirectory(prefix="apex-mut-base-") as temp:
        tree = Path(temp)
        copy_tree(tree)
        clean_passed, clean_failed = run_live_check(tree)
    print(f"  {'PASS' if clean_passed else 'FAIL'}  baseline"
          + ("" if clean_passed else f" (beklenmedik hatalar: {clean_failed})"))
    results.append({"mutation": "<none>", "live_check_passed": clean_passed,
                    "failed_observations": clean_failed, "verdict": clean_passed})
    if not clean_passed:
        print("\nSaglam hook canli kontrolden gecmiyor; mutasyonlari denemek anlamsiz.")
        return 1

    for index, mutation in enumerate(MUTATIONS, 1):
        print(f"\n{index}. {mutation['gate']} sabote edildi")
        if mutation["old"] not in source:
            print("  FAIL  mutasyon uygulanamadi: hedef kod bulunamadi (hook degismis olabilir)")
            results.append({"mutation": mutation["gate"], "applied": False, "verdict": False})
            continue
        with tempfile.TemporaryDirectory(prefix="apex-mut-") as temp:
            tree = Path(temp)
            copy_tree(tree)
            (tree / HOOK_REL).write_text(
                source.replace(mutation["old"], mutation["new"], 1), encoding="utf-8")
            passed, failed = run_live_check(tree)
        caught = mutation["expect_step"] in failed
        print(f"  {'PASS' if caught else 'FAIL'}  canli kontrol bunu yakalamali: "
              f"\"{mutation['expect_step']}\"")
        if not caught:
            print(f"        canli kontrol {'gecti' if passed else 'basarisiz'}; "
                  f"bildirilen hatalar: {failed or 'yok'}")
        results.append({"mutation": mutation["gate"], "applied": True,
                        "expected_failure": mutation["expect_step"],
                        "failed_observations": failed, "verdict": caught})

    caught_count = sum(1 for r in results if r["verdict"])
    print(f"\n{caught_count}/{len(results)} kontrol gecti "
          f"({len(MUTATIONS)} mutasyon + saglam baseline)")
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(redact(
            {"mutations": len(MUTATIONS), "caught": caught_count - 1,
             "python": sys.version.split()[0], "results": results}),
            ensure_ascii=False, indent=2) + "\n")
        print(f"kanit: {args.output}")
    return 0 if caught_count == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
