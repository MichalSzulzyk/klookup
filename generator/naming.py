from __future__ import annotations

from datetime import datetime
from pathlib import Path


def build_filename(hhmm: str, artist: str, created_at: datetime | None = None) -> str:
    now = created_at or datetime.now()
    return f"{hhmm}_{artist}_{now.strftime('%Y%m%d%H%M')}.jpg"


def build_sidecar_filename(hhmm: str, artist: str, created_at: datetime | None = None) -> str:
    now = created_at or datetime.now()
    return f"{hhmm}_{artist}_{now.strftime('%Y%m%d%H%M')}.json"


def find_latest(output_dir: Path, hhmm: str, artist: str) -> Path | None:
    matches = list(output_dir.glob(f"{hhmm}_{artist}_*.jpg"))
    if not matches:
        return None
    return sorted(matches, key=lambda p: p.stem.split("_")[-1])[-1]
