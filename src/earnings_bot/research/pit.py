"""Shared point-in-time inputs for the research addendum (Step 0, Setup G, Setup F).

* Universe: tickers that were S&P 500 members at some point since 2010 (data/membership.py).
* Prices: Yahoo adjusted daily bars 2009-2026 (consolidated volume); Alpaca SIP from 2016 for
  names Yahoo has dropped (delisted).
* Earnings: the Yahoo + Alpha Vantage history, filtered to reports made while the company was
  an index member.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from earnings_bot.config import SETUP_A, SETUP_B
from earnings_bot.data import calendar, history, membership, universe, yahoo_prices
from earnings_bot.indicators import add_indicators

START = "2010-01-01"


def ind(df: pd.DataFrame) -> pd.DataFrame:
    return add_indicators(df, SETUP_A.ema_trend_period, SETUP_A.atr_period,
                          ema_rising_lookback=SETUP_B.ema_rising_lookback)


def load_prices(symbols, end: str = "2026-11-12"):
    """Yahoo 2009+ first; for names Yahoo has dropped (delisted), Alpaca SIP from 2016."""
    from earnings_bot.config import load_settings
    from earnings_bot.data import prices as alpaca_prices

    px, missing, source = {}, [], {}
    need_alpaca = []
    for s in symbols:
        df = yahoo_prices.load_history_range(s, "2009-01-01", end)
        if df is None or len(df) < 60:
            need_alpaca.append(s)
            continue
        px[s], source[s] = ind(df), "yahoo"
    if need_alpaca:
        alpaca_prices.update_prices(alpaca_prices.make_data_client(load_settings()), need_alpaca)
        for s in need_alpaca:
            df = alpaca_prices.load_prices(s)
            if df is None or len(df) < 60:
                missing.append(s)
            else:
                px[s], source[s] = ind(df), "alpaca (2016+)"
    return px, missing, source


def pit_filter(hist: pd.DataFrame, iv: pd.DataFrame) -> pd.DataFrame:
    """Keep reports where the ticker was an index member on the report date."""
    m = hist.merge(iv, left_on="symbol", right_on="ticker", how="inner")
    ok = (m.start.isna() | (m.start <= m.report_date)) & (m.end.isna() | (m.end > m.report_date))
    return m[ok].drop(columns=["ticker", "start", "end"]).drop_duplicates(["symbol", "report_date"])


@dataclass
class PitInputs:
    sessions: pd.DatetimeIndex
    intervals: pd.DataFrame
    px: dict
    source: dict
    missing: list
    hist_pit: pd.DataFrame
    universe: pd.DataFrame  # symbol, sector (Unknown:<sym> for past members), date_added


def load_inputs() -> PitInputs:
    sessions = calendar.load_sessions()
    iv = membership.load_intervals()
    tickers = membership.all_tickers_since(START, iv)
    syms = sorted({membership.data_symbol(t) for t in tickers} - {None} | {"SPY"})
    px, missing, source = load_prices(syms)
    sectors = universe.load_sp500().set_index("symbol").sector.to_dict()
    uni = pd.DataFrame({"symbol": sorted(px), "sector": [sectors.get(s, f"Unknown:{s}") for s in sorted(px)],
                        "date_added": pd.NaT})
    hist = history.load_history()
    return PitInputs(sessions, iv, px, source, missing, pit_filter(hist, iv), uni)
