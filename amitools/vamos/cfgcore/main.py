import argparse
import ConfigParser
import json
import logging
import os
from .value import Value, ValueList, ValueDict


# get and configure a config logger before all other loggers
# of the system are initialized. They are often configured by
# the config system itself...
log_cfg = logging.getLogger('config')


class MainParser(object):

  def __init__(self, debug=None, *args, **kwargs):
    if debug is None:
      debug = 'AMITOOLS_CONFIG_DEBUG' in os.environ
    self.parsers = []
    self.ap = argparse.ArgumentParser(*args, **kwargs)
    self._setup_logging(debug)
    self.args = None
    self.arg_grp = None
    self.file_arg_name = None
    self.skip_arg_name = None

  def add_parser(self, sub_parser):
    self.parsers.append(sub_parser)
    sub_parser.setup_args(self.ap)

  def parse(self, paths=None, args=None):
    """convenience function that combines all other calls.

       add file and skip args.
       pre-parse args.
       either load given config.
       if no skip args:
         try given paths for configs. first match wins.
       finally parse args.

       return (cfg_file, read_ok) or (None, True) on skip
    """
    self.add_file_arg()
    self.add_skip_arg()
    cfg_file, skip_cfgs = self.pre_parse_args(args)
    if cfg_file:
      res = self.parse_config_auto(cfg_file)
      ok = res is not None
    elif not skip_cfgs:
      cfg_file, res = self.parse_files(paths)
      ok = res is not None
    else:
      ok = True
    self.parse_args(args)
    return cfg_file, ok

  def add_file_arg(self, name=None, long_name=None, arg_name=None,
                   args=None):
    """add a command line arg to specify a config file."""
    # setup default naming
    if name is None:
      name = '-c'
    if long_name is None:
      long_name = '--config-file'
    if arg_name is None:
      arg_name = 'config_file'
    # add arg switch
    self._ensure_arg_group()
    self.arg_grp.add_argument(name, long_name, action='store', default=None,
                              help="read configuration from specified file")
    self.file_arg_name = arg_name

  def add_skip_arg(self, name=None, long_name=None, arg_name=None):
    """add a 'skip default config' switch."""
    # setup default naming
    if name is None:
      name = '-S'
    if long_name is None:
      long_name = '--skip-configs'
    if arg_name is None:
      arg_name = 'skip_configs'
    # add arg switch
    self._ensure_arg_group()
    self.arg_grp.add_argument(name, long_name,
                              action='store_true', default=False,
                              help="do not read any configuration files")
    self.skip_arg_name = arg_name

  def _ensure_arg_group(self):
    if self.arg_grp is None:
      self.arg_grp = self.ap.add_argument_group(
          'Config Options',
          'control reading of config files')

  def pre_parse_args(self, args=None):
    """parse args to get the values for file and skip arg.

       Returns (cfg_file, skip_cfg) or (None, False)
    """
    self.args = self.ap.parse_args(args)
    cfg_file = None
    skip_cfg = False
    if self.file_arg_name:
      cfg_file = getattr(self.args, self.file_arg_name, None)
    if self.skip_arg_name:
      skip_cfg = getattr(self.args, self.skip_arg_name, False)
    return cfg_file, skip_cfg

  def parse_dict_config(self, cfg_dict, file_format=None):
    if file_format is None:
      file_format = 'dict'
    for parser in self.parsers:
      parser.parse_config(cfg_dict, file_format)

  def parse_files(self, paths):
    if paths is None:
      return None, None
    for file in paths:
      if os.path.exists(file):
        res = self.parse_config_auto(file)
        return file, res
    return None, None

  def parse_config_auto(self, file):
    is_str = type(file) is str
    if is_str and not os.path.exists(file):
      log_cfg.info("config '%s' doest not exist!", file)
      return None
    try:
      if is_str:
        with open(file, "r") as fh:
          file_format = self._auto_detect_format(fh)
      else:
        file_format = self._auto_detect_format(file)
        file.seek(0)
    except IOError as e:
      log_cfg.error("%s: IO error: %s", file, e)
      return None
    log_cfg.debug("%s: format '%s' detected", file, file_format)
    if file_format == 'json':
      return self.parse_json_config(file)
    elif file_format == 'ini':
      return self.parse_ini_config(file)

  def parse_ini_config(self, file_name):
    is_str = type(file_name) is str
    if is_str and not os.path.exists(file_name):
      log_cfg.info("ini config '%s' doest not exist!", file_name)
      return None
    cfg_dict = self._read_ini_file(file_name)
    # report to parsers
    if cfg_dict:
      for parser in self.parsers:
        parser.parse_config(cfg_dict, 'ini')
    return cfg_dict

  def parse_json_config(self, file_name):
    is_str = type(file_name) is str
    log_name = file_name if is_str else "???"
    if is_str and not os.path.exists(file_name):
      log_cfg.info("json config '%s' doest not exist!", file_name)
      return None
    try:
      if is_str:
        with open(file_name, "r") as fh:
          cfg_dict = json.load(fh)
      else:
        cfg_dict = json.load(file_name)
    except ValueError as e:
      log_cfg.error("%s: json parser failed: %s", log_name, e)
      return None
    except IOError as e:
      log_cfg.error("%s: IO error: %s", log_name, e)
      return None
    # report to parsers
    if cfg_dict:
      for parser in self.parsers:
        parser.parse_config(cfg_dict, 'json')
    return cfg_dict

  def parse_args(self, args=None):
    # if args were not already parsed by pre_parse_args() above
    if self.args is None:
      self.args = self.ap.parse_args(args)
    # notify parsers about args
    for parser in self.parsers:
      parser.parse_args(self.args)
    return self.args

  def _auto_detect_format(self, file_obj):
    for line in file_obj:
      l = line.strip()
      if l.startswith('{'):
        return 'json'
      elif l.startswith('['):
        return 'ini'
      elif len(l) > 0:
        return None

  def _setup_logging(self, debug):
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(name)10s:%(levelname)7s:  %(message)s')
    ch.setFormatter(formatter)
    log_cfg.addHandler(ch)
    if debug:
      log_cfg.setLevel(logging.DEBUG)
    else:
      log_cfg.setLevel(logging.WARN)
    log_cfg.debug("logging setup")

  def _read_ini_file(self, file_name):
    is_str = type(file_name) is str
    log_name = file_name if is_str else "???"
    p = ConfigParser.SafeConfigParser()
    try:
      if is_str:
        p.read(file_name)
      else:
        p.readfp(file_name)
    except ConfigParser.Error as e:
      txt = str(e).replace('\n', '  ')
      log_cfg.error("%s: ini parser failed: %s", log_name, txt)
      return None
    except IOError as e:
      log_cfg.error("%s: IO error: %s", log_name, e)
      return None
    # convert to dictionary
    res = {}
    for sec in p.sections():
      sec_dict = {}
      res[sec] = sec_dict
      for key, val in p.items(sec):
        sec_dict[key] = val
    return res
