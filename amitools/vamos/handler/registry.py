"""Handler type registry: map a handler type name to a factory.

A volume's ``?handler=<type>`` config option selects a factory by name. The
factory is called with the volume name, its host path (may be empty for
non-host handlers), the parsed volume config, and the shared host file
system, and returns a ready :class:`~amitools.vamos.handler.base.Handler`.

The default registry knows the ``hostfs`` type. Later ``ram``, ``nil``,
``console`` and ``packet`` types register here as well, so the DOS layer can
stay unaware of how a volume is implemented.
"""

from .filesys import HostFileSysHandler


class HandlerRegistry:
    """Registry of handler factories keyed by a lower-cased type name."""

    def __init__(self):
        self._factories = {}

    def add_type(self, type_name, factory):
        """register a factory under ``type_name`` (case-insensitive)"""
        self._factories[str(type_name).lower()] = factory
        return factory

    def get(self, type_name):
        return self._factories.get(str(type_name).lower())

    def get_all_types(self):
        return sorted(self._factories)

    def create(self, type_name, name, path, cfg, file_system):
        """create a handler of ``type_name`` or return None if unknown"""
        factory = self.get(type_name)
        if factory is None:
            return None
        return factory(name, path, cfg, file_system)


def hostfs_factory(name, path, cfg, file_system):
    """factory for a handler backed by a host directory tree"""
    return HostFileSysHandler(name, path, file_system=file_system)


def default_registry():
    """build the registry with the built-in handler types"""
    registry = HandlerRegistry()
    registry.add_type("hostfs", hostfs_factory)
    return registry
