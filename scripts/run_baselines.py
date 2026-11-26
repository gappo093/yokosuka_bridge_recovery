"""ベースラインをすべて評価し、結果表と提出ファイル例を書き出す。

    python scripts/run_baselines.py

出力:
    results/leaderboard.csv
    submissions/baseline_<名前>.json   (提出ファイルの書式例を兼ねる)
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pandas as pd

from bridgerecovery.baselines import BASELINES
from bridgerecovery.evaluate import Evaluator
from bridgerecovery.io import load_graph, load_scenario, save_order
from bridgerecovery.paths import RESULTS_DIR


def main() -> None:
    G = load_graph()
    sc = load_scenario()
    ev = Evaluator(G, sc)
    print(f"被災 {len(sc.bridges)} 橋 / 拠点 {len(ev.hub_idx)} か所 / {sc.crews} 班 / {sc.horizon_days:g} 日")

    rows = []
    for name, fn in BASELINES.items():
        t0 = time.perf_counter()
        order = fn(ev)
        res = ev.evaluate(order)
        dt = time.perf_counter() - t0
        save_order(order, ROOT / "submissions" / f"baseline_{name}.json", method=name, author="baseline")
        rows.append({"method": name, "score_minutes": res.score_minutes, "normalized": res.normalized,
                     "makespan_days": res.makespan_days, "seconds": round(dt, 2)})
        print(f"  {name:24s} {res.summary()}  ({dt:.1f}s)")

    print(f"\n参考: 全橋閉鎖のまま {res.worst_minutes:.3f} 分 / 被害なし {res.best_minutes:.3f} 分")
    RESULTS_DIR.mkdir(exist_ok=True)
    df = pd.DataFrame(rows).sort_values("score_minutes")
    df.to_csv(RESULTS_DIR / "leaderboard.csv", index=False, encoding="utf-8-sig")
    print(f"-> {RESULTS_DIR / 'leaderboard.csv'}")


if __name__ == "__main__":
    main()
