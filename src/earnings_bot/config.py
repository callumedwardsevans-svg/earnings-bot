"""All risk limits, strategy parameters and environment settings in one place.

Risk limits are expressed as fractions of *current* account equity, so they scale
automatically with the ~$10k paper account (not Alpaca's default $100k).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]

# --------------------------------------------------------------------------- #
# Account
# --------------------------------------------------------------------------- #
# Approximate starting equity of the paper account. Used only for reporting
# (return since start, sanity check on connect). Sizing always uses live equity.
EXPECTED_STARTING_EQUITY = 10_000.0


# --------------------------------------------------------------------------- #
# Risk limits (checked before every order)
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class RiskLimits:
    risk_per_trade_pct: float = 0.0075  # 0.75% of equity; risk = (entry - stop) * shares
    max_position_pct: float = 0.15  # 15% of equity per position
    max_open_positions: int = 5
    max_positions_per_sector: int = 2
    daily_loss_limit_pct: float = 0.02  # equity down 2% on the day -> stop new entries
    kill_switch_file: Path = PROJECT_ROOT / "STOP"


RISK = RiskLimits()


# --------------------------------------------------------------------------- #
# Strategy parameters (filled in properly in milestone 3)
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class UniverseParams:
    min_price: float = 10.0
    min_avg_dollar_volume: float = 50_000_000.0
    avg_volume_window: int = 20


@dataclass(frozen=True)
class SetupAParams:  # post-earnings drift
    min_eps_surprise_pct: float = 5.0
    min_gap_pct: float = 3.0
    min_volume_multiple: float = 2.0
    ema_trend_period: int = 50
    atr_period: int = 14
    atr_stop_multiple: float = 2.0
    take_profit_r: float = 3.0
    max_hold_days: int = 20
    trail_atr_multiple: float = 2.0
    trail_activate_r: float = 1.0


@dataclass(frozen=True)
class SetupBParams:  # pre-earnings run-up
    entry_days_before_report: int = 7
    ema_trend_period: int = 50
    atr_period: int = 14
    atr_stop_multiple: float = 1.5


UNIVERSE = UniverseParams()
SETUP_A = SetupAParams()
SETUP_B = SetupBParams()

# Backtest costs
SLIPPAGE_BPS = 5.0  # each way
COMMISSION_PER_TRADE = 0.0


# --------------------------------------------------------------------------- #
# Environment / secrets
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Settings:
    """Values from .env. Secrets are excluded from repr so they can't leak into logs."""

    alpaca_key_id: str = field(repr=False)
    alpaca_secret_key: str = field(repr=False)
    alpaca_base_url: str
    allow_live: bool
    finnhub_api_key: str = field(default="", repr=False)
    alphavantage_api_key: str = field(default="", repr=False)


def load_settings(env_file: Path | None = None) -> Settings:
    """Load settings from .env (project root by default) plus the process environment."""
    load_dotenv(env_file or PROJECT_ROOT / ".env", override=False)
    return Settings(
        alpaca_key_id=os.getenv("ALPACA_KEY_ID", "").strip(),
        alpaca_secret_key=os.getenv("ALPACA_SECRET_KEY", "").strip(),
        alpaca_base_url=os.getenv("ALPACA_BASE_URL", "https://paper-api.alpaca.markets").strip(),
        allow_live=os.getenv("ALLOW_LIVE", "").strip().lower() == "true",
        finnhub_api_key=os.getenv("FINNHUB_API_KEY", "").strip(),
        alphavantage_api_key=os.getenv("ALPHAVANTAGE_API_KEY", "").strip(),
    )
