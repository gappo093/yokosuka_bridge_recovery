"""道路網・被災橋梁・拠点を地図に描く。

    python scripts/plot_scenario.py   -> results/scenario_map.png
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import osmnx as ox

from bridgerecovery.io import load_graph, load_scenario
from bridgerecovery.paths import RESULTS_DIR

COLOR = {"小": "#f2a516", "中": "#e8590c", "大": "#c92a2a"}


def main() -> None:
    G = load_graph()
    sc = load_scenario()
    fig, ax = ox.plot_graph(G, show=False, close=False, node_size=0, edge_color="#bbbbbb",
                            edge_linewidth=0.3, bgcolor="white", figsize=(10, 10))
    for b in sc.bridges:
        for u, v, _ in b.edges:
            ax.plot([G.nodes[u]["x"], G.nodes[v]["x"]], [G.nodes[u]["y"], G.nodes[v]["y"]],
                    color=COLOR.get(b.damage, "red"), linewidth=3)
        ax.annotate(b.bridge_id, (b.lon, b.lat), fontsize=6, xytext=(3, 3), textcoords="offset points")
    ax.scatter([G.nodes[h]["x"] for h in sc.hubs], [G.nodes[h]["y"] for h in sc.hubs],
               marker="P", s=60, color="#1c7ed6", zorder=5, label="hub (hospital)")
    for lvl, c in [("small", "#f2a516"), ("medium", "#e8590c"), ("large", "#c92a2a")]:
        ax.plot([], [], color=c, linewidth=3, label=f"damaged bridge ({lvl})")
    ax.legend(loc="lower left")
    ax.set_title("Yokosuka: hypothetical damaged bridges (exercise scenario)")
    RESULTS_DIR.mkdir(exist_ok=True)
    out = RESULTS_DIR / "scenario_map.png"
    fig.savefig(out, dpi=200, bbox_inches="tight")
    print(f"-> {out}")


if __name__ == "__main__":
    main()
