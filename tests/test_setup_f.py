"""Setup F: point-in-time share counts, split basis, selection, crash guard."""

import numpy as np
import pandas as pd
import pytest

from earnings_bot.research.setup_f import crash_guard_on, select_f, shares_on


def test_shares_point_in_time_and_split_basis():
    f = pd.Series([4.0, 4.0, 1.0, 1.0], index=pd.to_datetime(["2020-07-01", "2020-08-28", "2020-08-31", "2020-09-30"]))
    sec = pd.DataFrame({"end": pd.to_datetime(["2020-07-17"]), "val": [4.3e9], "filed": pd.to_datetime(["2020-07-31"])})
    # known on 2020-09-30, from a pre-split filing: 4.3bn x 4 = 17.2bn on the post-split basis
    v, src = shares_on("2020-09-30", sec, None, f)
    assert src == "sec" and v == pytest.approx(17.2e9)
    # not yet filed on 2020-07-20 -> nothing known
    assert shares_on("2020-07-20", sec, None, f)[0] is None


def test_yahoo_lag_and_disagreement():
    f = pd.Series(1.0, index=pd.date_range("2020-01-01", "2020-12-31"))
    y = pd.Series([1e9], index=pd.to_datetime(["2020-06-01"]))
    assert shares_on("2020-07-01", None, y, f)[0] is None  # < 45 days old: not yet usable
    assert shares_on("2020-07-31", None, y, f)[0] == 1e9
    sec = pd.DataFrame({"end": pd.to_datetime(["2020-06-30"]), "val": [2e9], "filed": pd.to_datetime(["2020-07-10"])})
    v, src = shares_on("2020-07-31", sec, y, f)
    assert src.startswith("yahoo") and v == 1e9  # SEC differs by >25%: use the ticker-specific count


def test_selection_two_quintiles():
    n = 100
    df = pd.DataFrame({"ticker": [f"T{i}" for i in range(n)], "raw_close": 50.0,
                       "turnover": np.arange(n, dtype=float), "r1": np.arange(n, dtype=float)[::-1]})
    df.loc[95, "raw_close"] = 5.0  # below $10: excluded
    pick = select_f(df)
    # top 20 by turnover among 99 eligible are T79..T99 minus T95 -> 20 names; top 4 by r1 among them
    assert len(pick) == 4 and set(pick.ticker) == {"T79", "T80", "T81", "T82"}


def test_crash_guard():
    idx = pd.bdate_range("2015-01-01", "2021-12-31")
    calm = pd.Series(np.linspace(100, 200, len(idx)), index=idx)
    assert not crash_guard_on(calm, idx[-1])
    falling = calm.copy()
    tail = falling.index[-30:]
    falling[tail] = np.linspace(150, 60, 30) * (1 + 0.05 * np.sin(np.arange(30)))  # down 12m and volatile
    assert crash_guard_on(falling, idx[-1])
