import datetime
import re


date_format = r".*\((\d+)\.(\d+)\.(\d+)\)"
id_format = r"([a-z.]+) (\d+)\.(\d)+ \((\d+)\.(\d+)\.(\d+)\)\r\n"


class LibInfo(object):
    def __init__(self, name, version, revision, date, pos_size=0, neg_size=0):
        """pass either a valid id_string or a date object"""
        self.name = name
        self.version = version
        self.revision = revision
        self.date = date
        self.pos_size = pos_size
        self.neg_size = neg_size
        self.id_string = self._generate_id_string()

    def __str__(self):
        return "'%s' %d.%d +%d -%d (%d.%d.%d)" % (
            self.name,
            self.version,
            self.revision,
            self.pos_size,
            self.neg_size,
            self.date.day,
            self.date.month,
            self.date.year,
        )

    def __eq__(self, other):
        return (
            self.name == other.name
            and self.version == other.version
            and self.revision == other.revision
            and self.date == other.date
            and self.pos_size == other.pos_size
            and self.neg_size == other.neg_size
        )

    def get_name(self):
        return self.name

    def get_name_cstr_size(self):
        return len(self.name) + 1

    def get_version(self):
        return self.version

    def get_revision(self):
        return self.revision

    def get_pos_size(self):
        return self.pos_size

    def get_neg_size(self):
        return self.neg_size

    def get_total_size(self):
        return self.pos_size + self.neg_size

    def get_id_string(self):
        return self.id_string

    def get_id_string_cstr_size(self):
        return len(self.id_string) + 1

    def get_date(self):
        return self.date

    def _generate_id_string(self):
        date = self.date
        date_str = "%d.%d.%04d" % (date.day, date.month, date.year)
        id_str = "%s %d.%d (%s)\r\n" % (
            self.name,
            self.version,
            self.revision,
            date_str,
        )
        return id_str

    @staticmethod
    def extract_date(id_str):
        """extract the data from an id_string"""
        mo = re.match(date_format, id_str)
        if mo is None:
            return None
        groups = mo.groups()
        day = int(groups[0])
        mon = int(groups[1])
        year = int(groups[2])
        date = datetime.date(year, mon, day)
        return date

    @staticmethod
    def parse_id_string(id_str, pos_size, neg_size):
        """parse string and return date"""
        mo = re.match(id_format, id_str)
        if mo is None:
            return None
        groups = mo.groups()
        name = groups[0]
        version = int(groups[1])
        revision = int(groups[2])
        day = int(groups[3])
        mon = int(groups[4])
        year = int(groups[5])
        date = datetime.date(year, mon, day)
        return LibInfo(name, version, revision, date, pos_size, neg_size)
