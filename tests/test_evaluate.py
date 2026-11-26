"""評価関数のテスト(ネット接続・OSMnx 不要の小さな道路網で確認する)。

    python -m pytest
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import networkx as nx
import pytest

from bridgerecovery.baselines import BASELINES
from bridgerecovery.evaluate import Evaluator, make_schedule
from bridgerecovery.scenario import DamagedBridge, Scenario


def toy():
    """拠点 0 と町 1, 2 を結ぶ橋 A(0-1)と B(0-2)。迂回路 0-3-1 は遅い。

    0 ==A== 1        町1 は迂回路あり(20分)、町2 は橋 B が唯一の経路
    0 ==B== 2
    0 --- 3 --- 1
    """
    G = nx.MultiDiGraph()
    def road(u, v, sec):
        G.add_edge(u, v, travel_time=sec)
        G.add_edge(v, u, travel_time=sec)
    road(0, 1, 60)   # 橋A
    road(0, 2, 60)   # 橋B
    road(0, 3, 600)
    road(3, 1, 600)
    sc = Scenario(
        bridges=[
            DamagedBridge("A", repair_days=10, edges=[[0, 1, 0], [1, 0, 0]]),
            DamagedBridge("B", repair_days=10, edges=[[0, 2, 0], [2, 0, 0]]),
        ],
        hubs=[0], crews=1, horizon_days=40, cap_minutes=60,
    )
    return G, sc


def test_accessibility_states():
    G, sc = toy()
    ev = Evaluator(G, sc)
    # 被害なし: ノード0,1,2,3 = 0, 1, 1, 10 分 -> 平均 3
    assert ev.accessibility(frozenset())[0] == pytest.approx(3.0)
    # 全閉鎖: 0, 20(迂回), 60(到達不能=上限), 10 -> 平均 22.5
    m, reach = ev.accessibility(ev.all_closed())
    assert m == pytest.approx(22.5)
    assert reach == pytest.approx(0.75)


def test_node_weights():
    G, sc = toy()
    # 人口が町2 にしかいない場合: 全閉鎖で 60分(到達不能), 被害なしで 1分
    ev = Evaluator(G, sc, node_weights={2: 100})
    assert ev.accessibility(ev.all_closed()) == pytest.approx((60.0, 0.0))
    assert ev.accessibility(frozenset())[0] == pytest.approx(1.0)


def test_better_order_scores_better():
    G, sc = toy()
    ev = Evaluator(G, sc)
    good = ev.evaluate(["B", "A"])  # 孤立している町2 を先に
    bad = ev.evaluate(["A", "B"])
    assert good.score_minutes < bad.score_minutes
    assert 0.0 <= bad.normalized < good.normalized <= 1.0


def test_schedule_parallel_crews():
    s = make_schedule(["A", "B", "C"], {"A": 5, "B": 3, "C": 2}, crews=2)
    fin = {x["bridge_id"]: x["finish"] for x in s}
    assert fin == {"A": 5, "B": 3, "C": 5}  # C は B の班が 3日目から着手


@pytest.mark.parametrize("bad", [["A"], ["A", "A"], ["A", "B", "Z"]])
def test_invalid_submission(bad):
    G, sc = toy()
    with pytest.raises(ValueError):
        Evaluator(G, sc).evaluate(bad)


def test_baselines_return_valid_orders():
    G, sc = toy()
    ev = Evaluator(G, sc)
    for fn in BASELINES.values():
        ev.validate(fn(ev))
    assert BASELINES["greedy_impact_per_day"](ev)[0] == "B"
