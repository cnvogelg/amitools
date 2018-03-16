import datetime
import re


id_format = "([a-z.]+) (\d+)\.(\d)+ \((\d+)\.(\d+)\.(\d+)\)\r\n"


class LibInfo(object):

  def __init__(self, name, version, revision, pos_size, neg_size,
               id_string=None, date=None):
    """pass either a valid id_string or a date object"""
    self.name = name
    self.version = version
    self.revision = revision
    self.pos_size = pos_size
    self.neg_size = neg_size
    if id_string is None:
      if date is None:
        raise ValueError("both date and id_string is None!")
      self.id_string = self.generate_id_string(date)
      self.date = date
    else:
      self.id_string = id_string
      self.date = self.parse_id_string(id_string)

  def __str__(self):
    return "'%s' %d.%d +%d -%d (%d.%d.%d)" % (
        self.name,
        self.version, self.revision,
        self.pos_size, self.neg_size,
        self.date.day, self.date.month, self.date.year
    )

  def get_name(self):
    return self.name

  def get_version(self):
    return self.version

  def get_revision(self):
    return self.revision

  def get_pos_size(self):
    return self.pos_size

  def get_neg_size(self):
    return self.neg_size

  def get_id_string(self):
    return self.id_string

  def get_date(self):
    return self.date

  def generate_id_string(self, date):
    """use date and internals to create id string"""
    date_str = "%d.%d.%04d" % (date.day, date.month, date.year)
    id_str = "%s %d.%d (%s)\r\n" % (
        self.name, self.version, self.revision, date_str
    )
    return id_str

  def parse_id_string(self, id_str):
    """parse string and return date"""
    mo = re.match(id_format, id_str)
    if mo is None:
      raise ValueError("no valid id_string: " + id_str)
    groups = mo.groups()
    assert groups[0] == self.name
    assert int(groups[1]) == self.version
    assert int(groups[2]) == self.revision
    day = int(groups[3])
    mon = int(groups[4])
    year = int(groups[5])
    date = datetime.date(day=day, month=mon, year=year)
    self.date = date
    return date
