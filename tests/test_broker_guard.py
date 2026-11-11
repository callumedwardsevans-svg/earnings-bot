"""The paper-only guard is the most important safety check in the project."""

import pytest

from earnings_bot.broker import LiveTradingRefused, check_endpoint, make_trading_client
from earnings_bot.config import Settings

PAPER = "https://paper-api.alpaca.markets"
LIVE = "https://api.alpaca.markets"


def _never_called():
    raise AssertionError("confirmation prompt should not have been shown")


@pytest.mark.parametrize("url", [PAPER, PAPER + "/", PAPER + "/v2", "  " + PAPER + "  ", PAPER.upper()])
def test_paper_endpoint_allowed(url):
    assert check_endpoint(url, allow_live=False, confirm=_never_called) is True


def test_live_refused_without_flag():
    with pytest.raises(LiveTradingRefused, match="LIVE endpoint"):
        check_endpoint(LIVE, allow_live=False, confirm=_never_called)


def test_live_refused_with_flag_but_no_confirmation():
    with pytest.raises(LiveTradingRefused, match="confirmation"):
        check_endpoint(LIVE, allow_live=True, confirm=lambda: False)


def test_live_allowed_only_with_flag_and_confirmation():
    assert check_endpoint(LIVE, allow_live=True, confirm=lambda: True) is False


def test_default_prompt_refuses_when_not_interactive(monkeypatch):
    # Scheduled/CI runs have no TTY, so the default prompt must refuse.
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)
    with pytest.raises(LiveTradingRefused, match="confirmation"):
        check_endpoint(LIVE, allow_live=True)


@pytest.mark.parametrize(
    "url",
    [
        "http://paper-api.alpaca.markets",  # not https
        "https://paper-api.alpaca.markets.evil.com",  # look-alike host
        "https://paper-api-alpaca.markets",
        "https://data.alpaca.markets",
        "https://paper-api.alpaca.markets/v3/orders",
        "",
    ],
)
def test_unknown_or_malformed_urls_refused_even_with_flag(url):
    with pytest.raises(LiveTradingRefused):
        check_endpoint(url, allow_live=True, confirm=lambda: True)


def _settings(url, allow_live=False):
    return Settings(
        alpaca_key_id="PKTESTKEYID",
        alpaca_secret_key="supersecretvalue",
        alpaca_base_url=url,
        allow_live=allow_live,
    )


def test_client_factory_refuses_live_before_touching_keys():
    with pytest.raises(LiveTradingRefused):
        make_trading_client(_settings(LIVE), confirm=_never_called)


def test_client_factory_builds_paper_client():
    client = make_trading_client(_settings(PAPER))
    assert "paper-api" in client._base_url  # alpaca-py stores the resolved URL here


def test_settings_repr_hides_secrets():
    text = repr(_settings(PAPER))
    assert "supersecretvalue" not in text
    assert "PKTESTKEYID" not in text


def test_load_settings_allow_live_needs_exact_true(monkeypatch, tmp_path):
    from earnings_bot.config import load_settings

    empty_env = tmp_path / ".env"
    empty_env.write_text("")
    for value, expected in [("true", True), ("TRUE", True), ("1", False), ("yes", False), ("", False)]:
        monkeypatch.setenv("ALLOW_LIVE", value)
        assert load_settings(empty_env).allow_live is expected
