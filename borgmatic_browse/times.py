import datetime


def format_time(time):
    '''
    Given a time as an ISO 8601 string, return it as a string in local time like "2026-10-31 17:40".
    Assume that a time without a time zone is already local, which is how Borg 1 reports times.

    Raise ValueError if the time can't be parsed.
    '''
    return datetime.datetime.fromisoformat(time).astimezone().strftime('%Y-%m-%d %H:%M')
