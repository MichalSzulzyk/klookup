from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass
class GenResult:
    image_bytes: bytes
    original_size: tuple[int, int]
    cost_usd: float
    request_id: str | None
    model_id: str


class Backend(Protocol):
    key: str
    model_id: str

    def estimate_cost_usd(self, n_images: int, quality: str) -> float:
        ...

    def generate(self, prompt: str, refs: list[Path], quality: str) -> GenResult:
        ...
