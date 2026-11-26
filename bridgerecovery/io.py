"""データの読み込みヘルパ。"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from .paths import GRAPH_PATH, SCENARIO_PATH
from .scenario import Scenario


def load_graph(path: Path = GRAPH_PATH):
    import osmnx as ox

    if not Path(path).exists():
        raise FileNotFoundError(f"{path} がありません。先に python scripts/fetch_yokosuka.py を実行してください")
    return ox.load_graphml(path)


def load_scenario(path: Path = SCENARIO_PATH) -> Scenario:
    if not Path(path).exists():
        raise FileNotFoundError(f"{path} がありません。先に python scripts/make_scenario.py を実行してください")
    return Scenario.load(path)


def load_order(path: Path) -> list[str]:
    """提出ファイルを読む。JSON({"order": [...]} またはリスト)か、bridge_id 列を持つ CSV。"""
    path = Path(path)
    if path.suffix.lower() == ".json":
        d = json.loads(path.read_text(encoding="utf-8"))
        return list(d["order"] if isinstance(d, dict) else d)
    return pd.read_csv(path)["bridge_id"].astype(str).tolist()


def save_order(order: list[str], path: Path, method: str = "", author: str = "") -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    d = {"method": method, "author": author, "order": order}
    path.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
