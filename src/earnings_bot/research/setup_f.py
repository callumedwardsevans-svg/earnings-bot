"""Setup F: short-term momentum in high-turnover large caps (Medhat & Schmeling 2022), long-only.

Monthly, at each month-end close (formation):
* universe: point-in-time S&P 500 members, raw price > $10, turnover available, dual-class lines
  excluded (their share counts can't be matched to the traded class reliably);
* r1 = total return over the month (dividend-adjusted closes);
* turnover = sum of the month's raw consolidated daily volume / shares outstanding known at the
  month end, on the same split basis;
* pick: top quintile by turnover, then the top quintile of those by r1 (~20 names).
Holding month: equal weight, buy at the first open, sell at the last close (as written: flat
overnight between months).

Shares known at a date t (point in time):
* SEC EDGAR cover-page count, only if filed before t and the period ended within 200 days, and
  only for companies whose SEC ID comes from Wikipedia's CIK column or SEC's own ticker map;
* otherwise Yahoo's count, only if dated at least 45 days before t (Yahoo has no filing dates);
* if both exist and differ by more than 25%, Yahoo's ticker-specific count is used.
Counts are moved to the month-end split basis with f = raw close / split-adjusted close:
shares_t = N * f(as_of) / f(t).
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

from earnings_bot.data import membership, sec_shares
from earnings_bot.data.cache import DATA_DIR, UNIVERSE_DIR, read_parquet

DUAL_CLASS = {"GOOG", "GOOGL", "FOX", "FOXA", "NWS", "NWSA", "UA", "UAA", "BF.B", "BRK.B", "DISCA", "DISCK",
              "FOX_21CF", "FOXA_21CF"}
YAHOO_LAG_DAYS = 45
SEC_MAX_AGE_DAYS = 200


def split_factor(raw: pd.DataFrame, split: pd.DataFrame) -> pd.Series:
    f = (raw.close / split.close.reindex(raw.index)).dropna()
    return f.round(4)


def factor_at(f: pd.Series, d) -> float:
    d = pd.Timestamp(d)
    if f.empty:
        return 1.0
    s = f.loc[:d]
    return float(s.iloc[-1]) if len(s) else float(f.iloc[0])


def shares_on(t, sec_hist: pd.DataFrame | None, yahoo: pd.Series | None, f: pd.Series) -> tuple[float | None, str]:
    """Shares outstanding known at date t, on t's split basis, and which source was used."""
    t = pd.Timestamp(t)
    sec_v = None
    if sec_hist is not None:
        h = sec_hist[(sec_hist.filed < t) & (sec_hist.end >= t - pd.Timedelta(days=SEC_MAX_AGE_DAYS))]
        if len(h):
            row = h.sort_values(["end", "filed"]).iloc[-1]
            sec_v = float(row.val) * factor_at(f, row.end) / factor_at(f, t)
    y_v = None
    if yahoo is not None:
        y = yahoo.loc[: t - pd.Timedelta(days=YAHOO_LAG_DAYS)]
        y = y[y.index >= t - pd.Timedelta(days=SEC_MAX_AGE_DAYS + YAHOO_LAG_DAYS)]
        if len(y):
            y_v = float(y.iloc[-1]) * factor_at(f, y.index[-1]) / factor_at(f, t)
    if sec_v and y_v and not (0.8 <= sec_v / y_v <= 1.25):
        return y_v, "yahoo (SEC disagreed)"
    if sec_v:
        return sec_v, "sec"
    if y_v:
        return y_v, "yahoo"
    return None, "none"


def reliable_ciks() -> dict[str, int]:
    """Ticker -> CIK only where the ID comes from Wikipedia's CIK column or SEC's ticker map."""
    cm = read_parquet(UNIVERSE_DIR / "cik_map.parquet")
    ok = cm[cm.how.isin(["wikipedia", "sec ticker map"]) & cm.cik.notna()]
    return dict(zip(ok.ticker, ok.cik.astype(int)))


def build_panel(month_ends: pd.DatetimeIndex, px_adj: dict, iv: pd.DataFrame, yahoo_shares: dict) -> pd.DataFrame:
    """One row per (formation month end, ticker) with r1, turnover, raw price, membership."""
    ciks = reliable_ciks()
    rows = []
    tickers = sorted(set(iv.ticker) - DUAL_CLASS)
    for t in tickers:
        sym = membership.data_symbol(t)
        if not sym or sym not in px_adj:
            continue
        raw = read_parquet(DATA_DIR / "prices_raw" / f"{sym}.parquet")
        spl = read_parquet(DATA_DIR / "prices_split" / f"{sym}.parquet")
        if raw is None or raw.empty or spl is None or spl.empty:
            continue
        f = split_factor(raw, spl)
        sec_hist = sec_shares.shares_history(ciks[t])[0] if t in ciks else None
        ysh = yahoo_shares.get(sym)
        adj = px_adj[sym]
        vol_m = raw.volume.groupby(raw.index.to_period("M")).sum()
        spells = iv[iv.ticker == t]
        for me in month_ends:
            member = bool(((spells.start.isna() | (spells.start <= me)) & (spells.end.isna() | (spells.end > me))).any())
            if not member:
                continue
            p = me.to_period("M")
            if p not in vol_m.index or me not in raw.index:
                continue
            sh, src = shares_on(me, sec_hist, ysh, f)
            a_now = adj.close.loc[:me]
            a_prev = adj.close.loc[: (p - 1).to_timestamp(how="end")]
            a_12 = adj.close.loc[: (p - 12).to_timestamp(how="end")]
            if a_now.empty or a_now.index[-1] != me or a_prev.empty:
                continue
            rows.append({"month_end": me, "ticker": t, "symbol": sym, "raw_close": float(raw.close.loc[me]),
                         "r1": float(a_now.iloc[-1] / a_prev.iloc[-1] - 1),
                         "r_12_1": float(a_prev.iloc[-1] / a_12.iloc[-1] - 1) if len(a_12) and
                         (p - 12).to_timestamp(how="end") - a_12.index[-1] < pd.Timedelta(days=40) else np.nan,
                         "turnover": float(vol_m.loc[p] / sh) if sh else np.nan, "shares_source": src})
    return pd.DataFrame(rows)


def top_quintile(df: pd.DataFrame, col: str) -> pd.DataFrame:
    n = math.ceil(len(df) / 5)
    return df.sort_values(col, ascending=False).head(n)


def select_f(month: pd.DataFrame) -> pd.DataFrame:
    """Top quintile by turnover, then the top quintile of those by r1."""
    elig = month[(month.raw_close > 10) & month.turnover.notna() & month.r1.notna()]
    return top_quintile(top_quintile(elig, "turnover"), "r1")


def crash_guard_on(spy_close: pd.Series, t) -> bool:
    """Halve exposure if SPY's 12-month return < 0 and its 21-day vol is above the 80th
    percentile of the trailing 5 years (both measured at the formation close)."""
    s = spy_close.loc[:t]
    if len(s) < 260 * 5:
        return False
    r12 = s.iloc[-1] / s.iloc[-253] - 1
    vol = s.pct_change().rolling(21).std()
    hist = vol.iloc[-252 * 5:]
    return bool(r12 < 0 and vol.iloc[-1] > hist.quantile(0.8))
