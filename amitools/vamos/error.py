class VamosError(Exception):
    def __str__(self):
        return "VamosError"


class NestedCPURunError(VamosError):
    def __init__(self, pc, error):
        self.pc = pc
        self.error = error

    def __str__(self):
        tname = self.error.__class__.__name__
        return "Nested CPU Run Failed: pc=%06x: %s: %s" % (self.pc, tname, self.error)


class OutOfAmigaMemoryError(VamosError):
    def __init__(self, alloc, size):
        self._alloc = alloc
        self._size = size

    def __str__(self):
        return "Out of Amiga Memory: %s size=%s" % (str(self._alloc), self._size)


class UnsupportedFeatureError(VamosError):
    def __init__(self, what):
        self._what = what

    def __str__(self):
        return "Unupported vamos Feature: %s" % self._what


class AmigaDeviceNotFoundError(VamosError):
    def __init__(self, dev):
        self._dev = dev

    def __str__(self):
        return "Amiga volume not found: %s" % self._dev


class VersionMismatchError(VamosError):
    def __init__(self, what, got, want):
        self._what = what
        self._got = got
        self._want = want

    def __str__(self):
        return "Version Mismatch: %s got=%d want=%d" % (
            self._what,
            self._got,
            self._want,
        )


class VamosInternalError(VamosError):
    def __init__(self, what):
        self._what = what

    def __str__(self):
        return "Internal Vamos Error: %s" % self._what
