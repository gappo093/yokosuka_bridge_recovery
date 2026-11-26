"""評価関数。

問題設定
--------
- 被災橋梁はすべて通行止めから始まる。
- 復旧班 `crews` 班が、提出された順序 `order` の先頭から1橋ずつ受け持つ
  (手の空いた班が次の橋に取りかかる。移動時間は無視)。
- 橋は復旧が完了した時点で通行可能になる。
- 各時点のアクセス性 = 「全ノードから最寄り拠点(病院など)までの最短所要時間(分)」の平均。
  到達不能・上限超えは `cap_minutes` として数える。`node_weights` で人口による重み付けもできる。
- スコア = 評価期間 [0, horizon_days] でのアクセス性の時間平均(分)。**小さいほど良い。**
- normalized = (全橋閉鎖のまま - スコア) / (全橋閉鎖のまま - 被害なし)。**1に近いほど良い。**
"""
from __future__ import annotations

import heapq
from dataclasses import dataclass, field

import networkx as nx
import numpy as np
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import dijkstra

from .scenario import Scenario


@dataclass
class EvalResult:
    score_minutes: float  # 小さいほど良い
    normalized: float  # 1 に近いほど良い
    makespan_days: float  # 全橋の復旧完了日
    worst_minutes: float  # 全橋閉鎖のまま
    best_minutes: float  # 被害なし
    schedule: list[dict] = field(default_factory=list)  # 各橋の着工・完了日と担当班
    timeline: list[dict] = field(default_factory=list)  # 時刻ごとのアクセス性

    def summary(self) -> str:
        return (
            f"score={self.score_minutes:.3f} 分 (小さいほど良い) | "
            f"normalized={self.normalized:.4f} (1に近いほど良い) | "
            f"全橋復旧={self.makespan_days:.1f} 日"
        )


def make_schedule(order: list[str], repair_days: dict[str, float], crews: int) -> list[dict]:
    """順序どおりに、手の空いた班へ橋を割り当てる。"""
    free = [(0.0, c) for c in range(crews)]
    heapq.heapify(free)
    out = []
    for bid in order:
        t, c = heapq.heappop(free)
        finish = t + float(repair_days[bid])
        out.append({"bridge_id": bid, "crew": c, "start": t, "finish": finish})
        heapq.heappush(free, (finish, c))
    return out


class Evaluator:
    """道路網とシナリオを受け取り、復旧順序を評価する。

    `G` は OSMnx の MultiDiGraph(辺属性 `travel_time` [秒] が必要)。
    `node_weights` に {ノードID: 人口など} を渡すと、平均を重み付きにする(省略時は全ノード同じ重み)。
    """

    def __init__(self, G: nx.MultiDiGraph, scenario: Scenario, node_weights: dict | None = None):
        self.scenario = scenario
        self.ids = scenario.bridge_ids
        self.repair_days = {b.bridge_id: b.repair_days for b in scenario.bridges}
        bidx_of = {}
        for i, b in enumerate(scenario.bridges):
            for u, v, k in b.edges:
                if not G.has_edge(u, v, k):
                    raise ValueError(
                        f"シナリオの橋 {b.bridge_id} の辺 ({u}, {v}, {k}) が道路網にありません。"
                        "道路網を取り直した場合は OSM の更新で ID が変わります。"
                        "共通リポジトリの data/raw/yokosuka_drive.graphml を使ってください"
                    )
                bidx_of[(u, v, k)] = i

        nodes = list(G.nodes)
        idx = {n: i for i, n in enumerate(nodes)}
        self.n = len(nodes)
        if node_weights is None:
            wt = np.ones(self.n)
        else:
            wt = np.array([float(node_weights.get(n, 0.0)) for n in nodes])
            if wt.sum() <= 0:
                raise ValueError("node_weights の合計が 0 です")
        self._node_w = wt / wt.sum()
        src, dst, w, bidx = [], [], [], []
        for u, v, k, t in G.edges(keys=True, data="travel_time"):
            # 「各ノード → 拠点」の距離を拠点からの1回の探索で求めるため、辺を逆向きに持つ
            src.append(idx[v])
            dst.append(idx[u])
            w.append(max(float(t if t is not None else 0.0), 1e-3))
            bidx.append(bidx_of.get((u, v, k), -1))
        self._src = np.array(src)
        self._dst = np.array(dst)
        self._w = np.array(w)
        self._bidx = np.array(bidx)
        self.hub_idx = np.array(sorted({idx[h] for h in scenario.hubs if h in idx}))
        if len(self.hub_idx) == 0:
            raise ValueError("拠点ノードが道路網に見つかりません")
        self._cache: dict[frozenset, tuple[float, float]] = {}

    # ---- 状態ごとのアクセス性 ----
    def accessibility(self, closed: frozenset[int]) -> tuple[float, float]:
        """閉鎖中の橋(インデックス集合)に対する (平均所要時間[分], 到達可能ノード割合)。"""
        if closed in self._cache:
            return self._cache[closed]
        mask = ~np.isin(self._bidx, list(closed)) if closed else np.ones(len(self._w), bool)
        r, c, w = self._src[mask], self._dst[mask], self._w[mask]
        # 平行辺は最小の所要時間だけ残す(csr_matrix は重複を合計してしまうため)
        o = np.lexsort((w, c, r))
        r, c, w = r[o], c[o], w[o]
        keep = np.ones(len(r), bool)
        keep[1:] = (r[1:] != r[:-1]) | (c[1:] != c[:-1])
        M = csr_matrix((w[keep], (r[keep], c[keep])), shape=(self.n, self.n))
        d = dijkstra(M, directed=True, indices=self.hub_idx, min_only=True)
        minutes = np.minimum(d / 60.0, self.scenario.cap_minutes)
        res = (float(self._node_w @ minutes), float(self._node_w @ np.isfinite(d)))
        self._cache[closed] = res
        return res

    def all_closed(self) -> frozenset[int]:
        return frozenset(range(len(self.ids)))

    # ---- 提出物の評価 ----
    def validate(self, order: list[str]) -> None:
        if len(order) != len(set(order)):
            dup = sorted({b for b in order if order.count(b) > 1})
            raise ValueError(f"重複した bridge_id があります: {dup}")
        missing = set(self.ids) - set(order)
        extra = set(order) - set(self.ids)
        if missing or extra:
            raise ValueError(f"不足: {sorted(missing)} / 余分: {sorted(extra)}")

    def evaluate(self, order: list[str]) -> EvalResult:
        self.validate(order)
        H = self.scenario.horizon_days
        pos = {bid: i for i, bid in enumerate(self.ids)}
        sched = make_schedule(order, self.repair_days, self.scenario.crews)

        closed = set(self.all_closed())
        worst, _ = self.accessibility(frozenset(closed))
        best, _ = self.accessibility(frozenset())

        t_prev, integral = 0.0, 0.0
        acc, reach = self.accessibility(frozenset(closed))
        timeline = [{"day": 0.0, "minutes": acc, "reachable": reach, "open_bridges": 0}]
        for ev in sorted(sched, key=lambda s: s["finish"]):
            t = min(ev["finish"], H)
            integral += acc * (t - t_prev)
            t_prev = t
            closed.discard(pos[ev["bridge_id"]])
            acc, reach = self.accessibility(frozenset(closed))
            timeline.append(
                {"day": ev["finish"], "minutes": acc, "reachable": reach,
                 "open_bridges": len(self.ids) - len(closed)}
            )
        integral += acc * max(H - t_prev, 0.0)
        score = integral / H
        norm = (worst - score) / (worst - best) if worst > best else 1.0
        return EvalResult(
            score_minutes=score,
            normalized=norm,
            makespan_days=max(s["finish"] for s in sched),
            worst_minutes=worst,
            best_minutes=best,
            schedule=sched,
            timeline=timeline,
        )
