import datetime

import pytz
from iso8601 import iso8601


def get_utc_time(seconds):
    return datetime.datetime.utcfromtimestamp(seconds).replace(tzinfo=pytz.timezone("UTC"))


def get_time_since_epoch(utc_datetime):
    begin_epoch = get_utc_time(0)
    timestamp = (utc_datetime - begin_epoch).total_seconds()
    return timestamp


def time_to_seconds(str_datetime_utc):
    """
    Converts time in utc format 2016-06-27T14:26:30.000+00:00 to seconds
    """
    parsed_datetime = iso8601.parse_date(str_datetime_utc)
    return get_time_since_epoch(parsed_datetime)
