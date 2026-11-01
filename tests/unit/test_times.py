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


def test_get_timestamp_returns_float():
    assert isinstance(module.get_timestamp('2026-10-31T17:40:59'), float)


def test_get_timestamp_with_utc_offset_returns_seconds_since_epoch():
    expected = datetime.datetime(2026, 10, 31, 6, 40, 59, tzinfo=datetime.UTC).timestamp()

    assert module.get_timestamp('2026-10-31T17:40:59+11:00') == expected


def test_get_timestamp_with_z_suffix_returns_seconds_since_epoch():
    expected = datetime.datetime(2026, 10, 31, 12, 40, 59, tzinfo=datetime.UTC).timestamp()

    assert module.get_timestamp('2026-10-31T12:40:59Z') == expected


def test_get_timestamp_keeps_fractional_seconds():
    assert module.get_timestamp('2026-10-31T12:40:59.5Z') == (
        module.get_timestamp('2026-10-31T12:40:59Z') + 0.5
    )


def test_get_timestamp_with_naive_time_assumes_local_time(auckland_time):
    # Auckland is UTC+13 on this date.
    expected = datetime.datetime(2026, 10, 31, 4, 40, 59, tzinfo=datetime.UTC).timestamp()

    assert module.get_timestamp('2026-10-31T17:40:59') == expected


def test_get_timestamp_with_invalid_time_raises():
    with pytest.raises(ValueError):
        module.get_timestamp('yesterday')


def test_get_timestamp_orders_times_across_a_daylight_saving_change():
    # Australian daylight saving time ends at 03:00 local on 2026-04-05, so 02:30 at +11:00 is
    # earlier than 02:10 at +10:00, even though it sorts later as a string.
    earlier = '2026-04-05T02:30:00+11:00'
    later = '2026-04-05T02:10:00+10:00'

    assert earlier > later
    assert module.get_timestamp(earlier) < module.get_timestamp(later)
