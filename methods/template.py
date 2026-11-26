"""自分の手法のひな形。このファイルをコピーして methods/<GitHubユーザー名>.py を作る。

    cp methods/template.py methods/<GitHubユーザー名>.py
    python methods/<GitHubユーザー名>.py
        -> 評価結果を表示し、submissions/<GitHubユーザー名>.json を書き出す

変更してよいのは methods/ と submissions/ の自分のファイルだけです(共通コードは変更しない)。
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from bridgerecovery.baselines import shortest_repair_first
from bridgerecovery.evaluate import Evaluator
from bridgerecovery.io import load_graph, load_scenario, save_order

METHOD_NAME = "template"  # 手法の短い名前に変える


def solve(ev: Evaluator) -> list[str]:
    """復旧する順に bridge_id を並べたリストを返す。

    使える情報:
        ev.ids                      被災橋梁の bridge_id のリスト
        ev.repair_days[bid]         各橋の復旧日数
        ev.scenario.crews           復旧班の数
        ev.scenario.bridges         各橋の詳細(名前・道路種別・長さ・座標・辺)
        ev.accessibility(closed)    閉鎖中の橋(ev.ids のインデックス集合)でのアクセス性
        ev.evaluate(order)          順序全体のスコア(試行錯誤に使ってよい)
    """
    # ここを自分の手法に書き換える(今は「復旧日数の短い順」のまま)
    return shortest_repair_first(ev)


if __name__ == "__main__":
    name = Path(__file__).stem
    ev = Evaluator(load_graph(), load_scenario())
    order = solve(ev)
    print(ev.evaluate(order).summary())
    if name != "template":
        out = ROOT / "submissions" / f"{name}.json"
        save_order(order, out, method=METHOD_NAME, author=name)
        print(f"-> {out}")
    else:
        print("(template.py のままでは提出ファイルを書き出しません。コピーしてから実行してください)")
