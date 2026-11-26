# このリポジトリについて(Claude Code 向け)

横須賀市の道路網(OSMnx)上で、架空の被災橋梁の復旧順序を最適化する授業演習。詳細は README.md。

## 守ること
- `bridgerecovery/evaluate.py`(評価関数)と `data/` 以下は全員共通。学生の手法のために変更しない。
- `scripts/fetch_yokosuka.py` / `scripts/make_scenario.py` は実行しない(OSM の更新で橋の ID が変わり、スコアが比較不能になる)。
- 学生の手法は `bridgerecovery/baselines.py` と同じ `(ev: Evaluator) -> list[str]` の形で、自分用のファイル(例: `methods/<名前>.py`)に書く。
- 被災シナリオは架空。実在の被害であるかのような説明文を書かない。

## コマンド
- テスト: `python -m pytest`
- ベースライン比較: `python scripts/run_baselines.py`
- 提出物の評価: `python scripts/evaluate.py submissions/<file>.json`
