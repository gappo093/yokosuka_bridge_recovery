"""被災シナリオ(仮)のデータ構造と読み書き。"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path


@dataclass
class DamagedBridge:
    bridge_id: str
    repair_days: float
    damage: str = ""
    name: str = ""
    highway: str = ""
    length_m: float = 0.0
    lat: float = 0.0
    lon: float = 0.0
    edges: list[list[int]] = field(default_factory=list)  # [[u, v, key], ...]


@dataclass
class Scenario:
    bridges: list[DamagedBridge]
    hubs: list[int]  # 拠点(病院など)の道路網ノードID
    crews: int = 3  # 同時に作業できる復旧班の数
    horizon_days: float = 90.0  # 評価期間(日)
    cap_minutes: float = 60.0  # 到達不能・長時間の上限(分)。到達不能はこの値で数える
    seed: int | None = None
    note: str = "架空の被災シナリオ(演習用)。実際の被害想定ではない。"

    @property
    def bridge_ids(self) -> list[str]:
        return [b.bridge_id for b in self.bridges]

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(asdict(self), ensure_ascii=False, indent=1), encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> "Scenario":
        d = json.loads(Path(path).read_text(encoding="utf-8"))
        d["bridges"] = [DamagedBridge(**b) for b in d["bridges"]]
        return cls(**d)
