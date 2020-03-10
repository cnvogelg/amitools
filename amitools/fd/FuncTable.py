from .FuncDef import FuncDef


class FuncTable:
    """Store a function table"""

    def __init__(self, base_name, is_device=False):
        self.funcs = []
        self.base_name = base_name
        self.bias_map = {}
        self.name_map = {}
        self.index_tab = []
        self.max_bias = 0
        self.is_device = is_device

    def get_base_name(self):
        return self.base_name

    def get_funcs(self):
        return self.funcs

    def get_func_by_bias(self, bias):
        if bias in self.bias_map:
            return self.bias_map[bias]
        else:
            return None

    def get_max_bias(self):
        return self.max_bias

    def get_neg_size(self):
        return self.max_bias + 6

    def get_num_indices(self):
        return self.max_bias // 6

    def get_all_func_names():
        return list(self.name_map.keys())

    def has_func(self, name):
        return name in self.name_map

    def get_func_by_name(self, name):
        if name in self.name_map:
            return self.name_map[name]
        else:
            return None

    def get_num_funcs(self):
        return len(self.funcs)

    def get_index_table(self):
        return self.index_tab

    def get_func_by_index(self, idx):
        return self.index_tab[idx]

    def add_func(self, f):
        # add to list
        self.funcs.append(f)
        # store by bias
        bias = f.get_bias()
        if bias in self.bias_map:
            raise ValueError("bias %d already added!" % bias)
        self.bias_map[bias] = f
        # store by name
        name = f.get_name()
        self.name_map[name] = f
        # adjust max bias
        if bias > self.max_bias:
            self.max_bias = bias
        # update index table
        tab_len = bias // 6
        while len(self.index_tab) < tab_len:
            self.index_tab.append(None)
        index = tab_len - 1
        self.index_tab[index] = f

    def add_call(self, name, bias, arg, reg, is_std=False):
        if len(arg) != len(reg):
            raise IOError("Reg and Arg name mismatch in function definition")
        else:
            func_def = FuncDef(name, bias, False, is_std)
            self.add_func(func_def)
            if arg and len(arg) > 0:
                num_args = len(arg)
                for i in range(num_args):
                    func_def.add_arg(arg[i], reg[i])

    def dump(self):
        print(("FuncTable:", self.base_name))
        for f in self.funcs:
            f.dump()

    def get_num_std_calls(self):
        if self.is_device:
            return 6
        else:
            return 4

    def add_std_calls(self):
        if self.is_device:
            self.add_call("_OpenDev", 6, ["IORequest", "Unit"], ["a1", "d0"], True)
            self.add_call("_CloseDev", 12, ["IORequest"], ["a1"], True)
            self.add_call("_ExpungeDev", 18, ["MyDev"], ["a6"], True)
            self.add_call("_Empty", 24, [], [], True)
            self.add_call("BeginIO", 30, ["IORequest"], ["a1"], True)
            self.add_call("AbortIO", 36, ["IORequest"], ["a1"], True)
        else:
            self.add_call("_OpenLib", 6, ["MyLib"], ["a6"], True)
            self.add_call("_CloseLib", 12, ["MyLib"], ["a6"], True)
            self.add_call("_ExpungeLib", 18, ["MyLib"], ["a6"], True)
            self.add_call("_Empty", 24, [], [], True)
