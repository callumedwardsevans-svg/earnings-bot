"""Setup F fix 1: verify every company-ID (CIK) match by market cap during the membership spell.

A match is accepted if the filed share count x the raw (unadjusted) close gives a market cap of
at least $1bn (and below $6tn) in the first and middle month of the ticker's membership since
2016. Name-search matches that fail are replaced by the next EDGAR candidate that passes; names
with no passing candidate are dropped from Setup F (counted in the report).
"""
from __future__ import annotations

import json

import pandas as pd

from earnings_bot.config import PROJECT_ROOT
from earnings_bot.data import membership, sec_shares
from earnings_bot.data.cache import DATA_DIR, UNIVERSE_DIR, read_parquet, write_parquet
from earnings_bot.data.universe import CHANGES_PATH

START = pd.Timestamp("2016-01-01")
OUT = PROJECT_ROOT / "docs" / "research" / "setup_f"


def check(cik: int, ticker: str, spells: pd.DataFrame, raw: pd.DataFrame | None) -> tuple[bool, str]:
    if raw is None or raw.empty:
        return False, "no raw prices"
    h, tag = sec_shares.shares_history(cik)
    if h is None:
        return False, "no SEC share data"
    for sp in spells.itertuples():
        a = max(sp.start if pd.notna(sp.start) else START, START)
        b = sp.end if pd.notna(sp.end) else pd.Timestamp("2026-10-31")
        if b <= a:
            continue
        for d in (a + pd.Timedelta(days=31), a + (b - a) / 2):
            sh = sec_shares.shares_known_on(h, d)
            close = raw.close.loc[:d]
            if sh is None or close.empty:
                return False, f"no share count on {d.date()}"
            mcap = sh * float(close.iloc[-1])
            if not (1e9 <= mcap <= 6e12):
                return False, f"market cap ${mcap / 1e9:.2f}bn on {d.date()}"
    return True, "ok"


def main():
    iv = membership.load_intervals()
    iv = iv[iv.end.isna() | (iv.end > START)]
    cmap = read_parquet(UNIVERSE_DIR / "cik_map.parquet")
    ch = read_parquet(CHANGES_PATH)
    names = {}
    for col_t, col_n in (("added_ticker", "added_security"), ("removed_ticker", "removed_security")):
        for t, n in zip(ch[col_t], ch[col_n]):
            if isinstance(t, str) and isinstance(n, str):
                names[t.replace("|", "").strip()] = n
    rows = []
    for t in sorted(set(iv.ticker)):
        sym = membership.data_symbol(t)
        raw = read_parquet(DATA_DIR / "prices_raw" / f"{sym}.parquet") if sym else None
        spells = iv[iv.ticker == t]
        cur = cmap[cmap.ticker == t]
        cik = int(cur.cik.iloc[0]) if len(cur) and pd.notna(cur.cik.iloc[0]) else None
        how = cur.how.iloc[0] if len(cur) else "unresolved"
        ok, why = check(cik, t, spells, raw) if cik else (False, "no CIK")
        final, note = (cik, how) if ok else (None, None)
        if not ok and t in names:  # try other EDGAR candidates for the company name
            for cand, ename in sec_shares.search_candidates(names[t].split("(")[0].strip()):
                if cand == cik:
                    continue
                ok2, why2 = check(cand, t, spells, raw)
                if ok2:
                    final, note = cand, f"replaced by EDGAR candidate '{ename}'"
                    break
        rows.append({"ticker": t, "original_cik": cik, "original_source": how, "original_check": why,
                     "final_cik": final, "final_source": note or "dropped"})
    df = pd.DataFrame(rows)
    write_parquet(df, UNIVERSE_DIR / "cik_map_verified.parquet")
    df.to_csv(OUT / "cik_map_verified.csv", index=False)
    s = {"tickers with membership since 2016": len(df),
         "passed as first matched": int((df.original_check == "ok").sum()),
         "fixed by another EDGAR candidate": int(df.final_source.str.startswith("replaced").sum()),
         "dropped": int((df.final_source == "dropped").sum()),
         "failures of first match, by reason": df[df.original_check != "ok"].original_check.str.split(" on ").str[0].value_counts().to_dict(),
         "first-match failures by source": df[df.original_check != "ok"].original_source.value_counts().to_dict()}
    (OUT / "cik_verification.json").write_text(json.dumps(s, indent=2))
    print(json.dumps(s, indent=1))
    print(df[df.final_source.str.startswith("replaced")][["ticker", "original_check", "final_source"]].to_string(index=False))
    print("dropped:", df[df.final_source == "dropped"][["ticker", "original_check"]].values.tolist())


if __name__ == "__main__":
    main()
