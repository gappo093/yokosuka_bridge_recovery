# 横須賀・被災橋梁の復旧順序 演習リポジトリ

地震で横須賀市内の橋が複数通行止めになった、という**架空のシナリオ**で、
「限られた復旧班で、どの順番で橋を直すと市民が早く病院へ行けるようになるか」を考える演習です。

> **注意**: 被災橋梁リストは乱数で作った仮のものです。実際の被害想定・点検結果とは関係ありません。
> 道路データ © OpenStreetMap contributors(ODbL)。

### 研究の中での位置づけ(「避難シミュレーションの進め方」との関係)

卒業研究「地震時の橋梁通行不能と復旧」は、時間の長さが違う2つの問題に分かれます。

| | 避難(発災直後) | 復旧(このリポジトリ) |
|---|---|---|
| 時間スケール | 数分〜数時間 | 数日〜数か月 |
| 移動手段 | 徒歩(`network_type="walk"`) | 車(`network_type="drive"`) |
| 目的地 | 避難場所 | 拠点(ここでは病院) |
| 問い | 橋が落ちると避難時間・孤立人口がどう変わるか | どの順で橋を直すと機能が早く戻るか |

共通する道具は「道路網から橋の辺を外して最短経路を計算し直す」ことです。
`scripts/bridge_importance.py`(橋を1本ずつ止めたときの影響度)は、資料6章の「橋ごとの影響度」にあたります。

評価関数のスコア(機能低下の時間平均)は、Bruneau et al.(2003, Earthquake Spectra 19(4))の
「機能損失を時間で積分した面積」でレジリエンスを測る考え方と同じ形です。

## 1. 準備(初回のみ)

環境構築は [docs/setup_wsl_superpowers.md](docs/setup_wsl_superpowers.md) を参照(WSL・Claude Code・Superpowers)。

```bash
# WSL(Ubuntu)/ macOS
uv venv && source .venv/bin/activate
uv pip install -r requirements.txt
```

```powershell
# Windows の PowerShell で直接動かす場合
uv venv; .venv\Scripts\activate
uv pip install -r requirements.txt
```

## 2. 動かしてみる

道路網(`data/raw/`)と仮シナリオ(`data/scenario/`)はリポジトリに入っているので、すぐに評価できます。

```bash
python -m pytest                 # 評価関数のテスト(8件が通ればOK。手計算できる小さな道路網で検証)
python scripts/run_baselines.py  # ベースライン4種を評価 -> results/leaderboard.csv
python scripts/plot_scenario.py  # 地図を描く -> results/scenario_map.png
python scripts/bridge_importance.py  # 橋を1本ずつ止めた影響度 -> results/bridge_importance.csv
python scripts/evaluate.py submissions/baseline_greedy_impact_per_day.json --timeline
```

データを作り直す場合(担当教員用。**各自は実行しないでください**。OSM の更新で橋の ID が変わり、スコアを比べられなくなります):

```bash
python scripts/fetch_yokosuka.py   # OSMnx で道路網と病院を取得(数分)
python scripts/make_scenario.py    # 仮の被災橋梁リストを作成(--n, --seed, --crews, --horizon で変更可)
```

## 3. 問題設定

| 項目 | 既定値 | 説明 |
|---|---|---|
| 被災橋梁 | 30橋 | `data/scenario/damaged_bridges.csv`。最初はすべて通行止め |
| 復旧日数 | 2〜100日 | 被害程度(小・中・大)と橋の長さで決まる。**演習用の仮値**(出典確認後に置き換える。`scripts/make_scenario.py` 冒頭) |
| 復旧班 | 3班 | 提出順の先頭から、手の空いた班が次の橋に取りかかる |
| 拠点 | 病院16か所 | OSM の `amenity=hospital` を最寄り道路ノードに割当て |
| 評価期間 | 240日 | |
| 上限時間 | 60分 | 拠点へ行けないノードは60分として数える |

**アクセス性** = 道路網の全ノードから最寄り拠点までの車での最短所要時間(分)の平均。
今は全ノードを同じ重みで扱っています。`Evaluator(G, sc, node_weights={ノード: 人口})` とすれば、人口で重み付けした平均になります(e-Stat の人口メッシュを使う発展課題)。
そのため、たとえば `bridge_importance.py` の上位には高速道路の橋が並びます。一方通行の本線上のノード(人は住んでいない)が「孤立」として数えられるのが一因です。結果を読むときの注意点として、議論の題材にしてください。

**簡略化していること**(研究で発展させる余地): 橋は「通行止め → 完全復旧」の2状態だけ(応急復旧での部分開通や車線規制はない)/
復旧班の移動時間なし / 橋以外の被害(斜面崩壊・建物倒壊による閉塞)なし / 交通量・渋滞なし。

**スコア** = 評価期間中のアクセス性の時間平均(分)。**小さいほど良い**。
あわせて `normalized = (全橋閉鎖のまま − スコア) / (全橋閉鎖のまま − 被害なし)` を出します(**1に近いほど良い**)。

### ベースライン(seed=2026 の既定シナリオ)

| 方針 | score [分] | normalized |
|---|---|---|
| ID順 | 3.947 | 0.352 |
| ランダム | 3.944 | 0.357 |
| 復旧日数の短い順 | 3.864 | 0.501 |
| 貪欲法(1橋だけ直した改善量 ÷ 日数) | 3.762 | 0.684 |

## 4. 自分の手法を作る

1. `bridgerecovery/baselines.py` と同じ形 `def my_method(ev: Evaluator) -> list[str]` で関数を書く
2. `ev.accessibility(closed)` で「この橋たちが閉鎖中のときのアクセス性」を何度でも計算できる(結果はキャッシュされる)
3. 提出ファイルを書き出して評価する

```python
from bridgerecovery.io import load_graph, load_scenario, save_order
from bridgerecovery.evaluate import Evaluator

ev = Evaluator(load_graph(), load_scenario())
order = my_method(ev)
print(ev.evaluate(order).summary())
save_order(order, "submissions/<学籍番号>.json", method="my_method", author="<名前>")
```

提出ファイルの書式: `{"method": "...", "author": "...", "order": ["B0006", "B0009", ...]}`
(被災橋梁30橋を重複なく1回ずつ並べる。CSV なら `bridge_id` 列を上から順に)

改善のヒント: 2本そろって初めて効く橋の組合せ、3班が並行して動くこと、局所探索(2橋の入れ替え)、焼きなまし など。

## 5. ファイル構成

```
bridgerecovery/        共通コード(原則として変更しない。直したい点は Issue で)
  evaluate.py          評価関数 Evaluator, make_schedule
  baselines.py         ベースライン
  bridges.py           道路網からの橋梁抽出
  scenario.py          シナリオのデータ構造
  io.py                読み書き
scripts/               実行スクリプト
data/raw/              道路網 graphml・病院・全橋梁リスト(共通)
data/scenario/         仮の被災シナリオ(共通)
submissions/           提出ファイル
tests/                 評価関数のテスト
docs/                  環境構築の手順書
```
