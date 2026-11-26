"""提出された復旧順序を評価する。

    python scripts/evaluate.py submissions/my_order.json
    python scripts/evaluate.py submissions/my_order.csv --timeline

提出ファイル:
    JSON: {"method": "...", "author": "...", "order": ["B0012", "B0003", ...]}
    CSV : bridge_id 列を持ち、上から復旧する順
    被災橋梁すべてを、重複なく1回ずつ並べること。
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bridgerecovery.evaluate import Evaluator
from bridgerecovery.io import load_graph, load_order, load_scenario


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("submission", type=Path)
    p.add_argument("--timeline", action="store_true", help="時刻ごとのアクセス性も表示")
    args = p.parse_args()

    ev = Evaluator(load_graph(), load_scenario())
    try:
        res = ev.evaluate(load_order(args.submission))
    except ValueError as e:
        raise SystemExit(f"提出ファイルが不正です: {e}")
    print(res.summary())
    if args.timeline:
        for t in res.timeline:
            print(f"  day {t['day']:6.1f}  開通 {t['open_bridges']:3d} 橋  "
                  f"平均 {t['minutes']:.3f} 分  到達可能 {t['reachable']:.1%}")


if __name__ == "__main__":
    main()
