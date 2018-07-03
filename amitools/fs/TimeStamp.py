from __future__ import absolute_import
from __future__ import print_function

import time

ts_empty_string = "--.--.---- --:--:--.--"
ts_format = "%d.%m.%Y %H:%M:%S"

# Python time functions will provide seconds from 'epoch',
# which is 1970, but Amiga specs say that 1978 is the base year.
amiga_epoch = time.mktime(time.strptime("01.01.1978 00:00:00", ts_format))

class TimeStamp:
  def __init__(self, days=0, mins=0, ticks=0):
    self.days = days
    self.mins = mins
    self.ticks = ticks
    self.secs = days * 24 * 60 * 60 + mins * 60 + (ticks / 50)
    self.sub_secs = (ticks % 50)
  
  def __str__(self):
    t = time.localtime(self.secs + amiga_epoch)
    ts = time.strftime(ts_format, t)
    return "%s t%02d" % (ts, self.sub_secs)
    
  def get_secsf(self):
    return self.secs + self.sub_secs / 50.0
  
  def get_secs(self):
    return self.secs
  
  def from_secs(self, secs):
    secs = int(secs - amiga_epoch)
    ticks = secs * 50
    mins = ticks / (50 * 60)
    self.ticks = ticks % (50 * 60)
    self.days = mins / (60 * 24)
    self.mins = mins % (60 * 24)
    self.secs = secs
    self.sub_secs = 0
  
  def parse(self, s):
    # check for ticks
    s = s.strip()
    ticks = 0
    if len(s) > 3:
      t = s[-3:]
      if t[0] == 't' and t[1:].isdigit():
        ticks = int(t[1:])
        s = s[:-4]
    # parse normal time
    try:
      ts = time.strptime(s, ts_format)
      secs = int(time.mktime(ts))
      self.from_secs(secs)
      self.sub_secs = ticks
      self.ticks += ticks
      return True
    except ValueError:
      return False
  
if __name__ == '__main__':
  ts = TimeStamp()
  ts.from_secs(123)
  ts2 = TimeStamp(days=ts.days, mins=ts.mins, ticks=ts.ticks)
  if ts2.get_secs() != 123:
    print("FAIL")
  
  ts = TimeStamp()
  s = "05.01.2012 21:47:34 t40"
  ts.parse(s)
  txt = str(ts)
  if s != txt:
    print("FAIL")
