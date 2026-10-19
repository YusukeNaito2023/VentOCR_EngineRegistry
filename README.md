# VentOCR_EngineRegistry

The list of VentOCR analysis engines that users can install from the VentOCR desktop app
(**Analysis > Engines…**). Only engines listed in [`engines.json`](engines.json) can be installed.
Each engine (one key per ventilator model) lists its released versions; each version pins a tag and commit
of the public engine repository and carries a validation report (accuracy of the values and agreement of the waveforms).

VentOCR のデスクトップアプリの「解析 > エンジン…」からインストールできるエンジンの一覧です。**ここに載っているエンジンだけ**が
インストールできます（ライセンスは MIT）。

## アプリでの使われ方

- アプリはネットにつながっていれば、エンジンの画面を開くたびと起動のときに、このリポジトリの `main` の最新の `engines.json` を読む
  （GitHub の API で `main` の最新のコミットを調べ、そのコミットのファイルを読むので、push した直後から反映される）。
  つながっていなければ前回読んだ一覧を使う
- エンジンの画面には、インストール済みのエンジンと一覧のエンジンを並べて出す。一覧のエンジンは「インストール」（versions の最新の版）、
  インストール済みで一覧の版と違えば「入れ替える」で、その版の `commit` の zip をダウンロードして入れる。入れておくのはキーごとに1つの版で、
  一覧の別の版（古い版も）に入れ直せる（VentOCR 0.6.0 から。0.5.x は format 1 しか読めず「VentOCR を更新してください」と出す）
- 一覧の項目にはエンジンの画面に出す情報（manifest.json・既定の設定・README・画面レイアウト）がすべて入っているので、
  インストールする前でも中身を確かめられる（画面レイアウトの画像だけは、表示するときに `commit` のものを読む）

## 形（format 2）

```json
{"format": 2, "updated": "2026-10-19",
 "engines": [{"engine_key": "hamilton_ventocr", "repository": "YusukeNaito2023/VentOCR_Hamilton", "ventilator": "Hamilton",
              "versions": [{"version": "0.1.0", "tag": "v0.1.0", "commit": "…", "manifest": {…}, "validation": {…}, …}]}]}
```

### エンジン（`engines` の1つ。エンジンキーごとに1つ）

| キー | 内容 |
|---|---|
| `engine_key` | エンジンキー（入れるフォルダの名前。manifest.json の `engine_key` と同じ）。機種ごとに1つで、版が上がっても変わらない |
| `repository` | エンジンの公開リポジトリ（`所有者/名前`） |
| `ventilator` | 対応する人工呼吸器の機種（絞り込みに使う。手で書く。`make_entry.py --ventilator`） |
| `versions` | 版の一覧（版の昇順。下） |

### 版（`versions` の1つ）

| キー | 内容 |
|---|---|
| `version` | 版（`0.X.Y`）。manifest.json の `version`・core.py の `ENGINE_VERSION` と同じ |
| `tag`, `commit` | 版のタグ（`v<版>`）と、そのコミット（40 桁）。アプリは `commit` の zip を使い、タグが動かされても中身は変わらない |
| `core_version` | core.py の `ENGINE_VERSION`（解析結果に記録される版。`version` と同じ） |
| `manifest` | タグの時点の manifest.json（そのまま） |
| `default_options` | engine_options.json（既定の設定） |
| `readme` | README.md の中身 |
| `layout` | 画面レイアウトの画像のファイル名（`commit` のもの。無ければ null） |
| `waveforms` | エンジンが書く波形の列（Pressure・Flow・Volume・Edi・Pes） |
| `validation` | 精度の評価（下。版ごと） |

`ventilator`・`validation` 以外は `tools/make_entry.py` が作る（手で書かない）。

### validation（精度の評価）

エンジンの開発者が検証して報告する。報告が無いものは `reported: false`（アプリは「未報告」と出す）。

| キー | 内容 |
|---|---|
| `reported` | 報告があるか |
| `engine_version` | 評価したエンジンの版（ふつうはその版。前の版の評価を写したときは、写したことを `comment` に書く） |
| `date`, `reporter` | 評価した日（YYYY-MM-DD）・評価した人 |
| `videos`, `breaths` | 評価に使った動画の数・呼吸の数 |
| `modes` | 評価した換気モード（例 `["PC-A/C", "PS", "NAVA"]`） |
| `comment` | 自由記載（評価の方法・対象・条件、苦手な画面など） |
| `values` | 値ごと（manifest.json の `accuracy` の列）: `{"unit", "metric", "result", "n", "comment"}` |
| `waveforms` | 波形ごと: `{"metric", "result", "n", "comment"}` |

- `metric` は評価の方法（例: 値は「完全一致率 (%)」「MAE」「Bias ± LoA（Bland-Altman）」、波形は「Pearson r」「RMSE」「DTW 距離」）、
  `result` はその結果（数値か、`"98.2%"`・`"0.3 ± 1.1"` のような文字）、`n` は評価に使った呼吸の数（全体と違うとき）
- 基準（正解）は何か（呼吸器のログ・手入力など）を `comment` に書く

## エンジンを載せる・版を上げる

1. エンジンのリポジトリで版を上げてタグ `v<版>` を付け、GitHub に push する（版は `0.X.Y`。`ENGINE_VERSION`・manifest.json の `version`・タグをそろえる。
   約束事は [VentOCR_EngineTemplate の ENGINE_API.md](https://github.com/YusukeNaito2023/VentOCR_EngineTemplate/blob/main/ENGINE_API.md) の §2）
2. このリポジトリで `python3 tools/make_entry.py ../VentOCR_<機種> v<版> [--ventilator 機種]`（そのキーの `versions` に版が足される。
   同じ版があれば置き換わり、その版の validation は残る。新しいキーなら項目ができる）
3. 新しい版の `validation` を書く（新しい版は空＝未報告で足される）
4. `python3 tools/check_registry.py` → コミットして `main` に push（別の人はプルリクエストで送る。一覧の管理者が確かめて取り込む）

一覧から版を消すと、アプリからはその版を新しくインストールできなくなる（インストール済みのものはそのまま使える）。
タグは消さない・動かさない（一覧の版がそのコミットを指している）。
