import datetime
import time as time_module

import pytest

from borgmatic_browse import times as module


@pytest.fixture
def auckland_time(monkeypatch):
    # Auckland is UTC+13 on the dates below (daylight saving time), so a missing or wrong
    # conversion shows up no matter which time zone the tests happen to run in.
    monkeypatch.setenv('TZ', 'Pacific/Auckland')
    time_module.tzset()
    yield
    monkeypatch.undo()
    time_module.tzset()


def test_format_time_with_naive_time_drops_seconds_and_keeps_local_time():
    assert module.format_time('2026-10-31T17:40:59.123456') == '2026-10-31 17:40'


def test_format_time_with_time_zone_converts_to_local_time():
    time = datetime.datetime(2026, 10, 31, 6, 40, 59, tzinfo=datetime.UTC)

    assert module.format_time(time.isoformat()) == time.astimezone().strftime('%Y-%m-%d %H:%M')


def test_format_time_with_invalid_time_raises():
    with pytest.raises(ValueError):
        module.format_time('yesterday')


def test_format_time_with_naive_time_does_not_shift_it_in_a_non_utc_time_zone(auckland_time):
    assert module.format_time('2026-10-31T17:40:59') == '2026-10-31 17:40'


def test_format_time_with_utc_offset_converts_to_local_time_across_midnight(auckland_time):
    assert module.format_time('2026-10-31T17:40:59+05:00') == '2026-11-01 01:40'


def test_format_time_with_z_suffix_converts_to_local_time(auckland_time):
    assert module.format_time('2026-10-31T12:40:59Z') == '2026-11-01 01:40'
