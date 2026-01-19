"""helpers for path operations"""


def expand_progdir_path(ami_path, home_dir):
    """Expand '*' prefix (PROGDIR:) to the program's home directory.

    Args:
        ami_path: The Amiga path that may start with '*'
        home_dir: A lock object with ami_path attribute, or None

    Returns:
        The expanded path if ami_path starts with '*' and home_dir is set,
        otherwise returns ami_path unchanged.
    """
    if not ami_path.startswith("*") or home_dir is None:
        return ami_path

    home_path = home_dir.ami_path
    # Normalize base path for joining
    if home_path.endswith(":"):
        base_path = home_path
    elif home_path.endswith("/"):
        base_path = home_path[:-1]
    else:
        base_path = home_path

    rest = ami_path[1:]  # Remove the '*'
    if rest.startswith("/"):
        # '*/' means go up from home dir - join base with rest (which starts with /)
        return base_path + rest
    elif rest == "":
        # Just '*' means the home directory itself
        return home_path
    else:
        # '*name' means name relative to home dir
        if base_path.endswith(":"):
            return base_path + rest
        else:
            return base_path + "/" + rest


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
