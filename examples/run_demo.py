"""Run a complete tiny experiment using only Python and Git, with no network."""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "plugins/evrik/skills/research/scripts/research.py"


def git(project: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(project), *args], check=True, capture_output=True, text=True).stdout.strip()


def command(project: Path, operation: str, *args: str) -> dict:
    proc = subprocess.run([sys.executable, str(RUNNER), operation, "--project", str(project), *args], capture_output=True, text=True)
    if proc.returncode:
        raise RuntimeError(f"{operation}: {proc.stderr or proc.stdout}")
    return json.loads(proc.stdout)


def make_project(project: Path, *, declare_entry: bool = True) -> Path:
    if project.exists() and any(project.iterdir()):
        raise ValueError("Demo workspace must be empty or nonexistent; existing work is never overwritten.")
    shutil.copytree(ROOT / "examples/small-regression", project, dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns("__pycache__", ".research"))
    git(project, "init", "-b", "main")
    git(project, "config", "user.name", "Evrik Demo")
    git(project, "config", "user.email", "demo@example.invalid")
    git(project, "config", "core.autocrlf", "false")
    git(project, "add", ".")
    git(project, "commit", "-m", "Record fixed synthetic regression baseline")
    command(project, "init")
    if declare_entry:
        command(project, "reconcile", "--no-inherited-notes", "--rationale",
                "This newly generated synthetic example has no inherited investigation or prior run records.")
    protocol = {
        "schema_version": 1,
        "name": "Synthetic regression",
        "question": "Does fitted linear regression reduce fixed-test MSE versus the training mean?",
        "command": ["{python}", "evaluate.py", "--output", "{result}"],
        "metric": {"name": "mse", "direction": "minimize", "min_improvement": 0.1},
        "data_paths": ["data.json"],
        "comparability": {"split": "fixed synthetic train/test", "randomness": "none"},
        "budget": {"max_runs": 4, "timeout_seconds": 15},
    }
    (project / ".research/protocol.json").write_text(json.dumps(protocol, indent=2) + "\n", encoding="utf-8")
    return project


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True)
    args = parser.parse_args()
    project = make_project(args.workspace.resolve())
    baseline = command(project, "prepare", "--label", "mean-baseline", "--hypothesis", "Training mean is the reference predictor.")
    baseline_result = command(project, "run", "--id", baseline["id"])
    (project / "model.json").write_text('{"method": "linear"}\n', encoding="utf-8")
    git(project, "add", "model.json")
    git(project, "commit", "-m", "Fit a linear predictor using training data only")
    candidate = command(project, "prepare", "--label", "linear-candidate", "--hypothesis", "Fitted slope captures the linear relationship.")
    candidate_result = command(project, "run", "--id", candidate["id"])
    comparison = command(project, "compare", "--baseline", baseline["id"], "--candidate", candidate["id"])
    report = {"baseline": baseline_result, "candidate": candidate_result, "comparison": comparison,
              "scope": "Deterministic synthetic smoke test; no real-world model-quality or efficiency claim."}
    report_path = project / ".research/demo-report.json"
    report_path.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({"report": str(report_path), "comparison": comparison}, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
