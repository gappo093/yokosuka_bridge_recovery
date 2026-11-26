"""組合せ考慮の貪欲法 + 局所探索 + 焼きなまし法による復旧順序の最適化。

    python methods/kippei-pei.py
        -> 評価結果を表示し、submissions/kippei-pei.json を書き出す

考え方
------
1. 初期解(組合せ考慮の貪欲法)
   ベースラインの貪欲法は「1橋だけ直したときの改善量 ÷ 日数」で選ぶため、
   直列につながった橋のように「2本そろって初めて効く」橋を後回しにしてしまう。
   そこで候補を「1橋」と「2橋の組」に広げ、
   「その候補を直したときの改善量 ÷ 候補の合計日数」が最大のものから並べる
   (Smith 則 w_j / p_j を組に拡張したもの)。
2. 局所探索
   「1橋を別の位置へ移す(挿入)」「2橋を入れ替える(交換)」を、
   スコアが良くなる限り繰り返す。3班が並行して動くことは、
   評価関数と同じスケジュール計算(make_schedule)で直接評価するので自然に考慮される。
3. 焼きなまし法
   局所解から抜け出すため、悪化する操作も確率 exp(-Δ/T) で受け入れる。
   複数の乱数シードで実行し、最良の順序を提出する。

再現性: 乱数シード SEEDS、反復回数 SA_ITERS、温度 T0→T1 を下に記録する。
"""
from __future__ import annotations

import itertools
import math
import random
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from bridgerecovery.baselines import greedy_impact_per_day
from bridgerecovery.evaluate import Evaluator, make_schedule
from bridgerecovery.io import load_graph, load_scenario, save_order

METHOD_NAME = "pair-greedy + local search + simulated annealing"

# ---- 解析条件(再現性のため記録) ----
SEEDS = [0, 1, 2]  # 焼きなましの乱数シード
SA_ITERS = 4000  # シードあたりの焼きなまし反復回数
T0, T1 = 2e-3, 1e-5  # 焼きなましの初期・終了温度 [分](スコアの差の目安に合わせる)


class FastScore:
    """評価関数 ev.evaluate と同じスコアを、検証や時系列の記録を省いて速く計算する。"""

    def __init__(self, ev: Evaluator):
        self.ev = ev
        self.pos = {bid: i for i, bid in enumerate(ev.ids)}
        self.H = ev.scenario.horizon_days
        self.crews = ev.scenario.crews
        self.memo: dict[tuple, float] = {}

    def __call__(self, order: list[str]) -> float:
        key = tuple(order)
        if key in self.memo:
            return self.memo[key]
        ev, H = self.ev, self.H
        sched = make_schedule(order, ev.repair_days, self.crews)
        closed = set(range(len(ev.ids)))
        acc = ev.accessibility(frozenset(closed))[0]
        t_prev, integral = 0.0, 0.0
        for s in sorted(sched, key=lambda s: s["finish"]):
            if s["finish"] >= H:  # 評価期間の後に開く橋はスコアに影響しない
                break
            t = s["finish"]
            integral += acc * (t - t_prev)
            t_prev = t
            closed.discard(self.pos[s["bridge_id"]])
            acc = ev.accessibility(frozenset(closed))[0]
        integral += acc * (H - t_prev)
        score = integral / H
        self.memo[key] = score
        return score


def pair_greedy(ev: Evaluator) -> list[str]:
    """候補を「1橋」と「2橋の組」に広げた貪欲法。"""
    days = [ev.repair_days[b] for b in ev.ids]
    closed = set(ev.all_closed())
    order: list[int] = []
    while closed:
        base = ev.accessibility(frozenset(closed))[0]
        gain1 = {i: base - ev.accessibility(frozenset(closed - {i}))[0] for i in closed}
        best, best_val = None, None
        for i in closed:
            val = (gain1[i] / days[i], -days[i])
            if best_val is None or val > best_val:
                best, best_val = (i,), val
        # 組の改善量は計算が重いので、相乗効果がありそうな組だけ調べる:
        # 片方を単独で直しても効かない(改善量 ≒ 0)橋を含む組に限定する
        zero = [i for i in closed if gain1[i] <= 1e-9]
        for i in zero:
            for j in closed:
                if j == i:
                    continue
                g = base - ev.accessibility(frozenset(closed - {i, j}))[0]
                if g <= gain1[i] + gain1[j] + 1e-9:  # 相乗効果なし
                    continue
                val = (g / (days[i] + days[j]), -(days[i] + days[j]))
                if val > best_val:
                    # 組は「効く方(単独改善量の大きい方)」を先に置く
                    best = (j, i) if gain1[j] >= gain1[i] else (i, j)
                    best_val = val
        for i in best:
            closed.remove(i)
            order.append(i)
    return [ev.ids[i] for i in order]


def local_search(order: list[str], f: FastScore) -> list[str]:
    """挿入と交換で、改善がなくなるまで最良改善を繰り返す。"""
    cur, cur_s = list(order), f(order)
    n = len(cur)
    improved = True
    while improved:
        improved = False
        best, best_s = None, cur_s
        for i, j in itertools.permutations(range(n), 2):  # 挿入: i 番目を j 番目へ
            cand = cur[:i] + cur[i + 1:]
            cand.insert(j, cur[i])
            s = f(cand)
            if s < best_s - 1e-12:
                best, best_s = cand, s
        for i, j in itertools.combinations(range(n), 2):  # 交換
            cand = list(cur)
            cand[i], cand[j] = cand[j], cand[i]
            s = f(cand)
            if s < best_s - 1e-12:
                best, best_s = cand, s
        if best is not None:
            cur, cur_s, improved = best, best_s, True
    return cur


def simulated_annealing(order: list[str], f: FastScore, seed: int) -> list[str]:
    """挿入・交換をランダムに試し、悪化も確率 exp(-Δ/T) で受け入れる。"""
    rng = random.Random(seed)
    cur, cur_s = list(order), f(order)
    best, best_s = list(cur), cur_s
    n = len(cur)
    for k in range(SA_ITERS):
        T = T0 * (T1 / T0) ** (k / SA_ITERS)  # 指数的に冷やす
        i, j = rng.sample(range(n), 2)
        cand = list(cur)
        if rng.random() < 0.5:
            cand.insert(j, cand.pop(i))
        else:
            cand[i], cand[j] = cand[j], cand[i]
        s = f(cand)
        if s <= cur_s or rng.random() < math.exp(-(s - cur_s) / T):
            cur, cur_s = cand, s
            if s < best_s:
                best, best_s = list(cand), s
    return best


def solve(ev: Evaluator, verbose: bool = True) -> list[str]:
    f = FastScore(ev)
    t0 = time.time()

    def log(msg: str) -> None:
        if verbose:
            print(f"[{time.time() - t0:6.1f}s] {msg}", flush=True)

    starts = {"greedy_impact_per_day": greedy_impact_per_day(ev), "pair_greedy": pair_greedy(ev)}
    for name, o in starts.items():
        log(f"初期解 {name:22s} score={f(o):.4f}")
    start = min(starts.values(), key=f)

    cur = local_search(start, f)
    log(f"局所探索            score={f(cur):.4f}")

    results = []
    for seed in SEEDS:
        o = local_search(simulated_annealing(cur, f, seed), f)
        results.append((f(o), seed, o))
        log(f"焼きなまし seed={seed} → 局所探索 score={f(o):.4f}")
    scores = [r[0] for r in results]
    log(f"シード間のばらつき: 最良 {min(scores):.4f} / 最悪 {max(scores):.4f}")
    return min(results)[2]


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
