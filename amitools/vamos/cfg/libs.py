from amitools.vamos.cfgcore import *


class LibsParser(Parser):
  def __init__(self):
    def_cfg = {
        "*.library": {
            "mode": "auto",
            "version": 0,
            "expunge": "shutdown"
        },
        "*.device": {
            "mode": "auto",
            "version": 0,
            "expunge": "shutdown"
        }
    }
    arg_cfg = {
        "libs": Argument('-O', '--lib-options',
                         action='append',
                         help="set lib/dev options: <lib>=<key>=<value>,...")
    }
    Parser.__init__(self, def_cfg, arg_cfg,
                    "libs/devs", "configure vamos libraries and devices")
    self.lib_default = self.def_dict.get_default()['*.library']
    self.dev_default = self.def_dict.get_default()['*.device']
    self.vd = ValueDict(ValueDict(str), kv_sep='=', sep='+')

  def _is_valid_lib_name(self, name):
    return name.endswith('.library')

  def _is_valid_dev_name(self, name):
    return name.endswith('.device')

  def parse_args(self, args):
    ad = self.arg_dict.gen_dict(args)
    if 'libs' in ad:
      libs = self.vd.parse(ad['libs'])
      for lib_name in libs:
        # check name
        if self._is_valid_lib_name(lib_name):
          default = self.lib_default
        elif self._is_valid_dev_name(lib_name):
          default = self.dev_default
        else:
          raise ValueError("invalid lib/dev name: " + lib)
        if lib_name not in self.cfg:
          self.cfg[lib_name] = self.def_dict.gen_dict(default)
        val = libs[lib_name]
        self.def_dict.merge_cfg(self.cfg[lib_name], val, self.lib_default)
      return libs
    else:
      return {}

  def parse_config(self, cfg_dict, file_format):
    for lib_name in cfg_dict:
      if self._is_valid_lib_name(lib_name):
        default = self.lib_default
      elif self._is_valid_dev_name(lib_name):
        default = self.dev_default
      else:
        continue
      lib_cfg = cfg_dict[lib_name]
      if lib_name not in self.cfg:
        self.cfg[lib_name] = self.def_dict.gen_dict(default)
      self.def_dict.merge_cfg(self.cfg[lib_name], lib_cfg, self.lib_default)
