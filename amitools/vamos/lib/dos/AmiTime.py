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
    # UNIX epoch to Amiga epoch (Jan 1 1978)
    AMIGA_EPOCH = 252460800

    asec = t - AMIGA_EPOCH
    whole = int(asec)
    frac  = asec - whole
    
    # days since 1978
    tday = whole // 86400
    rem  = whole % 86400
    
    # minutes since midnight
    tmin = rem // 60
    
    # seconds within the minute
    sec_in_min = rem % 60
    
    # ticks since the start of the minute
    tick = sec_in_min * 50 + int(frac * 50)

    return AmiTime(tday, tmin, tick)


def ami_to_sys_time(ami):
    seconds = ami.tick // 50.0  # ticks are 50th of a second
    seconds += ami.tmin * 60  # convert minutes to seconds
    seconds += (ami.tday + 2922) * 24 * 60 * 60
    return seconds
