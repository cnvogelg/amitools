from .impl import LibImpl


class LibRegistry:
    def __init__(self):
        self.impls = {}

    def add_lib_impl(self, name, impl):
        self.impls[name] = impl

    def get_lib_impl(self, name):
        """search a library by name and return its class"""
        if name in self.impls:
            return self.impls[name]

    def has_name(self, name):
        """test if a given name is available"""
        return name in self.impls

    def get_all_impls(self):
        """return all registered lib classes"""
        return list(self.impls.values())

    def get_all_names(self):
        """return all registered lib class names"""
        return list(self.impls.keys())
