from amitools.vamos.log import log_prof
from amitools.vamos.profiler import Profiler
from amitools.vamos.cfgcore import ConfigDict


class LibFuncProfileData(object):
    """keep info for a library function"""

    def __init__(self, func_id, add_samples=False):
        self.func_id = func_id
        if add_samples:
            self.deltas = []
        else:
            self.deltas = None
        self.sum = 0.0
        self.num = 0
        self.add_samples = add_samples
        self.tag = None

    def __eq__(self, other):
        return (
            self.func_id == other.func_id
            and self.add_samples == other.add_samples
            and self.deltas == other.deltas
            and self.sum == other.sum
            and self.num == other.num
            and self.tag == other.tag
        )

    def __ne__(self, other):
        return (
            self.func_id != other.func_id
            or self.add_samples != other.add_samples
            or self.deltas != other.deltas
            or self.sum != other.sum
            or self.num != other.num
            or self.tag != other.tag
        )

    @classmethod
    def from_dict(cls, data_dict, add_samples=False):
        func_id = data_dict.fid
        d = cls(func_id, add_samples)
        if "deltas" in data_dict:
            d.deltas = data_dict.deltas
        else:
            d.deltas = None
        if "tag" in data_dict:
            d.tag = data_dict.tag
        d.sum = data_dict.sum
        d.num = data_dict.num
        return d

    def get_data(self):
        cfg = ConfigDict({"fid": self.func_id, "sum": self.sum, "num": self.num})
        if self.deltas is not None:
            cfg["deltas"] = self.deltas
        if self.tag:
            cfg["tag"] = self.tag
        return cfg

    def count(self, delta):
        v = round(delta, 6)
        self.sum += v
        self.num += 1
        if self.add_samples:
            self.deltas.append(v)

    def get_func_id(self):
        return self.func_id

    def get_num_calls(self):
        return self.num

    def get_deltas(self):
        return self.deltas

    def get_sum_delta(self):
        return round(self.sum, 6)

    def get_avg_delta(self):
        if self.num > 0:
            return self.sum / self.num
        else:
            return 0.0

    def set_tag(self, tag):
        self.tag = tag

    def get_tag(self):
        return self.tag

    def __repr__(self):
        return "LibProfileFuncData(func_id=%r,add_samples=%r):num=%r,sum=%r,deltas=%r,tag=%r" % (
            self.func_id,
            self.add_samples,
            self.num,
            self.sum,
            self.deltas,
            self.tag,
        )

    def dump(self, name):
        n = self.num
        s = self.sum * 1000
        a = self.get_avg_delta() * 1000
        return "%-20s  %6d calls  %10.3f ms  avg  %10.3f ms  %s" % (
            name,
            n,
            s,
            a,
            self.tag,
        )


class LibProfileData(object):
    """store call profiles of all contained functions"""

    def __init__(self, fd=None, add_samples=False):
        """create profile with number of function indices"""
        self.fd = None
        self.add_samples = add_samples
        self.func_map = {}
        self.func_table = None
        if fd:
            self.setup_func_table(fd)

    def __repr__(self):
        return "LibProfileData(func_map=%r,add_samples=%r)" % (
            self.func_map,
            self.add_samples,
        )

    def __eq__(self, other):
        return self.func_map == other.func_map and self.add_samples == other.add_samples

    def __ne__(self, other):
        return self.func_map != other.func_map or self.add_samples != other.add_samples

    @classmethod
    def from_dict(cls, data_dict, fd=None):
        add_samples = data_dict.add_samples
        obj = cls(add_samples=add_samples)
        funcs = data_dict.funcs
        for name in funcs:
            data = funcs[name]
            func_prof = LibFuncProfileData.from_dict(data, add_samples)
            obj.func_map[name] = func_prof
        if fd:
            obj.setup_func_table(fd)
        return obj

    def get_data(self):
        res = ConfigDict()
        res["add_samples"] = self.add_samples
        funcs = {}
        res["funcs"] = funcs
        for name in self.func_map:
            func = self.func_map[name]
            data = func.get_data()
            funcs[name] = data
        return res

    def setup_func_table(self, fd, impl_funcs=None):
        self.fd = fd
        num_func = fd.get_num_indices()
        self.func_table = []
        for idx in range(num_func):
            fd_func = fd.get_func_by_index(idx)
            if fd_func:
                name = fd_func.get_name()
                if name in self.func_map:
                    func = self.func_map[name]
                else:
                    func = LibFuncProfileData(idx, self.add_samples)
                    self.func_map[name] = func
                # add tag?
                if impl_funcs and name in impl_funcs:
                    tag = impl_funcs[name].tag
                    func.set_tag(tag)
            else:
                func = None
            self.func_table.append(func)

    def remove_empty(self):
        new_map = {}
        for name in self.func_map:
            func = self.func_map[name]
            if func.get_num_calls() > 0:
                new_map[name] = func
        self.func_map = new_map
        self.func_table = None

    def get_fd(self):
        return self.fd

    def get_func_by_index(self, index):
        return self.func_table[index]

    def get_func_by_name(self, name):
        return self.func_map[name]

    def get_all_func_names(self):
        return sorted(self.func_map.keys())

    def get_all_funcs(self):
        """return a generator for func_name, func tuples"""
        for name in sorted(self.func_map.keys()):
            func = self.func_map[name]
            yield name, func

    def get_total(self):
        total_calls = 0
        total_delta = 0.0
        for name in self.func_map:
            func = self.func_map[name]
            total_calls += func.get_num_calls()
            total_delta += func.get_sum_delta()
        if total_calls > 0:
            avg = total_delta / total_calls
        else:
            avg = 0.0
        return total_calls, total_delta, avg

    def get_total_str(self):
        c, d, a = self.get_total()
        d *= 1000
        a *= 1000
        return "%-20s  %6d calls  %10.3f ms  avg  %10.3f ms" % ("LIB TOTAL", c, d, a)

    def dump(self, name, write=print):
        write("----- %s -----" % name)
        for name in self.get_all_func_names():
            func = self.func_map[name]
            write(func.dump(name))
        total = self.get_total_str()
        write(total)


class LibProfiler(Profiler):

    name = "libs"

    def __init__(self, names=None, add_calls=False, add_all=False):
        self.lib_profiles = {}
        self.names = names
        self.add_all = add_all
        self.add_calls = add_calls
        self.enabled = False

    def get_name(self):
        return self.name

    def parse_config(self, cfg):
        if not cfg:
            return True
        self.names = cfg.names
        self.add_calls = cfg.calls
        return True

    def set_data(self, data_dict):
        data_list = data_dict.data
        for name in data_list:
            data = data_list[name]
            prof = LibProfileData.from_dict(data)
            if not prof:
                return False
            self.lib_profiles[name] = prof
        return True

    def get_data(self):
        res = ConfigDict()
        libs = {}
        res["data"] = libs
        for name in self.lib_profiles:
            prof = self.lib_profiles[name]
            libs[name] = prof.get_data()
        return res

    def setup(self):
        if self.names is None:
            self.names = []
        self.add_all = "all" in self.names
        self.enabled = True
        log_prof.debug(
            "libs: names=%s, all=%s, add_calls=%s",
            self.names,
            self.add_all,
            self.add_calls,
        )

    def shutdown(self):
        for name in self.lib_profiles:
            prof = self.lib_profiles[name]
            # prof.remove_empty()
        num_libs = self.get_num_libs()
        if num_libs == 0:
            log_prof.warning("profiling enabled but no lib profiles found!")

    def create_profile(self, lib_name, fd, impl_funcs=None):
        """get or create a new profile for a library"""
        # profiling disabled
        if not self.enabled:
            log_prof.debug("libs: create '%s' -> disabled", lib_name)
            return None
        # already created profile
        if lib_name in self.lib_profiles:
            log_prof.debug("libs: create '%s' -> reuse", lib_name)
            prof = self.lib_profiles[lib_name]
            prof.setup_func_table(fd, impl_funcs)
            return prof
        elif self.add_all or lib_name in self.names:
            # shall we create a profile for this lib?
            log_prof.debug("libs: create '%s' -> NEW", lib_name)
            prof = LibProfileData(fd, self.add_calls)
            self.lib_profiles[lib_name] = prof
            return prof
        else:
            log_prof.debug("libs: create '%s' -> not found", lib_name)

    def get_profile(self, lib_name):
        if lib_name in self.lib_profiles:
            return self.lib_profiles[lib_name]

    def get_all_lib_names(self):
        return sorted(self.lib_profiles.keys())

    def get_all_libs(self):
        """return generator for lib_name, lib tuples"""
        lib_names = self.get_all_lib_names()
        for lib_name in lib_names:
            lib = self.lib_profiles[lib_name]
            yield lib_name, lib

    def get_num_libs(self):
        return len(self.lib_profiles)

    def dump(self, log=print):
        names = self.get_all_lib_names()
        for name in names:
            prof = self.get_profile(name)
            prof.dump(name, log)
