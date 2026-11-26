"""自分の手法のひな形。このファイルをコピーして methods/<GitHubユーザー名>.py を作る。

    cp methods/template.py methods/<GitHubユーザー名>.py
    python methods/<GitHubユーザー名>.py
        -> 評価結果を表示し、submissions/<GitHubユーザー名>.json を書き出す

変更してよいのは methods/ と submissions/ の自分のファイルだけです(共通コードは変更しない)。
"""
from __future__ import annotations

import sys
from itertools import combinations
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from bridgerecovery.baselines import shortest_repair_first
from bridgerecovery.evaluate import Evaluator
from bridgerecovery.io import load_graph, load_scenario, save_order

METHOD_NAME = "bundle_greedy_ls"


def find_bundles(ev: Evaluator, threshold: float = 1e-4) -> list[tuple[int, int, float]]:
    """2本そろって初めて効く橋の組(束)を探す。

    全閉鎖の状態で、橋 i, j を開けたときの改善量を g(i), g(j), g(i,j) とし、
    相乗効果 syn = g(i,j) - g(i) - g(j) [分] が threshold を超える組を、
    syn の大きい順に (i, j, syn)(i < j, ev.ids のインデックス)で返す。
    """
    closed = ev.all_closed()
    worst = ev.accessibility(closed)[0]
    n = len(ev.ids)
    g1 = [worst - ev.accessibility(closed - {i})[0] for i in range(n)]
    out = []
    for i, j in combinations(range(n), 2):
        syn = (worst - ev.accessibility(closed - {i, j})[0]) - g1[i] - g1[j]
        if syn > threshold:
            out.append((i, j, syn))
    out.sort(key=lambda t: -t[2])
    return out


def bundle_greedy(ev: Evaluator, bundles: list[tuple[int, int, float]]) -> tuple[list[str], list[dict]]:
    """束を考慮した貪欲法。

    各ステップで、未復旧の単独の橋 i(改善量 / days_i)と、両方未復旧の束 {i, j}
    (2本開けた改善量 / (days_i + days_j))を、**現在の状態で**比べて比率最大を採る。
    同率なら単独を優先し、次に bridge_id 順。束は日数の長い方を先に並べる。
    最大の改善量が 0 以下なら、残りを (日数, bridge_id) の昇順に並べて終わる。
    戻り値: (順序, ログ[{step, kind, bridges, gain, ratio}])
    """
    days = [ev.repair_days[b] for b in ev.ids]
    closed = set(ev.all_closed())
    order: list[str] = []
    log: list[dict] = []
    while closed:
        base = ev.accessibility(frozenset(closed))[0]
        cands = []  # (key, members, gain, ratio, kind)
        for i in closed:
            gain = base - ev.accessibility(frozenset(closed - {i}))[0]
            r = gain / days[i]
            cands.append(((-r, 0, ev.ids[i]), [i], gain, r, "single"))
        for i, j, _ in bundles:
            if i in closed and j in closed:
                gain = base - ev.accessibility(frozenset(closed - {i, j}))[0]
                r = gain / (days[i] + days[j])
                mem = sorted([i, j], key=lambda k: (-days[k], ev.ids[k]))
                cands.append(((-r, 1, min(ev.ids[i], ev.ids[j])), mem, gain, r, "bundle"))
        if max(c[2] for c in cands) <= 0:
            for i in sorted(closed, key=lambda k: (days[k], ev.ids[k])):
                order.append(ev.ids[i])
                log.append({"step": len(log) + 1, "kind": "fallback", "bridges": [ev.ids[i]],
                            "gain": 0.0, "ratio": 0.0})
            break
        _, mem, gain, r, kind = min(cands, key=lambda c: c[0])
        for k in mem:
            order.append(ev.ids[k])
            closed.discard(k)
        log.append({"step": len(log) + 1, "kind": kind, "bridges": [ev.ids[k] for k in mem],
                    "gain": gain, "ratio": r})
    return order, log


def solve(ev: Evaluator) -> list[str]:
    """復旧する順に bridge_id を並べたリストを返す。

    使える情報:
        ev.ids                      被災橋梁の bridge_id のリスト
        ev.repair_days[bid]         各橋の復旧日数
        ev.scenario.crews           復旧班の数
        ev.scenario.bridges         各橋の詳細(名前・道路種別・長さ・座標・辺)
        ev.accessibility(closed)    閉鎖中の橋(ev.ids のインデックス集合)でのアクセス性
        ev.evaluate(order)          順序全体のスコア(試行錯誤に使ってよい)
    """
    # ここを自分の手法に書き換える(今は「復旧日数の短い順」のまま)
    return shortest_repair_first(ev)


if __name__ == "__main__":
    name = Path(__file__).stem
    ev = Evaluator(load_graph(), load_scenario())
    order = solve(ev)
    print(ev.evaluate(order).summary())
    if name != "template":
        out = ROOT / "submissions" / f"{name}.json"
        save_order(order, out, method=METHOD_NAME, author=name)
        print(f"-> {out}")
    else:
        print("(template.py のままでは提出ファイルを書き出しません。コピーしてから実行してください)")
