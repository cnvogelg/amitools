import re

tag = b"$VER:"


def find(data):
    off = data.find(tag)
    if off == -1:
        return None
    start = off + len(tag)
    end = start
    size = len(data)
    while end < size:
        if data[end] == chr(0):
            break
        end += 1
    return data[start:end].strip()


def get_version(data):
    m = re.search(r"\s(\d+)\.(\d+)\s", data.decode("latin-1"))
    if m is None:
        return None
    else:
        return (int(m.group(1)), int(m.group(2)))
