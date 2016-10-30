import ConfigParser
import os
import os.path

from Log import log_main

class VamosLibConfig:
  def __init__(self, mode='auto', version=0, profile=False):
    self.mode = mode
    self.version = version
    self.profile = profile
    # types of keys
    self._keys = {
      'mode' : str,
      'version' : int,
      'profile' : bool
    }

  def parse_key_value(self, lib_name, kv_str, errors):
    """parse a key value string: k=v,k=v,..."""
    kvs = kv_str.split(',')
    if len(kvs) == 0:
      errors.append("%s: No key,value given in -o option: '%s'" % (lib_name, kv_str))
    else:
      for kv in kvs:
        r = kv.split('=')
        if len(r) != 2:
          errors.append("%s: Syntax error: '%s'" % (lib_name, kv))
        else:
          k,v = r
          self.set_value(lib_name, k, v, errors)

  def set_value(self, lib_name, k, v, errors):
    if k in self._keys:
      t = self._keys[k]
      try:
        rv = t(v)
        # validate value
        check_name = '_check_' + k
        if hasattr(self, check_name):
          check_func = getattr(self, check_name)
          if check_func(rv):
            setattr(self, k, rv)
          else:
            errors.append("%s: invalid '%s' value: '%s'" % (lib_name, k, rv))
        # no validation available
        else:
          setattr(self, k, rv)
      except ValueError:
        errors.append("%s: invalid '%s' value: '%s' for type %s" % (lib_name, k, v, t))
    else:
      errors.append("%s: invalid key: '%s'" % (lib_name, k))

  def _check_mode(self, v):
    return v in ('auto', 'vamos', 'amiga', 'off')

  def _check_version(self, v):
    return v >= 0



class VamosConfig(ConfigParser.SafeConfigParser):

  default_lib = '*.library'

  def __init__(self, extra_file=None, skip_defaults=False, args=None, def_data_dir=None):
    ConfigParser.SafeConfigParser.__init__(self)
    self.def_data_dir = def_data_dir
    self.files = []
    self.args = args

    # keep errors until logging is available
    self.errors = []

    # prepend extra file
    if extra_file != None:
      self.files.append(extra_file)
    # read default config files (if they exist)
    if not skip_defaults:
      # add config in current working dir
      self.files.append(os.path.join(os.getcwd(),".vamosrc"))
      # add config in home directory
      self.files.append(os.path.expanduser("~/.vamosrc"))

    # read configs
    self.found_files = self.read(self.files)

    # setup config
    self._reset()
    self._parse_config()
    self._parse_lib_config()
    self._parse_args(args)
    self._parse_lib_args(args)
    self._set_defaults()

  def get_lib_config(self, lib_name):
    """get a configuration object for the given lib"""
    # specific lib in config?
    if lib_name in self.libs:
      return self.libs[lib_name]
    # default config
    elif self.default_lib in self.libs:
      return self.libs[default_lib]
    # create default config
    else:
      return VamosLibConfig(version=40)

  def get_args(self):
    """return the command line arguments"""
    return self.args

  def log(self):
    """after logging is setup dump info and other remarks"""
    if len(self.found_files) == 0:
      log_main.info("no config file found: %s" % ",".join(self.files))
    else:
      log_main.info("read config file: %s" % ",".join(self.found_files))
    # dump config
    self._dump()
    # print recorded errors
    if len(self.errors) > 0:
      for e in self.errors:
        log_main.error("config error: " + e)

  def _dump(self):
    # main config
    for key in sorted(self._keys):
      log_main.debug("config: [vamos]  %s = %s", key, getattr(self,key))
    # lib configs
    for lib in sorted(self.libs):
      cfg = self.libs[lib]
      for key in sorted(cfg._keys):
        log_main.debug("config: [%s]  %s = %s", lib, key, getattr(cfg,key))

  def _reset(self):
    # library config
    self.libs = {
      'dos.library' : VamosLibConfig('vamos', 40, False),
      'exec.library' : VamosLibConfig('vamos', 40, False),
      'icon.library' : VamosLibConfig('auto', 0, False)
    }
    # define keys that can be set
    self._keys = {
      # logging
      'logging' : (str, None),
      'verbose' : (int, 0),
      'quiet' : (bool, False),
      'benchmark' : (bool, False),
      'log_file' : (str, None),
      # low-level tracing
      'instr_trace' : (bool, False),
      'memory_trace' : (bool, False),
      'internal_memory_trace' : (bool, False),
      'reg_dump' : (bool, False),
      # cpu emu
      'cpu' : (str, "68000"),
      'max_cycles' : (int, 0),
      'cycles_per_block' : (int, 1000),
      # system
      'ram_size' : (int, 1024),
      'stack_size' : (int, 4),
      'hw_access' : (str, "emu"),
      'shell' : (bool, False),
      # dirs
      'data_dir' : (str, self.def_data_dir),
      # paths
      'pure_ami_paths' : (bool, False)
    }
    # prefill keys with None
    for key in self._keys:
      setattr(self, key, None)

  def _set_defaults(self):
    for key in self._keys:
      val = getattr(self, key)
      if val is None:
        def_val = self._keys[key][1]
        setattr(self, key, def_val)

  def _check_cpu(self, val):
    return val in ('68000','68020','000','020','00','20')

  def _set_value(self, key, value):
    if key in self._keys:
      val_type = self._keys[key][0]
      try:
        rv = val_type(value)
        # check value
        check_name = '_check_' + key
        if hasattr(self, check_name):
          check_func = getattr(self, check_name)
          if(check_func(rv)):
            setattr(self, key, rv)
          else:
            self.errors.append("Invalid '%s' value: '%s'" % (key, rv))
        else:
          setattr(self, key, rv)
      except ValueError:
        self.errors.append("Invalid '%s' type: '%s' must be %s" % (key, value, val_type))
    else:
      self.errors.append("Invalid key: '%s'" % key)

  def _parse_config(self):
    # parse [vamos] section
    sect = 'vamos'
    for key in self._keys:
      if self.has_option(sect, key) and getattr(self, key) is None:
        value = self.get(sect, key)
        self._set_value(key, value)

  def _parse_args(self, args):
    # get paramters from args (allow to overwrite existing settings)
    for key in self._keys:
      if hasattr(args, key):
        arg_value = getattr(args, key)
        if arg_value is not None:
          self._set_value(key, arg_value)

  def _parse_lib_config(self):
    # run through all sections matching [<bla.library>]:
    for lib_name in self.sections():
      if lib_name.endswith('.library'):
        # check for lib
        if lib_name in self.libs:
          lib = self.libs[lib_name]
        else:
          lib = VamosLibConfig()
          self.libs[lib_name] = lib
        # walk through options
        for key in self.options(lib_name):
          if key in lib._keys:
            v = self.get(lib_name, key)
            # set value
            lib.set_value(lib_name, key, v, self.errors)
          else:
            self.errors.append("%s: Invalid option: '%s'" % (lib_name, key))

  def _parse_lib_args(self, args):
    # parse lib options
    if hasattr(args, 'lib_options') and args.lib_options != None:
      for e in args.lib_options:
        # lib:key=value,key=value
        r = e.split(':')
        if len(r) != 2:
          self.errors.append("Syntax error: '%s'" % e)
        else:
          lib, kv = r
          # generate lib name
          if lib.endswith('.library'):
            lib_name = lib
          else:
            lib_name = lib + '.library'
          # find or create config
          if lib_name in self.libs:
            # use already defined lib
            lib_cfg = self.libs[lib_name]
          else:
            # create new lib
            lib_cfg = VamosLibConfig()
            self.libs[lib_name] = lib_cfg
          # parse key value
          lib_cfg.parse_key_value(lib_name, kv, self.errors)
