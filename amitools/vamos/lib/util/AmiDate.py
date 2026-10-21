import datetime

from amitools.vamos.libstructs import ClockDataStruct

# when Amiga time began...
amiga_epoch = datetime.datetime(1978, 1, 1, 0, 0, 0)


def write_clock_data(dt, mem, data_ptr):
    """convert Python datetime struct to Amiga ClockData stored at pointer"""
    data = ClockDataStruct(mem, data_ptr)
    # fill in date struct
    data.sec.val = dt.second
    data.min.val = dt.minute
    data.hour.val = dt.hour
    data.mday.val = dt.day
    data.month.val = dt.month
    data.year.val = dt.year
    # Amiga weekdays are Sunday-based, while Python uses Monday=0.
    data.wday.val = (dt.weekday() + 1) % 7


def read_clock_data(mem, data_ptr):
    """read Amiga ClockData and return corresponding Python datetime
    return None if data is invalid
    """
    data = ClockDataStruct(mem, data_ptr)
    # read date struct
    sec = data.sec.val
    minute = data.min.val
    hour = data.hour.val
    mday = data.mday.val
    month = data.month.val
    year = data.year.val

    try:
        dt = datetime.datetime(year, month, mday, hour, minute, sec)
        if year < 1978:
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
