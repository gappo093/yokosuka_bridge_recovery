"""ペア束貪欲法 + 局所探索(作者: matugolo)。

    python methods/matugolo.py
        -> 束の表・束貪欲のステップ・手法比較を表示し、submissions/matugolo.json を書き出す

考え方:
  1. find_bundles   全閉鎖の状態で「2本そろって初めて効く橋の組」(相乗効果 > 1e-4 分)を探す。
  2. bundle_greedy  単独の橋と束を「現在の状態での改善量 / 班日数」で比べ、大きい順に並べる。
                    貪欲法(1橋ずつ)では改善 0 に見えて後回しになる橋を、相方と一緒に早められる。
  3. local_search   入れ替え・挿入の山登り(シード 2026、評価回数の上限 max_evals)で仕上げる。
シナリオは演習用の架空のもの。
"""
from __future__ import annotations

import random
import sys
from itertools import combinations
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import time

from bridgerecovery.baselines import greedy_impact_per_day
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


def local_search(ev: Evaluator, order: list[str], max_evals: int = 5000,
                 seed: int = 2026, stats: dict | None = None) -> tuple[list[str], list[dict]]:
    """入れ替え(swap)と挿入(insert)による山登り法(first-improvement)。

    近傍の並びは random.Random(seed) で1回だけシャッフルする(再現性のため)。
    改善(1e-9 より大きく下がる)した時点で採用し、近傍の先頭から走査し直す。
    1周して改善がないか、ev.evaluate の呼び出しが max_evals 回に達したら終わる。
    戻り値: (順序, 採用した移動[{move, a, b, before, after}])(a, b は順序上の位置)
    stats に辞書を渡すと {"evals": 評価回数, "converged": 1周改善なしで止まったか} を書き込む
    (False なら max_evals で打ち切り)。30橋の近傍は 1305 通り。max_evals=2000 では
    実データで打ち切られたため、既定値を 5000 にした(2026-11-26 時点で約4000回強で収束)。
    """
    n = len(order)
    moves = [("swap", a, b) for a in range(n) for b in range(a + 1, n)]
    moves += [("insert", a, b) for a in range(n) for b in range(n) if a != b]
    random.Random(seed).shuffle(moves)

    cur = list(order)
    cur_score = ev.evaluate(cur).score_minutes
    evals = 1
    log: list[dict] = []
    improved, budget_hit = True, False
    while improved and not budget_hit:
        improved = False
        for kind, a, b in moves:
            if evals >= max_evals:
                budget_hit = True
                break
            cand = list(cur)
            if kind == "swap":
                cand[a], cand[b] = cand[b], cand[a]
            else:
                cand.insert(b, cand.pop(a))
            s = ev.evaluate(cand).score_minutes
            evals += 1
            if s < cur_score - 1e-9:
                log.append({"move": kind, "a": a, "b": b, "before": cur_score, "after": s})
                cur, cur_score = cand, s
                improved = True
                break
    if stats is not None:
        stats.update({"evals": evals, "converged": not improved and not budget_hit})
    return cur, log


def solve(ev: Evaluator) -> list[str]:
    """束貪欲の順序を初期解として局所探索をかけた順序を返す。"""
    start, _ = bundle_greedy(ev, find_bundles(ev))
    order, _ = local_search(ev, start)
    return order


def report(ev: Evaluator) -> list[str]:
    """束の表・束貪欲のステップ・手法比較を表示し、最終順序(solve と同じ)を返す。"""
    ids, days = ev.ids, ev.repair_days
    bundles = find_bundles(ev)
    print(f"[1] 相乗効果のある組(全閉鎖から開けた場合): {len(bundles)} 組")
    for i, j, syn in bundles:
        print(f"    {ids[i]} + {ids[j]}  syn={syn:+.4f} 分  日数 {days[ids[i]]:g}/{days[ids[j]]:g}")

    start, glog = bundle_greedy(ev, bundles)
    print("[2] 束貪欲のステップ")
    for e in glog:
        print(f"    {e['step']:2d} {e['kind']:8s} {'+'.join(e['bridges']):13s} "
              f"改善={e['gain']:.4f} 分  比率={e['ratio']:.5f}")

    rows = []
    def add(label, order, sec=0.0, moves=None, st=None):
        r = ev.evaluate(order)
        stop = "" if st is None else f"{st['evals']}/{'収束' if st['converged'] else '打切'}"
        rows.append((label, r.score_minutes, r.normalized, r.makespan_days, sec, moves, stop))

    g = greedy_impact_per_day(ev)
    add("greedy", g)
    st_g, st_b = {}, {}
    t = time.perf_counter(); g_ls, g_log = local_search(ev, g, stats=st_g)
    add("greedy+LS", g_ls, time.perf_counter() - t, len(g_log), st_g)
    add("bundle_greedy", start)
    t = time.perf_counter(); final, b_log = local_search(ev, start, stats=st_b)
    add("bundle_greedy+LS", final, time.perf_counter() - t, len(b_log), st_b)

    print("[3] 比較(score は小さいほど良い)")
    print(f"    {'method':18s} {'score[分]':>10s} {'normalized':>10s} {'全橋復旧[日]':>12s} {'LS秒':>6s} {'LS移動':>6s} {'評価回数/停止':>12s}")
    for label, sc, nm, mk, sec, mv, stop in rows:
        print(f"    {label:18s} {sc:10.6f} {nm:10.4f} {mk:12.1f} {sec:6.1f} {'' if mv is None else mv:>6} {stop:>12s}")

    print("[4] bundle_greedy+LS で採用した移動(位置は 0 始まり)")
    for e in b_log:
        print(f"    {e['move']:6s} {e['a']:2d}->{e['b']:2d}  {e['before']:.4f} -> {e['after']:.4f}")
    return final


if __name__ == "__main__":
    name = Path(__file__).stem
    ev = Evaluator(load_graph(), load_scenario())
    order = report(ev)
    print(ev.evaluate(order).summary())
    out = ROOT / "submissions" / f"{name}.json"
    save_order(order, out, method=METHOD_NAME, author=name)
    print(f"-> {out}")
