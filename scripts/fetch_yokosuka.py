"""横須賀市の車道ネットワークと拠点(病院)を OpenStreetMap から取得する。

    python scripts/fetch_yokosuka.py

出力:
    data/raw/yokosuka_drive.graphml  道路網(辺に length[m], speed_kph, travel_time[s], bridge など)
    data/raw/hubs.csv                拠点(病院)と最寄り道路ノード
"""
from __future__ import annotations

import argparse
import sys
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np
import osmnx as ox
import pandas as pd

from bridgerecovery.paths import CACHE_DIR, GRAPH_PATH, HUBS_PATH, RAW_DIR

PLACE = "Yokosuka, Kanagawa, Japan"
# 病院が取得できなかった場合の予備拠点(座標はおおよそ)
FALLBACK_HUBS = [{"name": "横須賀市役所(予備拠点)", "lat": 35.2813, "lon": 139.6722}]


def nearest_nodes(G, lats, lons) -> list[int]:
    nodes = list(G.nodes)
    ny = np.array([G.nodes[n]["y"] for n in nodes])
    nx_ = np.array([G.nodes[n]["x"] for n in nodes])
    out = []
    for lat, lon in zip(lats, lons):
        dy = (ny - lat) * 111_000
        dx = (nx_ - lon) * 111_000 * np.cos(np.radians(lat))
        out.append(int(nodes[int(np.argmin(dx * dx + dy * dy))]))
    return out


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--place", default=PLACE)
    args = p.parse_args()

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    ox.settings.use_cache = True
    ox.settings.cache_folder = str(CACHE_DIR)
    ox.settings.log_console = False

    print(f"[1/3] 道路網を取得中: {args.place} (初回は数分かかります)")
    G = ox.graph_from_place(args.place, network_type="drive", simplify=False)
    # 橋の区間と前後の一般区間が1本の辺にまとめられないよう、bridge タグの境目で辺を分ける
    G = ox.simplify_graph(G, edge_attrs_differ=["bridge"])
    # 一方通行の関係で行き来できない端のノードを除き、強連結な最大成分だけ残す
    G = ox.truncate.largest_component(G, strongly=True)
    G = ox.add_edge_speeds(G, fallback=30)
    G = ox.add_edge_travel_times(G)
    ox.save_graphml(G, GRAPH_PATH)
    print(f"      ノード {G.number_of_nodes():,} / 辺 {G.number_of_edges():,} -> {GRAPH_PATH}")

    print("[2/3] 拠点(病院)を取得中")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            gdf = ox.features_from_place(args.place, tags={"amenity": "hospital"})
            pts = gdf.geometry.representative_point()
        hubs = pd.DataFrame(
            {
                "name": gdf["name"].fillna("(名称なし)").values if "name" in gdf else "(名称なし)",
                "lat": pts.y.values,
                "lon": pts.x.values,
            }
        )
    except Exception as e:  # noqa: BLE001
        print(f"      病院の取得に失敗したため予備拠点を使います: {e}")
        hubs = pd.DataFrame(FALLBACK_HUBS)
    if hubs.empty:
        hubs = pd.DataFrame(FALLBACK_HUBS)
    hubs["node"] = nearest_nodes(G, hubs["lat"], hubs["lon"])
    hubs = hubs.drop_duplicates("node").reset_index(drop=True)
    hubs.to_csv(HUBS_PATH, index=False, encoding="utf-8-sig")
    print(f"      拠点 {len(hubs)} か所 -> {HUBS_PATH}")

    n_bridge = sum(1 for *_, b in G.edges(data="bridge") if b not in (None, "no"))
    print(f"[3/3] 完了。bridge タグ付きの辺: {n_bridge:,} 本")
    print("      次: python scripts/make_scenario.py")


if __name__ == "__main__":
    main()
