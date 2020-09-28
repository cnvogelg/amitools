from amitools.vamos.cfgcore import *


class LibsParser(Parser):
    def __init__(self):
        modes = ("auto", "vamos", "amiga", "fake", "off")
        expunges = ("last_close", "shutdown", "no_mem")
        def_cfg = {
            "libs": {
                "*.library": {
                    "mode": Value(str, "auto", enum=modes),
                    "version": 0,
                    "expunge": Value(str, "shutdown", enum=expunges),
                    "num_fake_funcs": 0,
                }
            },
            "devs": {
                "*.device": {
                    "mode": Value(str, "auto", enum=modes),
                    "version": 0,
                    "expunge": Value(str, "shutdown", enum=expunges),
                    "num_fake_funcs": 0,
                }
            },
        }
        arg_cfg = {
            "libs": Argument(
                "-O",
                "--lib-options",
                action="append",
                help="set lib/dev options: <lib>=<key>=<value>,...",
            )
        }
        Parser.__init__(
            self,
            "libs",
            def_cfg,
            arg_cfg,
            "libs/devs",
            "configure vamos libraries and devices",
        )
        self.lib_default = self.def_dict.get_default()["libs"]["*.library"]
        self.dev_default = self.def_dict.get_default()["devs"]["*.device"]
        self.vd = ValueDict(ValueDict(str), kv_sep="=", sep="+")

    def _is_valid_lib_name(self, name):
        return name.endswith(".library")

    def _is_valid_dev_name(self, name):
        return name.endswith(".device")

    def _ensure_name_dict(self, group, name, default):
        # ensure group
        if group not in self.cfg:
            g = {}
            self.cfg[group] = g
        else:
            g = self.cfg[group]
        # ensure name
        if name not in g:
            n = self.def_dict.gen_dict(default)
            g[name] = n
        else:
            n = g[name]
        return n

    def parse_args(self, args):
        ad = self.arg_dict.gen_dict(args)
        if "libs" in ad:
            libs = self.vd.parse(ad["libs"])
            for lib_name in libs:
                # check name
                if self._is_valid_lib_name(lib_name):
                    default = self.lib_default
                    lib_dict = self._ensure_name_dict("libs", lib_name, default)
                elif self._is_valid_dev_name(lib_name):
                    default = self.dev_default
                    lib_dict = self._ensure_name_dict("devs", lib_name, default)
                else:
                    raise ValueError("invalid lib/dev name: " + lib)
                # merge values
                val = libs[lib_name]
                self.def_dict.merge_cfg(lib_dict, val, default)
            return libs
        else:
            return {}

    def parse_config(self, cfg_dict, file_format):
        if file_format == "ini":
            self._parse_config_ini(cfg_dict)
        else:
            self._parse_config_dict(cfg_dict)

    def _parse_config_dict(self, cfg_dict):
        if "libs" in cfg_dict:
            default = self.lib_default
            libs = cfg_dict["libs"]
            for lib_name in libs:
                lib_dict = self._ensure_name_dict("libs", lib_name, default)
                # merge values
                val = libs[lib_name]
                self.def_dict.merge_cfg(lib_dict, val, default)
        if "devs" in cfg_dict:
            default = self.dev_default
            devs = cfg_dict["devs"]
            for lib_name in devs:
                lib_dict = self._ensure_name_dict("devs", lib_name, default)
                # merge values
                val = devs[lib_name]
                self.def_dict.merge_cfg(lib_dict, val, default)

    def _parse_config_ini(self, cfg_dict):
        for lib_name in cfg_dict:
            if self._is_valid_lib_name(lib_name):
                default = self.lib_default
                lib_dict = self._ensure_name_dict("libs", lib_name, default)
            elif self._is_valid_dev_name(lib_name):
                default = self.dev_default
                lib_dict = self._ensure_name_dict("devs", lib_name, default)
            else:
                continue
            # merge values
            lib_cfg = cfg_dict[lib_name]
            self.def_dict.merge_cfg(lib_dict, lib_cfg, default)
