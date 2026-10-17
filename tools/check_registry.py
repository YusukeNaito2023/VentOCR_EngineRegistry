"""engines.json の形を確かめる: python3 tools/check_registry.py（問題が無ければ終了コード 0）。push の前に実行する。"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = ("engine_key", "repository", "tag", "commit", "ventilator", "manifest", "validation")
VALIDATION = ("reported", "engine_version", "date", "reporter", "videos", "breaths", "modes", "comment", "values", "waveforms")
RESULT = ("metric", "result", "n", "comment")


def main() -> int:
    data = json.loads((ROOT / "engines.json").read_text("utf-8"))
    problems = []
    if data.get("format") != 1:
        problems.append("format は 1")
    keys = set()
    for i, e in enumerate(data.get("engines", [])):
        name = e.get("engine_key", f"#{i}")
        problems += [f"{name}: {k} がありません" for k in REQUIRED if not e.get(k) and e.get(k) is not False]
        if name in keys:
            problems.append(f"{name}: engine_key が重複しています")
        keys.add(name)
        if not re.fullmatch(r"[0-9a-f]{40}", e.get("commit", "")):
            problems.append(f"{name}: commit は 40 桁のコミット")
        if not re.fullmatch(r"[\w.-]+/[\w.-]+", e.get("repository", "")):
            problems.append(f"{name}: repository は 所有者/名前")
        if (e.get("manifest") or {}).get("engine_key") != name:
            problems.append(f"{name}: manifest の engine_key が違います")
        v = e.get("validation") or {}
        problems += [f"{name}: validation.{k} がありません" for k in VALIDATION if k not in v]
        for group in ("values", "waveforms"):
            for col, r in (v.get(group) or {}).items():
                problems += [f"{name}: validation.{group}.{col}.{k} がありません" for k in RESULT if k not in r]
        if v.get("reported") and not (v.get("engine_version") and v.get("date") and v.get("breaths")):
            problems.append(f"{name}: reported なら engine_version・date・breaths を書く")
    for p in problems:
        print(p)
    print(f"{len(data.get('engines', []))} 個のエンジン、" + (f"{len(problems)} 件の問題" if problems else "問題ありません"))
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
