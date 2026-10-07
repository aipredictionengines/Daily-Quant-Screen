from dqs.adapters.polymarket import parse_hit_label, parse_range_label


def test_parse_range():
    assert parse_range_label("84,000-86,000") == (84000.0, 86000.0)
    assert parse_range_label("Will BTC be between $82,000 and $84,000 on October 7?") == (82000.0, 84000.0)


def test_parse_hit():
    assert parse_hit_label("↑ 85,000") == ("UP", 85000.0)
    assert parse_hit_label("Bitcoin above $90,000") == ("UP", 90000.0)
    assert parse_hit_label("↓ 81,000") == ("DOWN", 81000.0)
