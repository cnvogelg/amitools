class AmiTime:
  def __init__(self, tday, tmin, tick):
    self.tday = tday
    self.tmin = tmin
    self.tick = tick
  def __str__(self):
    return "[days=%d, min=%04d, tick=%04d]" % (self.tday, self.tmin, self.tick)
  
  def to_sys_time(self):
    return (self.tick / 50) + self.tmin * 60 + self.tday * (60*60*24)

def sys_to_ami_time(t):
  ts = int(t)
  tmil = t - ts
  tmin = ts / 60
  ts = ts % 60
  tday = tmin / (60*24)
  tmin = tmin % (60*24)
  ts += tmil
  tick = int(ts * 200) # 1/50 sec
  return AmiTime(tday, tmin, tick)
