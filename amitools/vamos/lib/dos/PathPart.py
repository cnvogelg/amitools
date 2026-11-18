"""helpers for path operations"""

from amitools.vamos.log import log_dos

from .Error import DOSFALSE, DOSTRUE


def expand_progdir_path(ami_path, home_dir):
    """Expand '*' prefix (PROGDIR:) to the program's home directory.

    Args:
        ami_path: The Amiga path that may start with '*'
        home_dir: A lock object with ami_path attribute, or None

    Returns:
        The expanded path if ami_path starts with '*' and home_dir is set,
        otherwise returns ami_path unchanged.
    """
    if not str(ami_path).startswith("*") or home_dir is None:
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


def _file_part(path):
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


def _path_part(path):
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


def _split_name(name, separator, oldpos, size):
    """split off one part of a name at the given separator.

    Returns a tuple (next_pos, part). next_pos is the position after the
    separator to continue with the next part or -1 if the part was the
    last one. At most size - 1 characters are returned in part.
    """
    n = len(name)
    max_len = max(size - 1, 0)
    pos = oldpos
    part = []
    while pos < n and len(part) < max_len and ord(name[pos]) != separator:
        part.append(name[pos])
        pos += 1
    if pos < n and ord(name[pos]) == separator:
        return pos + 1, "".join(part)
    # a NUL separator matches the terminator at the end of the name
    if pos >= n and separator == 0:
        return pos + 1, "".join(part)
    return -1, "".join(part)


def _add_part(dirname, filename, size):
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


# ----- fd functions -----


def file_part(dos, ctx, addr):
    path = ctx.mem.r_cstr(addr)
    pos = _file_part(path)
    if pos < len(path):
        log_dos.info("FilePart: path='%s' -> result='%s'", path, path[pos:])
    else:
        log_dos.info("FilePart: path='%s' -> pos=NULL", path)
    return addr + pos


def path_part(dos, ctx, addr):
    path = ctx.mem.r_cstr(addr)
    pos = _path_part(path)
    if pos < len(path):
        log_dos.info("PathPart: path='%s' -> result='%s'", path, path[:pos])
    else:
        log_dos.info("PathPart: path='%s' -> pos=NULL", path)
    return addr + pos


def add_part(dos, ctx, dn_addr, fn_addr, size):
    dn = ctx.mem.r_cstr(dn_addr)
    fn = ctx.mem.r_cstr(fn_addr)
    np = _add_part(dn, fn, size)
    log_dos.info("AddPart: dn='%s' fn='%s' size=%d -> np='%s'", dn, fn, size, np)
    if np != None:
        ctx.mem.w_cstr(dn_addr, np)
        return DOSTRUE
    else:
        return DOSFALSE


def split_name(dos, ctx, name, separator, buf_ptr, oldpos, size):
    pos, part = _split_name(name, separator, oldpos, size)
    ctx.mem.w_cstr(buf_ptr, part)
    log_dos.info(
        "SplitName: name='%s' sep=%d oldpos=%d size=%d -> pos=%d part='%s'",
        name,
        separator,
        oldpos,
        size,
        pos,
        part,
    )
    return pos
