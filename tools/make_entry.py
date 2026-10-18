"""エンジンのリポジトリのタグから engines.json の項目を作る・更新する。

    python3 tools/make_entry.py <エンジンのリポジトリ（手元の clone）> <タグ> [--ventilator 機種] [--repository 所有者/名前]

- タグの時点のファイル（manifest.json・core.py の ENGINE_VERSION・engine_options.json・README.md・layout.jpg・波形の列）を
  `git show <タグ>:<ファイル>` で読む（作業中の変更は使わない）。タグのコミットは GitHub に push 済みであること
- 同じ engine_key の項目があれば置き換える。ただし validation（精度の評価）と ventilator は残す（手で書くもの）。
  新しい版で増えた値・波形の欄は validation に足す（消えた値の欄は残すので、要らなければ手で消す）。
  版が変わったときは、validation の engine_version が古い版のままになる（アプリは「この評価は版 x のもの」と出す）。評価をやり直したら書き直す
- 新しい項目の validation は空（reported: false）。値は manifest.json の accuracy の列、波形はエンジンが書く列から作る
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "engines.json"
WAVE_CHANNELS = ("Pressure", "Flow", "Volume", "Edi", "Pes")


def git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True).stdout


def show(repo: Path, tag: str, path: str) -> str | None:
    try:
        return git(repo, "show", f"{tag}:{path}")
    except subprocess.CalledProcessError:
        return None


def exists(repo: Path, tag: str, path: str) -> bool:
    return subprocess.run(["git", "-C", str(repo), "cat-file", "-e", f"{tag}:{path}"], capture_output=True).returncode == 0


def blank_validation(manifest: dict, waves: list[str]) -> dict:
    return {
        "reported": False,
        "engine_version": None,
        "date": None,
        "reporter": None,
        "videos": None,
        "breaths": None,
        "modes": [],
        "comment": "",
        "values": {col: {"unit": (spec or {}).get("unit"), "metric": None, "result": None, "n": None, "comment": ""}
                   for col, spec in (manifest.get("accuracy") or {}).items()},
        "waveforms": {ch: {"metric": None, "result": None, "n": None, "comment": ""} for ch in waves},
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("repo", type=Path)
    parser.add_argument("tag")
    parser.add_argument("--ventilator", help="対応する人工呼吸器の機種（manifest.json に ventilator が無いとき）")
    parser.add_argument("--repository", help="GitHub の 所有者/名前（省略すると origin の URL から）")
    args = parser.parse_args()
    repo = args.repo.resolve()

    manifest_text = show(repo, args.tag, "manifest.json")
    if manifest_text is None:
        sys.exit(f"{args.tag} に manifest.json がありません")
    manifest = json.loads(manifest_text)
    key = manifest.get("engine_key")
    if not isinstance(key, str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", key):
        sys.exit("manifest.json に正しい engine_key がありません")
    core = show(repo, args.tag, "core.py") or ""
    m = re.search(r'^ENGINE_VERSION\s*=\s*["\']([^"\']+)["\']', core, re.M)
    options_text = show(repo, args.tag, "engine_options.json")
    sources = core + "".join(show(repo, args.tag, f) or "" for f in git(repo, "ls-tree", "--name-only", args.tag).split()
                             if f.endswith(".py") and f != "core.py")
    waves = [ch for ch in WAVE_CHANNELS if f'"{ch}"' in sources]

    repository = args.repository
    if not repository:
        url = git(repo, "remote", "get-url", "origin").strip()
        repository = re.sub(r"(\.git)?$", "", url.split("github.com")[-1].lstrip(":/"))
    entry = {
        "engine_key": key,
        "repository": repository,
        "tag": args.tag,
        "commit": git(repo, "rev-list", "-n", "1", args.tag).strip(),
        "ventilator": manifest.get("ventilator") or args.ventilator,
        "core_version": m.group(1) if m else None,
        "manifest": manifest,
        "default_options": json.loads(options_text) if options_text else None,
        "readme": show(repo, args.tag, "README.md"),
        "layout": "layout.jpg" if exists(repo, args.tag, "layout.jpg") else None,
        "waveforms": waves,
    }

    registry = json.loads(REGISTRY.read_text("utf-8")) if REGISTRY.is_file() else {"format": 1, "engines": []}
    old = next((e for e in registry["engines"] if e["engine_key"] == key), None)
    entry["ventilator"] = entry["ventilator"] or (old or {}).get("ventilator")
    entry["validation"] = (old or {}).get("validation") or blank_validation(manifest, waves)
    # 新しい版で増えた値（manifest の accuracy）・波形の欄を足す（書いてある評価は残す）
    blank = blank_validation(manifest, waves)
    for group in ("values", "waveforms"):
        current = entry["validation"].setdefault(group, {})
        for name, item in blank[group].items():
            current.setdefault(name, item)
    registry["engines"] = [e for e in registry["engines"] if e["engine_key"] != key] + [entry]
    registry["engines"].sort(key=lambda e: e["engine_key"].lower())
    registry["updated"] = date.today().isoformat()
    REGISTRY.write_text(json.dumps(registry, ensure_ascii=False, indent=2) + "\n", "utf-8")
    print(f"{key} {args.tag}（{entry['commit'][:12]}）を {'更新' if old else '追加'}しました")
    if entry["ventilator"] is None:
        print("注意: ventilator（機種）がありません。--ventilator で指定してください")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
