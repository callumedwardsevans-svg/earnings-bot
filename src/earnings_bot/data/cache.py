"""Small helpers for the local cache (Parquet + raw JSON)."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from earnings_bot.config import PROJECT_ROOT

DATA_DIR = PROJECT_ROOT / "data"
PRICES_DIR = DATA_DIR / "prices"
RAW_DIR = DATA_DIR / "raw"
EARNINGS_DIR = DATA_DIR / "earnings"
UNIVERSE_DIR = DATA_DIR / "universe"
CALENDAR_DIR = DATA_DIR / "calendar"


def _atomic_replace(tmp: Path, path: Path) -> None:
    os.replace(tmp, path)  # atomic on the same volume, so a crash never leaves half a file


def write_parquet(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    df.to_parquet(tmp)
    _atomic_replace(tmp, path)


def read_parquet(path: Path) -> pd.DataFrame | None:
    return pd.read_parquet(path) if path.exists() else None


def write_json(obj, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj), encoding="utf-8")
    _atomic_replace(tmp, path)


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def age_hours(path: Path) -> float:
    """Hours since the file was last written (inf if missing)."""
    if not path.exists():
        return float("inf")
    mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    return (datetime.now(timezone.utc) - mtime).total_seconds() / 3600
