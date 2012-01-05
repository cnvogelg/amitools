import time

ts_empty_string = "--.--.---- --:--:--.--"

class TimeStamp:
  def __init__(self, days, mins, ticks):
    self.days = days
    self.mins = mins
    self.ticks = ticks
    self.secs = days * 24 * 60 * 60 + mins * 60 + (ticks / 50)
    self.sub_secs = (ticks % 50)
  
  def __str__(self):
    t = time.gmtime(self.secs)
    ts = time.strftime("%d.%m.%Y %H:%M:%S",t)
    return "%s t%02d" % (ts, self.sub_secs)
    
  def get_secsf(self):
    return self.secs + self.sub_secs / 50.0
  
  def get_secs(self):
    return self.secs
    
def ts_create_from_secs(secs):
  ticks = int(secs * 50.0)
  mins = ticks / (50 * 60)
  ticks = ticks % (50 * 60)
  days = mins / (60 * 24)
  mins = mins % (60 * 24)
  return TimeStamp(days, mins, ticks)
  
