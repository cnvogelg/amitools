"""dos.library date conversion (RKRM AmigaDOS 3, "Convert a String to a Date
and Time" and "Comparing Dates").

``StrToDate`` fills ``dat_Stamp`` from the date/time strings in a
``DateTime`` structure. Vamos accepts the four DOS date layouts plus the
relative forms (``Today``/``Tomorrow``/``Yesterday`` and weekday names); a
missing string leaves the corresponding part of ``dat_Stamp`` untouched.
"""

import re
import time

from amitools.vamos.log import log_dos
from amitools.vamos.libstructs import DateStampStruct

from .AmiTime import sys_to_ami_time
from .Error import DOSFALSE, DOSTRUE

FORMAT_DOS = 0
FORMAT_INT = 1
FORMAT_USA = 2
FORMAT_CDN = 3
FORMAT_DEF = 4

DTF_SUBST = 1
DTF_FUTURE = 2

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
