import time

class TimeStamp:
  def __init__(self, days, mins, ticks):
    self.days = days
    self.mins = mins
    self.ticks = ticks
    self.secs = days * 24 * 60 * 60 + mins * 60 + (ticks / 50)
    self.msecs = (ticks % 50) * 1000 / 50
  
  def __str__(self):
    t = time.gmtime(self.secs)
    ts = time.strftime("%d.%m.%Y %H:%M:%S",t)
    return "%s.%03d" % (ts, self.msecs)