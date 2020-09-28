class FuncDef:
    """A function definition"""

    def __init__(self, name, bias, private=False, is_std=False):
        self.name = name
        self.bias = bias
        self.index = (bias - 6) // 6
        self.private = private
        self.std = is_std
        self.args = []

    def __str__(self):
        return self.get_str()

    def get_name(self):
        return self.name

    def get_bias(self):
        return self.bias

    def get_index(self):
        return self.index

    def is_private(self):
        return self.private

    def is_std(self):
        return self.std

    def get_args(self):
        return self.args

    def add_arg(self, name, reg):
        self.args.append((name, reg))

    def dump(self):
        print((self.name, self.bias, self.private, self.args))

    def get_arg_str(self, with_reg=True):
        if len(self.args) == 0:
            return "()"
        elif with_reg:
            return "( " + ", ".join(["%s/%s" % (x[0], x[1]) for x in self.args]) + " )"
        else:
            return "( " + ", ".join(["%s" % x[0] for x in self.args]) + " )"

    def get_str(self, with_reg=True):
        return self.name + self.get_arg_str(with_reg)
