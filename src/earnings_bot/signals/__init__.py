"""Signal generators. Each returns (candidates, funnel).

``candidates`` has one row per tradeable signal with everything an order needs, using
only information available when the order would be sent. ``funnel`` counts how many
reports survive each filter, in order, for the report.
"""

CANDIDATE_COLUMNS = [
    "setup", "variant", "symbol", "sector", "date_added", "signal_date", "entry_date", "entry_type",
    "ref_price", "stop", "target", "atr", "exit_by", "max_hold_days", "trail", "eps_surprise_pct",
    "gap_pct", "rank", "notes",
]
