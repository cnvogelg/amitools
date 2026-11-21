"""Validated configuration of a ``?handler=native`` volume (HANDLER.md 24a).

A native volume is written as a path-less spec whose ``?`` options name the
handler binary and the ``--disk`` partition it mounts::

    WORK:?handler=native,binary=/path/pfs3aio,device=DH0,globvec=-1

The options are validated once, when the registry factory builds the detached
handler, so a typo fails loudly instead of being silently ignored.
"""

from ..base import ERROR_BAD_NUMBER, HandlerError
from . import startup

# every key a ``?handler=native`` volume may carry. ``handler`` is always
# present in a volume config (it selects this type) and is accepted but unused.
KNOWN_KEYS = frozenset(
    (
        "handler",
        "binary",
        "handler_binary",
        "device",
        "unit",
        "part",
        "partition",
        "globvec",
        "stack",
        "priority",
    )
)

# default handler process stack (bytes) and exec task priority
DEFAULT_STACK = 4096
DEFAULT_PRIORITY = 0


def _parse_int(name, value, default):
    """parse a numeric option (``None`` -> ``default``) or raise"""
    if value is None:
        return default
    # a bare ``?key`` parses as a bool; a number is required here
    if isinstance(value, bool):
        raise HandlerError(ERROR_BAD_NUMBER, "native option '%s' needs a number" % name)
    if isinstance(value, int):
        return value
    try:
        return int(str(value), 0)
    except ValueError:
        raise HandlerError(
            ERROR_BAD_NUMBER,
            "native option '%s' is not a number: %r" % (name, value),
        ) from None


class NativeConfig:
    """the validated options of a ``?handler=native`` volume"""

    def __init__(self, cfg=None):
        cfg = dict(cfg or {})
        unknown = sorted(set(cfg) - KNOWN_KEYS)
        if unknown:
            raise HandlerError(
                ERROR_BAD_NUMBER,
                "unknown native handler option(s): %s" % ", ".join(unknown),
            )
        self.raw = cfg
        # the handler seglist source (host path, Amiga path or RDB driver)
        self.binary = cfg.get("binary") or cfg.get("handler_binary")
        # the block device: a ``--disk`` device node name and/or partition
        self.device = cfg.get("device")
        self.unit = _parse_int("unit", cfg.get("unit"), None)
        part = cfg.get("part")
        if part is None:
            part = cfg.get("partition")
        self.part = part
        # ``dol_GlobVec`` marker: -1 for a C handler, -2 for an assembler one
        self.globvec = _parse_int("globvec", cfg.get("globvec"), startup.GLOBVEC_C)
        self.stack = _parse_int("stack", cfg.get("stack"), DEFAULT_STACK)
        self.priority = _parse_int("priority", cfg.get("priority"), DEFAULT_PRIORITY)

    def __repr__(self):
        return "NativeConfig(binary=%r, device=%r, unit=%r, part=%r, globvec=%r)" % (
            self.binary,
            self.device,
            self.unit,
            self.part,
            self.globvec,
        )
