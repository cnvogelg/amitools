class DictTrafo(object):
    def __init__(self, trafo_dict=None, prefix=None):
        if trafo_dict is None:
            trafo_dict = {}
        self.trafo_dict = trafo_dict
        if type(prefix) is str:
            self.prefix = (prefix,)
        elif type(prefix) is tuple:
            self.prefix = prefix
        else:
            self.prefix = None

    def transform(self, in_dict, trafo_dict=None, keep_none=False):
        if trafo_dict is None:
            trafo_dict = self.trafo_dict
        res = {}
        for key in trafo_dict:
            val = trafo_dict[key]
            tval = type(val)
            # sub dict
            if tval is dict:
                vres = self.transform(in_dict, val)
            # (callable, rel_path)
            elif tval is tuple and len(val) == 2 and callable(val[0]):
                rel_path = self.read_rel_path(val[1], in_dict)
                vres = val[0](key, rel_path)
            # a rel_path in in_dict
            elif tval in (str, tuple, list):
                vres = self.read_rel_path(val, in_dict)
            # invalid
            else:
                raise ValueError("invalid type in trafo_dict: %s" + val)
            if vres is not None or keep_none:
                res[key] = vres
        return res

    def read_rel_path(self, path, in_dict):
        abs_path = []
        if self.prefix:
            abs_path += self.prefix
        if type(path) is str:
            abs_path.append(path)
        else:
            abs_path += path
        return self.read_path(abs_path, in_dict)

    def read_path(self, path, in_dict):
        if len(path) == 0:
            return in_dict
        if type(in_dict) is not dict:
            return None
        key = path[0]
        if key in in_dict:
            val = in_dict[key]
            path = path[1:]
            return self.read_path(path, val)
