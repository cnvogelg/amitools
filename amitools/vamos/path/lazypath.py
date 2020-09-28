from .amipath import AmiPath, AmiPathError


class LazyPath(object):
    def __init__(self, path, path_resolver=None):
        self.path_resolver = path_resolver
        self.set(path)

    def __eq__(self, other):
        if type(other) is str:
            return str(self) == other
        elif isinstance(other, AmiPath):
            return self.res_path == other
        elif not isinstance(other, LazyPath):
            return NotImplemented
        return self.path == other.path and self.res_path == other.res_path

    def __ne__(self, other):
        if type(other) is str:
            return str(self) != other
        elif isinstance(other, AmiPath):
            return self.res_path != other
        elif not isinstance(other, LazyPath):
            return NotImplemented
        return self.path != other.path or self.res_path != other.res_path

    def __repr__(self):
        return "LazyPath(path=%s, resolved_path=%s)" % (self.path, self.res_path)

    def __str__(self):
        if self.res_path:
            return str(self.res_path)
        else:
            return str(self.path) + "(!)"

    def set_path_resolver(self, path_resolver):
        self.path_resolver = path_resolver
        self.res_path = None

    def get_path_resolver(self):
        return self.path_resolver

    def get_resolved(self):
        if not self.res_path:
            self.resolve()
        return self.res_path

    def set(self, path):
        if type(path) is str:
            path = AmiPath(path)
        elif not isinstance(path, AmiPath):
            raise ValueError("path is not an AmiPath!")
        self.path = path
        self.res_path = None

    def get(self):
        return self.path

    def is_resolved(self):
        return self.res_path is not None

    def resolve(self):
        self.res_path = None
        if self.path_resolver:
            self.res_path = self.path_resolver(self.path)
        else:
            self.res_path = self.path


class LazyPathList(object):
    def __init__(self, paths=None, path_resolver=None):
        self.paths = []
        self.path_resolver = path_resolver
        self.set(paths)

    def __eq__(self, other):
        if not isinstance(other, LazyPathList):
            return NotImplemented
        return self.paths == other.paths

    def __ne__(self, other):
        if not isinstance(other, LazyPathList):
            return NotImplemented
        return self.paths != other.paths

    def __repr__(self):
        return "LazyPathList(paths=%r)" % self.paths

    def __str__(self):
        return "[%s]" % ",".join(map(str, self.paths))

    def _trafo(self, path):
        if type(path) is str:
            p = LazyPath(path)
        elif isinstance(path, AmiPath):
            p = LazyPath(path)
        elif not isinstance(path, LazyPath):
            raise ValueError("path is not a LazyPath")
        else:
            p = path
        # overwrite resolver
        if self.path_resolver:
            p.set_path_resolver(self.path_resolver)
        return p

    def set(self, paths):
        """set a list of lazy paths"""
        if paths is None:
            paths = []
        res = []
        for p in paths:
            res.append(self._trafo(p))
        self.paths = res

    def append(self, path):
        p = self._trafo(path)
        self.paths.append(p)

    def prepend(self, path):
        p = self._trafo(path)
        self.paths.insert(0, p)

    def remove(self, path):
        self.paths.remove(path)

    def get(self):
        """get the current list of lazy paths"""
        return self.paths

    def get_resolved(self):
        """return a list of all paths as resolved AmiPaths"""
        return [x.get_resolved() for x in self.paths]

    def is_resolved(self):
        """check if all items in the list are resolved"""
        for p in self.paths:
            if not p.is_resolved():
                return False
        return True

    def resolve(self):
        """resolve all items in the list"""
        for p in self.paths:
            p.resolve()
