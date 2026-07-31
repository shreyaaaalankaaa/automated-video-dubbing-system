from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .utils import read_json, write_json


@dataclass
class RunState:
    path: Path
    stages: dict[str, dict[str, Any]] = field(default_factory=dict)

    @classmethod
    def load(cls, path: Path) -> "RunState":
        payload = read_json(path, default={}) or {}
        return cls(path=path, stages=payload.get("stages", {}))

    def completed(self, stage: str) -> bool:
        return bool(self.stages.get(stage, {}).get("completed"))

    def mark(self, stage: str, **metadata: Any) -> None:
        self.stages[stage] = {
            "completed": True,
            "completed_at": datetime.now(UTC).isoformat(),
            **metadata,
        }
        write_json(self.path, {"stages": self.stages})
