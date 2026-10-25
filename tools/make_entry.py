"""エンジンのリポジトリのタグから engines.json の版を作る・足す（format 2）。

    python3 tools/make_entry.py <エンジンのリポジトリ（手元の clone）> <タグ> [--ventilator 機種] [--repository 所有者/名前]

- 一覧は engine_key ごとに1つの項目で、版は versions[]（版の昇順）。インストールできるのは versions の版だけ
- タグの時点のファイル（manifest.json・core.py の ENGINE_VERSION・engine_options.json・README.md・layout.jpg・波形の列）を
  `git show <タグ>:<ファイル>` で読む（作業中の変更は使わない）。タグのコミットは GitHub に push 済みであること
- 版は 0.X.Y。タグ = v<版>、manifest.json の version = core.py の ENGINE_VERSION = 版 でなければ止める
- 既存のキーなら versions に足す（同じ版があれば置き換える。そのときは validation を残す）。新しいキーなら項目を作る。
  ventilator はキーごと（手で書くもの。--ventilator か manifest.json の ventilator で、無ければ前の値を残す）
- 新しい版の validation は空（reported: false）。値は manifest.json の accuracy の列、波形はエンジンが書く列から作る。
  前の版と中身が同じで評価を引き継ぐときは、手で写して engine_version を書き直す
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
# manifest.json に outputs.waves（出力の宣言。ENGINE_API.md §8.1）が無い古いエンジンで、ソースの文字から探す波形の名前
WAVE_CHANNELS = ("Pressure", "Flow", "Volume", "Edi", "Pes", "Ptranspulm")


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
        # 評価で除外する Alert（manifest の outputs.alerts の exclude_from_accuracy から。評価をしたら、実際に除外したものに直す）
        "excluded_alerts": [a["name"] for a in ((manifest.get("outputs") or {}).get("alerts") or [])
                            if isinstance(a, dict) and a.get("name") and a.get("exclude_from_accuracy")],
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
    declared = [w.get("name") for w in ((manifest.get("outputs") or {}).get("waves") or []) if isinstance(w, dict) and w.get("name")]
    waves = declared or [ch for ch in WAVE_CHANNELS if f'"{ch}"' in sources]

    repository = args.repository
    if not repository:
        url = git(repo, "remote", "get-url", "origin").strip()
        repository = re.sub(r"(\.git)?$", "", url.split("github.com")[-1].lstrip(":/"))
    version = manifest.get("version")
    core_version = m.group(1) if m else None
    if not isinstance(version, str) or not re.fullmatch(r"0\.\d+\.\d+", version):
        sys.exit(f"manifest.json の version が 0.X.Y ではありません: {version!r}")
    if args.tag != f"v{version}":
        sys.exit(f"タグ {args.tag} が manifest.json の version（v{version}）と違います")
    if core_version != version:
        sys.exit(f"core.py の ENGINE_VERSION（{core_version}）が manifest.json の version（{version}）と違います")
    release = {
        "version": version,
        "tag": args.tag,
        "commit": git(repo, "rev-list", "-n", "1", args.tag).strip(),
        "core_version": core_version,
        "manifest": manifest,
        "default_options": json.loads(options_text) if options_text else None,
        "readme": show(repo, args.tag, "README.md"),
        "layout": "layout.jpg" if exists(repo, args.tag, "layout.jpg") else None,
        "waveforms": waves,
    }

    registry = json.loads(REGISTRY.read_text("utf-8")) if REGISTRY.is_file() else {"format": 2, "engines": []}
    if registry.get("format") != 2:
        sys.exit(f"engines.json の format が 2 ではありません（{registry.get('format')}）")
    entry = next((e for e in registry["engines"] if e["engine_key"] == key), None)
    if entry is None:
        entry = {"engine_key": key, "repository": repository, "ventilator": None, "versions": []}
        registry["engines"].append(entry)
    entry["repository"] = repository
    entry["ventilator"] = manifest.get("ventilator") or args.ventilator or entry.get("ventilator")
    old = next((v for v in entry["versions"] if v["version"] == version), None)
    release["validation"] = (old or {}).get("validation") or blank_validation(manifest, waves)
    # 版を置き換えたとき: 増えた値（manifest の accuracy）・波形の欄を足す（書いてある評価は残す）
    blank = blank_validation(manifest, waves)
    for group in ("values", "waveforms"):
        current = release["validation"].setdefault(group, {})
        for name, item in blank[group].items():
            current.setdefault(name, item)
    entry["versions"] = sorted([v for v in entry["versions"] if v["version"] != version] + [release],
                               key=lambda v: tuple(int(x) for x in v["version"].split(".")))
    registry["engines"].sort(key=lambda e: e["engine_key"].lower())
    registry["updated"] = date.today().isoformat()
    REGISTRY.write_text(json.dumps(registry, ensure_ascii=False, indent=2) + "\n", "utf-8")
    print(f"{key} {args.tag}（{release['commit'][:12]}）を{'置き換え' if old else '追加し'}ました（版: {', '.join(v['version'] for v in entry['versions'])}）")
    if entry["ventilator"] is None:
        print("注意: ventilator（機種）がありません。--ventilator で指定してください")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
