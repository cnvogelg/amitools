"""helpers for path operations"""


def file_part(path):
    pos = path.rfind("/")
    if pos != -1:
        pos += 1
    else:
        pos = path.find(":")
        if pos == -1:
            pos = 0
        else:
            pos += 1
    n = len(path)
    if pos >= n:
        pos = n
    return pos


def path_part(path):
    pos = path.rfind("/")
    if pos != -1:
        return pos
    else:
        pos = path.find(":")
        if pos == -1:
            pos = 0
        else:
            pos += 1
    n = len(path)
    if pos >= n:
        pos = n
    return pos


def add_part(dirname, filename, size):
    if len(dirname) == 0:
        return filename
    if len(filename) == 0:
        return dirname
    # does filename have a ':' ?
    pos = filename.find(":")
    if pos > 0:
        return filename
    elif pos == 0:
        # does dir have a ':'?
        dpos = dirname.find(":")
        if dpos >= 0:
            return dirname[0:dpos] + filename
        else:
            return filename
    else:
        # no colon in filenam
        if dirname[-1] in (":", "/"):
            return dirname + filename
        else:
            return dirname + "/" + filename
