"""ベースライン(比較用の単純な方針)。

どれも `(evaluator) -> list[str]`(bridge_id の復旧順序)の形をしている。
自分の手法も同じ形の関数にすれば、scripts/run_baselines.py に並べて比較できる。
"""
from __future__ import annotations

import random

from .evaluate import Evaluator


def random_order(ev: Evaluator, seed: int = 0) -> list[str]:
    """ランダム順(下限の目安)。"""
    order = list(ev.ids)
    random.Random(seed).shuffle(order)
    return order


def id_order(ev: Evaluator) -> list[str]:
    """ID 順(何も考えない場合)。"""
    return list(ev.ids)


def shortest_repair_first(ev: Evaluator) -> list[str]:
    """復旧日数の短い橋から(SPT 規則)。"""
    return sorted(ev.ids, key=lambda b: (ev.repair_days[b], b))


def greedy_impact_per_day(ev: Evaluator) -> list[str]:
    """貪欲法: 「その橋だけ直したときの改善量 ÷ 復旧日数」が最大の橋から選ぶ。

    橋どうしの組合せ効果(2本そろって初めて効く等)や復旧班の並列性は考えない。
    """
    closed = set(ev.all_closed())
    order = []
    while closed:
        base, _ = ev.accessibility(frozenset(closed))
        best_i, best_val = None, None
        for i in sorted(closed):
            gain = base - ev.accessibility(frozenset(closed - {i}))[0]
            val = (gain / ev.repair_days[ev.ids[i]], -ev.repair_days[ev.ids[i]])
            if best_val is None or val > best_val:
                best_i, best_val = i, val
        closed.remove(best_i)
        order.append(ev.ids[best_i])
    return order


BASELINES = {
    "id_order": id_order,
    "random": random_order,
    "shortest_repair_first": shortest_repair_first,
    "greedy_impact_per_day": greedy_impact_per_day,
}
