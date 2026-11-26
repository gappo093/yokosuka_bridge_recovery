"""橋を1本ずつ通行止めにして、拠点へのアクセス性がどれだけ悪くなるか(橋ごとの影響度)を調べる。

    python scripts/bridge_importance.py           # 道路網上の全橋梁
    python scripts/bridge_importance.py --damaged # 被災シナリオの30橋だけ

出力: results/bridge_importance.csv(影響の大きい順)
    delta_minutes   その橋だけ止めたときの平均所要時間の増加 [分]
    lost_reach_pct  拠点へ行けなくなるノードの割合 [%](孤立)
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd

from bridgerecovery.bridges import extract_bridges
from bridgerecovery.evaluate import Evaluator
from bridgerecovery.io import load_graph, load_scenario
from bridgerecovery.paths import RESULTS_DIR
from bridgerecovery.scenario import DamagedBridge, Scenario


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--damaged", action="store_true", help="被災シナリオの橋だけを調べる")
    args = p.parse_args()

    G = load_graph()
    sc = load_scenario()
    if args.damaged:
        target = sc
    else:
        table, edge_map = extract_bridges(G)
        target = Scenario(
            bridges=[DamagedBridge(bridge_id=r.bridge_id, repair_days=1.0, name=r.name, highway=r.highway,
                                   length_m=r.length_m, lat=r.lat, lon=r.lon, edges=edge_map[r.bridge_id])
                     for r in table.itertuples()],
            hubs=sc.hubs, cap_minutes=sc.cap_minutes,
        )
    ev = Evaluator(G, target)
    base_min, base_reach = ev.accessibility(frozenset())

    rows = []
    for i, b in enumerate(target.bridges):
        m, reach = ev.accessibility(frozenset({i}))
        rows.append({"bridge_id": b.bridge_id, "name": b.name, "highway": b.highway, "length_m": b.length_m,
                     "delta_minutes": round(m - base_min, 5),
                     "lost_reach_pct": round(100 * (base_reach - reach), 3),
                     "lat": b.lat, "lon": b.lon})
    df = pd.DataFrame(rows).sort_values(["delta_minutes", "lost_reach_pct"], ascending=False)
    RESULTS_DIR.mkdir(exist_ok=True)
    out = RESULTS_DIR / "bridge_importance.csv"
    df.to_csv(out, index=False, encoding="utf-8-sig")
    print(f"平常時: 平均 {base_min:.3f} 分 / {len(target.bridges)} 橋を1本ずつ通行止めにした結果(上位10):")
    print(df.head(10)[["bridge_id", "name", "highway", "length_m", "delta_minutes", "lost_reach_pct"]]
          .to_string(index=False))
    print(f"-> {out}")


if __name__ == "__main__":
    main()
