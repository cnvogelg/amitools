import datetime

from amitools.vamos.astructs import AccessStruct
from amitools.vamos.libstructs import ClockDataStruct


# when Amiga time began...
amiga_epoch = datetime.datetime(1978, 1, 1, 0, 0, 0)


def write_clock_data(dt, mem, data_ptr):
    """convert Python datetime struct to Amiga ClockData stored at pointer"""
    data = AccessStruct(mem, ClockDataStruct, struct_addr=data_ptr)
    # fill in date struct
    data.w_s("sec", dt.second)
    data.w_s("min", dt.minute)
    data.w_s("hour", dt.hour)
    data.w_s("mday", dt.day)
    data.w_s("month", dt.month)
    data.w_s("year", dt.year)
    data.w_s("wday", dt.weekday())


def read_clock_data(mem, data_ptr):
    """read Amiga ClockData and return corresponding Python datetime
    return None if data is invalid
    """
    data = AccessStruct(mem, ClockDataStruct, struct_addr=data_ptr)
    # read date struct
    sec = data.r_s("sec")
    minute = data.r_s("min")
    hour = data.r_s("hour")
    mday = data.r_s("mday")
    month = data.r_s("month")
    year = data.r_s("year")
    wday = data.r_s("wday")

    try:
        dt = datetime.datetime(year, month, mday, hour, minute, sec)
        if year < 1978:
            return None
        if dt.weekday() != wday:
            return None
        return dt
    except ValueError:
        return None


def date_at(seconds):
    """return a Python datetime representing given seconds after epoch"""
    return amiga_epoch + datetime.timedelta(seconds=seconds)


def seconds_since(dt):
    delta = dt - amiga_epoch
    return int(delta.total_seconds())
