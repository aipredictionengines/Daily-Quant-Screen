from dqs.rules import verify_btc_range_rules


RULES = """
This market will resolve according to the final "Close" price of the Binance 1 minute candle
for BTC/USDT closing at 12:00 in the ET timezone (noon) on the date specified in the title.
The resolution source for this market is Binance, specifically the BTC/USDT "Close" prices
with "1m" and "Candles" selected. If the reported value falls exactly between two brackets,
then this market will resolve to the higher range bracket.
"""


def test_range_rule_signature_passes():
    check = verify_btc_range_rules(RULES)
    assert check.status == "PASS"
    assert check.source == "Binance"
    assert check.pair == "BTC/USDT"
    assert check.interval == "1m"
    assert check.metric == "Close"
    assert check.time_et == "12:00 America/New_York"
    assert check.candle_reference == "CLOSE_AT"
    assert check.boundary_rule == "EXACT_BOUNDARY_TO_HIGHER_BRACKET"


def test_missing_rule_text_is_verify_not_pass():
    assert verify_btc_range_rules(None).status == "VERIFY"
