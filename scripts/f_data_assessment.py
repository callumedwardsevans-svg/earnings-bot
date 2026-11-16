"""Setup F data assessment: can turnover (volume / shares outstanding) be built point-in-time?

Run before any Setup F backtest. Writes docs/research/setup_f/DATA_ASSESSMENT.md and the CIK map.
"""

from __future__ import annotations

import io
import json
import random

import numpy as np
import pandas as pd
import requests

from earnings_bot.config import PROJECT_ROOT
from earnings_bot.data import membership, sec_shares, universe, yahoo_prices
from earnings_bot.data.cache import UNIVERSE_DIR, read_parquet, write_parquet
from earnings_bot.data.universe import CHANGES_PATH

OUT = PROJECT_ROOT / "docs" / "research" / "setup_f"
H = sec_shares.HEADERS


def build_cik_map(tickers, iv) -> pd.DataFrame:
    path = UNIVERSE_DIR / "cik_map.parquet"
    cached = read_parquet(path)
    if cached is not None and set(cached.ticker) >= set(tickers):
        return cached
    r = requests.get("https://en.wikipedia.org/wiki/List_of_S%26P_500_companies", headers=H, timeout=30)
    wiki = pd.read_html(io.StringIO(r.text))[0][["Symbol", "CIK", "Security"]]
    wiki_cik = dict(zip(wiki.Symbol, wiki.CIK))
    sec = {v["ticker"].replace("-", "."): v["cik_str"]
           for v in requests.get("https://www.sec.gov/files/company_tickers.json", headers=H, timeout=30).json().values()}
    ch = read_parquet(CHANGES_PATH)
    names = {}
    for col_t, col_n in (("added_ticker", "added_security"), ("removed_ticker", "removed_security")):
        for t, n in zip(ch[col_t], ch[col_n]):
            if isinstance(t, str) and isinstance(n, str):
                names[t.replace("|", "").strip()] = n
    rows = []
    for t in tickers:
        s = membership.data_symbol(t) or t
        if s in wiki_cik:
            rows.append((t, int(wiki_cik[s]), "wikipedia", None))
        elif s in sec:
            rows.append((t, int(sec[s]), "sec ticker map", None))
        elif t in names:
            hit = sec_shares.search_cik(names[t].split("(")[0].strip())
            rows.append((t, hit[0] if hit else None, "edgar name search" if hit else "unresolved",
                         f"{names[t]} -> {hit[1]}" if hit else names[t]))
        else:
            rows.append((t, None, "unresolved", None))
    df = pd.DataFrame(rows, columns=["ticker", "cik", "how", "match"])
    write_parquet(df, path)
    return df


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    iv = membership.load_intervals()
    iv = iv[iv.end.isna() | (iv.end > pd.Timestamp("2010-01-01"))]
    tickers = sorted(set(iv.ticker))
    cmap = build_cik_map(tickers, iv)
    current = set(universe.load_sp500().symbol)

    # shares history per ticker + month-level coverage over each membership spell
    months = pd.date_range("2010-01-31", "2026-10-31", freq="ME")
    cov_rows, hist_by_t, tag_used = [], {}, {}
    for r in cmap.itertuples():
        h, tag = (sec_shares.shares_history(int(r.cik)) if pd.notna(r.cik) else (None, None))
        hist_by_t[r.ticker], tag_used[r.ticker] = h, tag
        for sp in iv[iv.ticker == r.ticker].itertuples():
            a = sp.start if pd.notna(sp.start) else pd.Timestamp("2009-12-31")
            b = sp.end if pd.notna(sp.end) else pd.Timestamp("2026-11-30")
            for mth in months[(months > a) & (months <= b)]:
                ok = h is not None and sec_shares.shares_known_on(h, mth) is not None
                cov_rows.append((r.ticker, mth, ok, r.ticker in current))
    cov = pd.DataFrame(cov_rows, columns=["ticker", "month", "covered", "current"])
    cov["year"] = cov.month.dt.year

    # sanity: market cap = shares x unadjusted close in a mid-spell month must look like an S&P 500 company
    sanity = []
    for t, h in hist_by_t.items():
        if h is None:
            continue
        s = membership.data_symbol(t) or t
        px = yahoo_prices.load_history_range(s, "2009-01-01", "2026-11-12")
        mm = cov[(cov.ticker == t) & cov.covered].month
        if px is None or mm.empty:
            continue
        mth = mm.iloc[len(mm) // 2]
        sh = sec_shares.shares_known_on(h, mth)
        close = px.close.loc[:mth]
        if close.empty or sh is None:
            continue
        sanity.append((t, mth, sh, float(close.iloc[-1]), sh * float(close.iloc[-1])))
    san = pd.DataFrame(sanity, columns=["ticker", "month", "shares", "adj_close", "mcap_proxy"])
    # adj close understates past prices (dividends, splits), so this is a lower-bound style check

    # cross-check SEC vs Yahoo share counts (2016+, both raw) on a random sample of current members
    random.seed(7)
    sample = random.sample(sorted(t for t in hist_by_t if t in current and hist_by_t[t] is not None), 30)
    xc = []
    import yfinance as yf

    for t in sample:
        try:
            ys = yf.Ticker(t.replace(".", "-")).get_shares_full(start="2016-01-01", end="2026-11-15")
        except Exception:
            continue
        if ys is None or ys.empty:
            continue
        ys = ys[~ys.index.duplicated()]
        ys.index = ys.index.tz_localize(None)
        for mth in ["2018-06-30", "2021-06-30", "2025-06-30"]:
            sec_v = sec_shares.shares_known_on(hist_by_t[t], mth)
            yv = ys.loc[:mth]
            if sec_v and len(yv):
                xc.append((t, mth, sec_v / float(yv.iloc[-1])))
    xcdf = pd.DataFrame(xc, columns=["ticker", "month", "sec_over_yahoo"])

    # split data availability (needed to put raw shares and split-adjusted volume on one basis)
    split_rows = []
    for t in tickers:
        s = membership.data_symbol(t) or t
        try:
            sp = yf.Ticker(s.replace(".", "-")).splits
            split_rows.append((t, len(sp) if sp is not None else 0, sp is not None))
        except Exception:
            split_rows.append((t, 0, False))
    splits = pd.DataFrame(split_rows, columns=["ticker", "n_splits", "yahoo_has_record"])

    summary = {
        "tickers (members since 2010)": len(tickers),
        "CIK found": int(cmap.cik.notna().sum()),
        "CIK by source": cmap.how.value_counts().to_dict(),
        "tickers with shares history": int(sum(h is not None for h in hist_by_t.values())),
        "tag used": pd.Series(tag_used).value_counts(dropna=False).to_dict(),
        "member-months covered (all)": float(cov.covered.mean()),
        "member-months covered (current members)": float(cov[cov.current].covered.mean()),
        "member-months covered (past members)": float(cov[~cov.current].covered.mean()),
        "SEC vs Yahoo share counts: median ratio": float(xcdf.sec_over_yahoo.median()),
        "SEC vs Yahoo: share within 5%": float(((xcdf.sec_over_yahoo - 1).abs() <= 0.05).mean()),
        "n cross-checks": int(len(xcdf)),
        "market-cap proxy < $1bn (suspicious)": san[san.mcap_proxy < 1e9].ticker.tolist(),
        "tickers with splits on Yahoo record": int((splits.n_splits > 0).sum()),
    }
    by_year = cov.groupby("year").covered.mean()
    by_year_past = cov[~cov.current].groupby("year").covered.mean()
    (OUT / "assessment.json").write_text(json.dumps({**summary, "coverage_by_year": by_year.round(3).to_dict(),
                                                     "coverage_by_year_past_members": by_year_past.round(3).to_dict()},
                                                    indent=2, default=str))
    cmap.to_csv(OUT / "cik_map.csv", index=False)
    print(json.dumps(summary, indent=1, default=str))
    print(pd.DataFrame({"all": by_year, "past members": by_year_past}).round(3).to_string())
    print(cmap[cmap.how == "edgar name search"].head(25).to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
