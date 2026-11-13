#!/usr/bin/env python3
"""Backfill tools_called / findings_count into already-written result.json files.

The OpenCode runner path records 0 for these because runner._read_session_cost
reads the wrong AGENT_SMITH_DIR path and greps '[TOOL_CALL]' (the log writes
'TOOL_CALL'). runner_local fixes this for NEW runs; this script repairs results
already on disk by recomputing from each lab's own agent_stderr.txt.

Usage:
    ./.venv/bin/python backfill_metrics.py [runs_dir]   # default: ./runs

Safe to re-run anytime (idempotent). tokens stay 0 (in OpenCode's SQLite db) and
total_cost stays 0.0 (correct for a local Spark model — no API cost).
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from runner_local import _opencode_lab_metrics, _lab_tokens  # noqa: E402

runs = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("runs")
patched = 0
for result in sorted(runs.glob("run_*/result.json")):
    try:
        d = json.loads(result.read_text())
    except Exception as e:
        print(f"skip {result}: {e}")
        continue
    tools, findings = _opencode_lab_metrics(result.parent / "outputs")
    ru = d.setdefault("agent_execution", {}).setdefault("resource_usage", {})
    before = (ru.get("tools_called", 0), ru.get("findings_count", 0), ru.get("input_tokens", 0))
    ru["tools_called"], ru["findings_count"] = tools, findings
    ex = d.get("execution", {})
    if ex.get("started_at") and ex.get("completed_at"):
        ru.update(_lab_tokens(ex["started_at"], ex["completed_at"]))
    result.write_text(json.dumps(d, indent=2))
    patched += 1
    print(f"{d.get('benchmark_id','?'):14} tools {before[0]}->{tools}  "
          f"findings {before[1]}->{findings}  in_tok {before[2]}->{ru.get('input_tokens',0):,}")
print(f"\npatched {patched} result.json file(s)")
