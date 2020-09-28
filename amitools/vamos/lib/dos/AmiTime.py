class AmiTime:
    def __init__(self, tday, tmin, tick):
        self.tday = tday
        self.tmin = tmin
        self.tick = tick
        # 2922 is the number of days between Jan-1 1970 and Jan-1 1978
        # Note that Amiga uses an epoch of Jan-1 1978 whereas Unix
        # uses an epoch of Jan-1 1970.

    def __str__(self):
        return "[days=%d, min=%04d, tick=%04d]" % (self.tday, self.tmin, self.tick)

    def to_sys_time(self):
        return (self.tick // 50) + self.tmin * 60 + (self.tday + 2922) * (60 * 60 * 24)


def sys_to_ami_time(t):
    ts = int(t)  # entire seconds since epoch
    tmil = t - ts  # milliseconds
    tmin = ts // 60  # entire minutes
    ts = ts % 60  # seconds
    tday = tmin // (60 * 24)  # days
    tmin = tmin % (60 * 24)  # minutes
    ts += tmil  # seconds including milliseconds
    tick = int(ts * 50)  # 1/50 sec (tsk,tsk,tsk, no, *200 is not right here!)
    return AmiTime(tday - 2922, tmin, tick)


def ami_to_sys_time(ami):
    seconds = ami.tick // 50.0  # ticks are 50th of a second
    seconds += ami.tmin * 60  # convert minutes to seconds
    seconds += (ami.tday + 2922) * 24 * 60 * 60
    return seconds
