import datetime
from amitools.vamos.libcore import LibInfo


def libcore_info_date_test():
    date = datetime.date(day=24, month=12, year=2008)
    info = LibInfo("test.library", 42, 3, date, 36, 42)
    txt = str(info)
    assert txt == "'test.library' 42.3 +36 -42 (24.12.2008)"
    assert info.get_id_string() == "test.library 42.3 (24.12.2008)\r\n"
    assert info.get_date() == date


def libcore_info_idstr_test():
    id_string = "test.library 42.3 (24.12.2008)\r\n"
    info = LibInfo.parse_id_string(id_string, 36, 42)
    txt = str(info)
    assert txt == "'test.library' 42.3 +36 -42 (24.12.2008)"
    assert info.get_id_string() == id_string
    date = datetime.date(day=24, month=12, year=2008)
    assert info.get_date() == date
    date2 = LibInfo.extract_date(id_string)
    assert info.get_date() == date2
    info2 = LibInfo.parse_id_string(id_string, 36, 42)
    assert info == info2
