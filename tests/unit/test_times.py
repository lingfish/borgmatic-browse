import datetime

import pytest

from borgmatic_browse import times as module


def test_format_time_with_naive_time_drops_seconds_and_keeps_local_time():
    assert module.format_time('2026-10-31T17:40:59.123456') == '2026-10-31 17:40'


def test_format_time_with_time_zone_converts_to_local_time():
    time = datetime.datetime(2026, 10, 31, 6, 40, 59, tzinfo=datetime.UTC)

    assert module.format_time(time.isoformat()) == time.astimezone().strftime('%Y-%m-%d %H:%M')


def test_format_time_with_invalid_time_raises():
    with pytest.raises(ValueError):
        module.format_time('yesterday')
