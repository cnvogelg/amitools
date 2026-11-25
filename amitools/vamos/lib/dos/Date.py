"""dos.library date conversion (RKRM AmigaDOS 3, "Convert a String to a Date
and Time" and "Comparing Dates").

``StrToDate`` fills ``dat_Stamp`` from the date/time strings in a
``DateTime`` structure. Vamos accepts the four DOS date layouts plus the
relative forms (``Today``/``Tomorrow``/``Yesterday`` and weekday names); a
missing string leaves the corresponding part of ``dat_Stamp`` untouched.
"""

import re
import time

from amitools.vamos.astructs import LONG
from amitools.vamos.libstructs import DateStampStruct, DateTimeStruct
from amitools.vamos.log import log_dos

from .AmiTime import AmiTime, sys_to_ami_time
from .Error import DOSFALSE, DOSTRUE, dos_error_strings

FORMAT_DOS = 0
FORMAT_INT = 1
FORMAT_USA = 2
FORMAT_CDN = 3
FORMAT_DEF = 4

DTF_SUBST = 1
DTF_FUTURE = 2

DOS_MONTH_NAMES = (
    "Jan",
    "Feb",
    "Mar",
    "Apr",
    "May",
    "Jun",
    "Jul",
    "Aug",
    "Sep",
    "Oct",
    "Nov",
    "Dec",
)
SUBSTITUTED_DATES = ("Future", "Tomorrow", "Today", "Yesterday")

_MONTHS = {
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
}

# AmigaDOS epoch: 1978-01-01 was a Sunday
_WEEKDAYS = {
    "sunday": 0,
    "monday": 1,
    "tuesday": 2,
    "wednesday": 3,
    "thursday": 4,
    "friday": 5,
    "saturday": 6,
}
_EPOCH_WEEKDAY = 0


def _year_value(year):
    if year < 100:
        # AmigaDOS ROM rule: 78..99 -> 19xx, 00..45 -> 20xx
        if 78 <= year <= 99:
            return 1900 + year
        if 0 <= year <= 45:
            return 2000 + year
        return None
    if 1978 <= year <= 9999:
        return year
    return None


def _days_in_month(year, month):
    if month == 2:
        leap = year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)
        return 29 if leap else 28
    return 30 if month in (4, 6, 9, 11) else 31


def _days_since_epoch(year, month, day):
    """days between 1978-01-01 and the given date (may be negative)"""
    # days from 1970-01-01 (civil_from_days inverse)
    y = year - (1 if month <= 2 else 0)
    era = (y if y >= 0 else y - 399) // 400
    yoe = y - era * 400
    doy = (153 * (month + (-3 if month > 2 else 9)) + 2) // 5 + day - 1
    doe = yoe * 365 + yoe // 4 - yoe // 100 + doy
    days = era * 146097 + doe - 719468
    # 1978-01-01 is 2922 days after the Unix epoch
    return days - 2922


def _parse_numeric_date(text, date_format):
    parts = re.split(r"[-/.]", text)
    if len(parts) != 3:
        return None

    def to_int(txt):
        try:
            return int(txt)
        except ValueError:
            return None

    if date_format == FORMAT_INT:
        year, month, day = (to_int(x) for x in parts)
    elif date_format == FORMAT_USA:
        month, day, year = (to_int(x) for x in parts)
    else:  # FORMAT_DOS and FORMAT_CDN
        day, month, year = (to_int(x) for x in parts)
        if date_format == FORMAT_DOS and month is None:
            month = _MONTHS.get(parts[1].lower())
    if year is None or month is None or day is None:
        return None
    year = _year_value(year)
    if year is None:
        return None
    if not 1 <= month <= 12:
        return None
    if not 1 <= day <= _days_in_month(year, month):
        return None
    return _days_since_epoch(year, month, day)


def _parse_relative(text, today, future):
    low = text.lower()
    if low == "today":
        return today
    if low == "tomorrow":
        return today + 1
    if low == "yesterday":
        return today - 1
    weekday = _WEEKDAYS.get(low)
    if weekday is None:
        return None
    delta = (weekday - ((today + _EPOCH_WEEKDAY) % 7)) % 7
    if future:
        return today + delta
    # past weekday (today counts as this week's weekday)
    delta = delta - 7 if delta else 0
    return today + delta


def _parse_date(text, date_format, today, future):
    text = text.strip()
    if not text:
        return None
    relative = _parse_relative(text, today, future)
    if relative is not None:
        return relative
    if date_format == FORMAT_DEF:
        # no locale support: accept any of the numeric layouts
        for fmt in (FORMAT_DOS, FORMAT_USA, FORMAT_INT, FORMAT_CDN):
            days = _parse_numeric_date(text, fmt)
            if days is not None:
                return days
        return None
    return _parse_numeric_date(text, date_format)


def _parse_time(text):
    match = re.match(r"^\s*(\d{1,2}):(\d{1,2})(?::(\d{1,2}))?\s*$", text)
    if not match:
        return None
    hour = int(match.group(1))
    minute = int(match.group(2))
    second = int(match.group(3) or 0)
    if hour > 23 or minute > 59 or second > 59:
        return None
    return hour, minute, second


def str_to_date(ctx, date_time):
    """StrToDate(): return DOSTRUE on success, DOSFALSE on bad input"""
    stamp = date_time.dat_Stamp
    date_format = date_time.dat_Format.val
    flags = date_time.dat_Flags.val

    date_ptr = date_time.dat_StrDate.aptr
    time_ptr = date_time.dat_StrTime.aptr
    date_str = ctx.mem.r_cstr(date_ptr) if date_ptr else None
    time_str = ctx.mem.r_cstr(time_ptr) if time_ptr else None

    days = None
    time_parts = None
    if date_str is not None:
        now = sys_to_ami_time(time.time())
        days = _parse_date(date_str, date_format, now.tday, flags & DTF_FUTURE)
        if days is None:
            log_dos.info("StrToDate: cannot parse date '%s'", date_str)
            return DOSFALSE

    if time_str is not None:
        parsed = _parse_time(time_str)
        if parsed is None:
            log_dos.info("StrToDate: cannot parse time '%s'", time_str)
            return DOSFALSE
        hour, minute, second = parsed
        time_parts = (hour * 60 + minute, second * 50)

    # only write the stamp once both strings were parsed
    if days is not None:
        stamp.ds_Days.val = days
    if time_parts is not None:
        stamp.ds_Minute.val, stamp.ds_Tick.val = time_parts

    log_dos.info(
        "StrToDate: date=%r time=%r -> days=%d minute=%d tick=%d",
        date_str,
        time_str,
        stamp.ds_Days.val,
        stamp.ds_Minute.val,
        stamp.ds_Tick.val,
    )
    return DOSTRUE


def compare_dates(date1_ptr, date2_ptr, mem):
    """CompareDates(): negative if date1 is later, positive if date2 is later"""
    date1 = DateStampStruct(mem, date1_ptr)
    date2 = DateStampStruct(mem, date2_ptr)
    stamp1 = (date1.ds_Days.val, date1.ds_Minute.val, date1.ds_Tick.val)
    stamp2 = (date2.ds_Days.val, date2.ds_Minute.val, date2.ds_Tick.val)
    if stamp1 > stamp2:
        return -1
    if stamp1 < stamp2:
        return 1
    return 0


# ----- fd functions -----


def str_to_date_ptr(dos, ctx, date_time_ptr):
    """StrToDate(): build the DateTime view and convert its strings"""
    dt = DateTimeStruct(ctx.mem, date_time_ptr)
    return str_to_date(ctx, dt)


def compare_dates_values(dos, ctx, date1, date2):
    """CompareDates(): compare two DateStamp BPTRs"""
    result = compare_dates(date1, date2, ctx.mem)
    log_dos.info("CompareDates(%06x, %06x) -> %d", date1, date2, result)
    return result


def date_stamp(dos, ctx, ds_ptr):
    ds = DateStampStruct(ctx.mem, ds_ptr)
    t = time.time()
    at = sys_to_ami_time(t)
    log_dos.info("DateStamp: ptr=%06x sys_time=%d time=%s", ds_ptr, t, at)
    ds.ds_Days.val = at.tday
    ds.ds_Minute.val = at.tmin
    ds.ds_Tick.val = at.tick
    return ds_ptr


def _date_to_str(ctx, dt):
    """format the date/time in ``dt`` into its day/date/time strings"""
    dt_ptr = dt.addr
    ds_day = dt.dat_Stamp.ds_Days.val
    ds_min = dt.dat_Stamp.ds_Minute.val
    ds_tick = dt.dat_Stamp.ds_Tick.val
    date_format = dt.dat_Format.val
    flags = dt.dat_Flags.val
    str_day_ptr = dt.dat_StrDay.aptr
    str_date_ptr = dt.dat_StrDate.aptr
    str_time_ptr = dt.dat_StrTime.aptr
    at = AmiTime(ds_day, ds_min, ds_tick)
    st = at.to_sys_time()
    log_dos.info(
        "DateToStr: ptr=%06x format=%x flags=%x day_ptr=%06x "
        "date_ptr=%06x time_ptr=%06x %s => sys_time=%d",
        dt_ptr,
        format,
        flags,
        str_day_ptr,
        str_date_ptr,
        str_time_ptr,
        at,
        st,
    )
    t = time.gmtime(st)
    day_str = time.strftime("%A", t)
    year = t.tm_year % 100
    if date_format == FORMAT_INT:
        date_str = "%02d-%02d-%02d" % (year, t.tm_mon, t.tm_mday)
    elif date_format == FORMAT_USA:
        date_str = "%02d-%02d-%02d" % (t.tm_mon, t.tm_mday, year)
    elif date_format == FORMAT_CDN:
        date_str = "%02d-%02d-%02d" % (t.tm_mday, t.tm_mon, year)
    elif date_format == FORMAT_DEF:
        date_str = time.strftime("%x", t)
    else:
        date_str = "%02d-%s-%02d" % (
            t.tm_mday,
            DOS_MONTH_NAMES[t.tm_mon - 1],
            year,
        )
    if flags & DTF_SUBST:
        days_since = sys_to_ami_time(time.time()).tday - ds_day
        if days_since <= 7:
            if -1 <= days_since <= 1:
                date_str = SUBSTITUTED_DATES[days_since + 2]
            elif days_since < -1:
                date_str = "Future"
            else:
                date_str = day_str
    time_str = time.strftime("%H:%M:%S", t)
    log_dos.info(
        "DateToStr: result day='%s' date='%s' time='%s'",
        day_str,
        date_str,
        time_str,
    )
    if str_day_ptr != 0:
        ctx.mem.w_cstr(str_day_ptr, day_str)
    if str_date_ptr != 0:
        ctx.mem.w_cstr(str_date_ptr, date_str)
    if str_time_ptr != 0:
        ctx.mem.w_cstr(str_time_ptr, time_str)
    return DOSTRUE


def date_to_str(dos, ctx, dt_ptr):
    dt = DateTimeStruct(ctx.mem, dt_ptr)
    return _date_to_str(ctx, dt)


def dos_get_string(dos, ctx, errno):
    if errno >= 0x80000000:
        errno = errno - 0x100000000
    if errno in dos_error_strings:
        if errno in dos.errstrings:
            return dos.errstrings[errno]
        dos.errstrings[errno] = dos._alloc_mem(
            "Error %d" % errno, len(dos_error_strings[errno]) + 1
        )
        ctx.mem.w_cstr(dos.errstrings[errno], dos_error_strings[errno])
        return dos.errstrings[errno]
    else:
        return 0


class DateMixin:
    """dos.library fd methods (HANDLER.md step 22m)."""

    def DateStamp(self, ctx, ds_ptr):
        return date_stamp(self, ctx, ds_ptr)

    def DateToStr(self, ctx, dt_ptr):
        return date_to_str(self, ctx, dt_ptr)

    def DosGetString(self, ctx, errno):
        return dos_get_string(self, ctx, errno)

    def CompareDates(self, ctx, date1: LONG, date2: LONG):
        return compare_dates_values(self, ctx, date1.val, date2.val)

    def StrToDate(self, ctx, datetime: LONG):
        return str_to_date_ptr(self, ctx, datetime.val)
