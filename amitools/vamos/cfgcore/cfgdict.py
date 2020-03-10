class ConfigDict(dict):
    """a dictionary that also allows to access fields direclty by key"""

    def __init__(self, other=None):
        if isinstance(other, dict):
            self.clone(other)
        elif other is not None:
            raise ValueError

    def clone(self, other):
        for o in other:
            v = other[o]
            if type(v) is dict:
                self[o] = ConfigDict(v)
            else:
                self[o] = v

    def __getattr__(self, name):
        if name in self:
            return self[name]
        else:
            raise AttributeError

    def __setattr__(self, name, val):
        self[name] = val

    def __delattr__(self, name):
        del self[name]
