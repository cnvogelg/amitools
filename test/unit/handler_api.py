"""Guard test: the handler API stays a 1:1 map of AmigaDOS handler packets.

Every public action method of :class:`Handler` must correspond to exactly one
``DosAction``. This keeps the boundary a faithful model of the ``ACTION_*``
packets so a future ``PacketHandler`` can translate a method call into the
matching ``DosPacket``.
"""

import inspect

from amitools.vamos.handler import Handler
from amitools.vamos.handler.base import ACTION_METHODS
from amitools.vamos.lib.dos.action import DosAction

# lifecycle methods that are not AmigaDOS actions and have no packet
NON_ACTION_METHODS = {"shutdown"}


def handler_api_action_map_test():
    public = set()
    for name, _ in inspect.getmembers(Handler, predicate=inspect.isfunction):
        if name.startswith("_"):
            continue
        public.add(name)
    action_methods = public - NON_ACTION_METHODS
    unmapped = action_methods - set(ACTION_METHODS)
    assert not unmapped, f"handler methods without a packet: {sorted(unmapped)}"
    # every mapped method exists on the handler and maps to a real action
    for name, dos_action in ACTION_METHODS.items():
        assert hasattr(Handler, name), name
        assert isinstance(dos_action, DosAction), name


def handler_api_no_packetless_methods_test():
    # the packet-less DOS concepts must not be part of the handler API
    for name in ("tell", "is_interactive"):
        assert name not in ACTION_METHODS
        assert not hasattr(Handler, name)
