"""道路網から橋梁(bridge タグ付きの道路区間)を抽出する。"""
from __future__ import annotations

import ast
import math

import networkx as nx
import pandas as pd


def as_list(x) -> list:
    """OSMnx の属性値(単一値 / リスト / リスト文字列 / NaN)をリストにそろえる。"""
    if x is None:
        return []
    if isinstance(x, float) and math.isnan(x):
        return []
    if isinstance(x, list):
        return x
    if isinstance(x, str) and x.startswith("["):
        try:
            return list(ast.literal_eval(x))
        except (ValueError, SyntaxError):
            return [x]
    return [x]


def is_bridge(value) -> bool:
    return any(str(v).strip().lower() not in ("", "no", "false", "0") for v in as_list(value))


def extract_bridges(G: nx.MultiDiGraph) -> tuple[pd.DataFrame, dict[str, list[list]]]:
    """bridge タグ付きの辺を「1つの橋」単位にまとめる。

    同じ OSM way を共有する辺、または同じ交差点ペアを結ぶ辺(上り・下り)を同じ橋とみなす。

    Returns:
        bridges: 1行1橋の表 (bridge_id, name, highway, length_m, lat, lon, n_edges)
        bridge_edges: bridge_id -> [[u, v, key], ...](通行止めにする有向辺)
    """
    bridge_edges = [
        (u, v, k, d) for u, v, k, d in G.edges(keys=True, data=True) if is_bridge(d.get("bridge"))
    ]

    # 辺・OSM way・交差点ペアを節点とするグラフの連結成分 = 1つの橋
    H = nx.Graph()
    for u, v, k, d in bridge_edges:
        e = ("edge", u, v, k)
        H.add_node(e)
        H.add_edge(e, ("pair", frozenset((u, v))))
        for oid in as_list(d.get("osmid")):
            H.add_edge(e, ("osm", int(oid)))

    groups = []
    for comp in nx.connected_components(H):
        edges = sorted((n[1], n[2], n[3]) for n in comp if n[0] == "edge")
        osmids = sorted(n[1] for n in comp if n[0] == "osm")
        groups.append((osmids[0] if osmids else 0, edges))
    groups.sort()

    rows, edge_map = [], {}
    for i, (_, edges) in enumerate(groups, start=1):
        bid = f"B{i:04d}"
        names, hwys, pair_len = [], [], {}
        for u, v, k in edges:
            d = G.edges[u, v, k]
            names += [n for n in as_list(d.get("name")) if n]
            hwys += as_list(d.get("highway"))
            pair = frozenset((u, v))
            pair_len[pair] = min(pair_len.get(pair, math.inf), float(d.get("length", 0.0)))
        nodes = {n for u, v, _ in edges for n in (u, v)}
        rows.append(
            {
                "bridge_id": bid,
                "name": names[0] if names else "",
                "highway": hwys[0] if hwys else "",
                "length_m": round(sum(pair_len.values()), 1),
                "lat": round(sum(G.nodes[n]["y"] for n in nodes) / len(nodes), 6),
                "lon": round(sum(G.nodes[n]["x"] for n in nodes) / len(nodes), 6),
                "n_edges": len(edges),
            }
        )
        edge_map[bid] = [[int(u), int(v), int(k)] for u, v, k in edges]

    return pd.DataFrame(rows), edge_map
