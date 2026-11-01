import datetime


def get_timestamp(time):
    '''
    Given a time as an ISO 8601 string, return it as a float number of seconds since the epoch, for
    comparing times. Comparing the strings isn't enough, because times in an archive may have
    different UTC offsets, e.g. on either side of a daylight saving change. Assume that a time
    without a time zone is local.

    Raise ValueError if the time can't be parsed.
    '''
    return datetime.datetime.fromisoformat(time).timestamp()


def format_time(time):
    '''
    Given a time as an ISO 8601 string, return it as a string in local time like "2026-10-31 17:40".
    Assume that a time without a time zone is already local, which is how Borg 1 reports times.

    Raise ValueError if the time can't be parsed.
    '''
    return datetime.datetime.fromisoformat(time).astimezone().strftime('%Y-%m-%d %H:%M')
