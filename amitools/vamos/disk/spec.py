"""Per-image options on ``--disk`` (HANDLER.md step 25a).

A ``--disk`` value is ``IMAGE[?key=val,key=val]``::

    --disk floppy.adf?name=DF0
    --disk work.hdf?rw,bs=512
    --disk game.adz

The option list reuses the volume-spec syntax
(:meth:`amitools.vamos.path.Spec._parse_cfg`): the keys are separated by
commas, a bare key is ``True`` and ``key=on``/``key=false`` convert to
booleans. ``rw``/``ro`` pick the per-disk mode; every other key is handed to
the block-device factory. An unknown key is a config error, so a typo fails
loudly instead of being silently ignored. A ``?`` inside a path is therefore
not supported; such an image must be renamed.
"""

from dataclasses import dataclass, field
from typing import Mapping, Optional

from amitools.vamos.cfgcore import split_nest

# every option key a ``--disk`` entry may carry
KNOWN_KEYS = frozenset(("rw", "ro", "name", "type", "bs", "chs", "algo"))

# the subset only meaningful for a raw (non-RDB) image
RAW_KEYS = frozenset(("name", "type", "bs", "chs", "algo"))


def _parse_options(cfg_str):
    """parse a comma-separated ``key[=val]`` option list"""
    if not cfg_str:
        raise ValueError("empty disk options")
    options = {}
    for pair in split_nest(cfg_str, sep=","):
        kv = split_nest(pair, sep="=")
        n = len(kv)
        if n == 1:
            key, value = kv[0], True
        elif n == 2:
            key, value = kv
            lowered = value.lower()
            if lowered in ("true", "on", ""):
                value = True
            elif lowered in ("false", "off"):
                value = False
        else:
            raise ValueError("not a key value pair in disk options: %s" % pair)
        if not key:
            raise ValueError("invalid key in disk options")
        options[key] = value
    return options


@dataclass(frozen=True)
class DiskSpec:
    """a ``--disk`` value split into the image path and its options"""

    path: str
    options: Mapping[str, object] = field(default_factory=dict)
    read_only: Optional[bool] = None

    @classmethod
    def parse(cls, spec):
        text = str(spec)
        pos = text.find("?")
        if pos < 0:
            path = text
            options = {}
        else:
            path = text[:pos]
            options = _parse_options(text[pos + 1 :])
        if not path:
            raise ValueError("no image path in disk spec")
        unknown = set(options) - KNOWN_KEYS
        if unknown:
            raise ValueError("unknown disk option(s): %s" % ", ".join(sorted(unknown)))
        read_only = None
        has_rw = "rw" in options
        has_ro = "ro" in options
        if has_rw and has_ro:
            raise ValueError("both rw and ro given in disk spec")
        if has_rw:
            read_only = not bool(options.pop("rw"))
        elif has_ro:
            read_only = bool(options.pop("ro"))
        return cls(path, options, read_only)

    def factory_options(self):
        """the options handed to the block-device factory (no mode keys)"""
        return dict(self.options)
