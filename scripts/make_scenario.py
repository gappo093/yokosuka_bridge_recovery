"""仮の被災橋梁リスト(架空の被災シナリオ)を作る。

    python scripts/make_scenario.py              # 既定: 30橋, seed=2026, 3班, 240日
    python scripts/make_scenario.py --n 50 --seed 1

**注意: 被害は乱数で作った架空のもので、実際の被害想定・橋梁点検結果とは無関係です。**

被災の選び方(仮定):
    - 長さ 15 m 以上の橋から、長さ^0.5 × 道路種別の重み に比例する確率で選ぶ
    - 被害程度: 小 40% / 中 40% / 大 20%
    - 復旧日数: 小 2〜5日, 中 7〜20日, 大 25〜50日 を、長さに応じて割増し(最大2倍)

出力:
    data/raw/bridges_all.csv           道路網上の全橋梁
    data/scenario/damaged_bridges.csv  被災橋梁リスト(人が見る用)
    data/scenario/scenario.json        評価に使うシナリオ本体
"""
from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np
import pandas as pd

from bridgerecovery.bridges import extract_bridges
from bridgerecovery.io import load_graph
from bridgerecovery.paths import BRIDGES_ALL_PATH, DAMAGED_CSV_PATH, HUBS_PATH, SCENARIO_PATH
from bridgerecovery.scenario import DamagedBridge, Scenario

# ---------------------------------------------------------------------------
# 仮定パラメータ(演習用の仮値。文献の値ではない)
#
# 研究で使うときは、出典を確認した値に置き換えること。確認先の候補:
#   - 神奈川県 地震被害想定調査報告(道路・橋梁の章): 被害程度ごとの通行止め・規制期間
#   - FHWA HIF-23-034 / FEMA Hazus: 損傷状態(slight/moderate/extensive/complete)ごとの平均復旧日数
#   - 国総研資料(東日本大震災・熊本地震の橋梁復旧の経過): 応急復旧・本復旧の日数の実例
# 値を変えると橋の ID は同じでも復旧日数が変わるため、全員のスコアを取り直すこと。
# ---------------------------------------------------------------------------
CLASS_WEIGHT = {
    "motorway": 1.5, "trunk": 1.5, "primary": 1.5,
    "secondary": 1.2, "tertiary": 1.2,
}
DAMAGE_LEVELS = ["小", "中", "大"]
DAMAGE_PROB = [0.4, 0.4, 0.2]
REPAIR_RANGE = {"小": (2, 5), "中": (7, 20), "大": (25, 50)}


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--n", type=int, default=30, help="被災橋梁の数")
    p.add_argument("--seed", type=int, default=2026)
    p.add_argument("--crews", type=int, default=3, help="復旧班の数")
    p.add_argument("--horizon", type=float, default=240.0, help="評価期間(日)")
    p.add_argument("--cap", type=float, default=60.0, help="所要時間の上限(分)")
    p.add_argument("--min-length", type=float, default=15.0, help="候補にする橋の最小長さ(m)")
    args = p.parse_args()

    G = load_graph()
    bridges, edge_map = extract_bridges(G)
    bridges.to_csv(BRIDGES_ALL_PATH, index=False, encoding="utf-8-sig")
    print(f"道路網上の橋梁: {len(bridges)} 橋 -> {BRIDGES_ALL_PATH}")

    cand = bridges[bridges["length_m"] >= args.min_length].reset_index(drop=True)
    if len(cand) < args.n:
        raise SystemExit(f"候補が {len(cand)} 橋しかありません。--n か --min-length を小さくしてください")

    rng = np.random.default_rng(args.seed)
    w = np.sqrt(cand["length_m"]) * cand["highway"].map(CLASS_WEIGHT).fillna(1.0)
    pick = rng.choice(len(cand), size=args.n, replace=False, p=(w / w.sum()).to_numpy())
    dmg = cand.iloc[np.sort(pick)].copy().reset_index(drop=True)

    dmg["damage"] = rng.choice(DAMAGE_LEVELS, size=len(dmg), p=DAMAGE_PROB)
    base = [rng.integers(lo, hi + 1) for lo, hi in (REPAIR_RANGE[d] for d in dmg["damage"])]
    factor = np.minimum(1.0 + dmg["length_m"] / 200.0, 2.0)
    dmg["repair_days"] = [int(math.ceil(b * f)) for b, f in zip(base, factor)]

    hubs = pd.read_csv(HUBS_PATH)
    scenario = Scenario(
        bridges=[
            DamagedBridge(
                bridge_id=r.bridge_id, repair_days=float(r.repair_days), damage=r.damage,
                name=str(r.name) if isinstance(r.name, str) else "", highway=str(r.highway),
                length_m=float(r.length_m), lat=float(r.lat), lon=float(r.lon),
                edges=edge_map[r.bridge_id],
            )
            for r in dmg.itertuples()
        ],
        hubs=[int(n) for n in hubs["node"]],
        crews=args.crews,
        horizon_days=args.horizon,
        cap_minutes=args.cap,
        seed=args.seed,
    )
    scenario.save(SCENARIO_PATH)
    cols = ["bridge_id", "name", "highway", "length_m", "damage", "repair_days", "lat", "lon"]
    dmg[cols].to_csv(DAMAGED_CSV_PATH, index=False, encoding="utf-8-sig")

    print(f"被災橋梁: {len(dmg)} 橋 (小 {sum(dmg.damage == '小')} / 中 {sum(dmg.damage == '中')} / 大 {sum(dmg.damage == '大')})")
    print(f"復旧日数の合計: {dmg.repair_days.sum()} 日 / 復旧班 {args.crews} 班 / 評価期間 {args.horizon:g} 日")
    print(f"-> {DAMAGED_CSV_PATH}\n-> {SCENARIO_PATH}")
    print("次: python scripts/run_baselines.py")


if __name__ == "__main__":
    main()
