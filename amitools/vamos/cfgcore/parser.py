from .value import Value, ValueList, ValueDict
from .defdict import DefaultDict
from .argdict import ArgumentDict


class Parser(object):

  def __init__(self, def_cfg=None, arg_cfg=None,
               arg_sect=None, arg_desc=None):
    self.def_dict = DefaultDict(def_cfg)
    self.arg_dict = ArgumentDict(arg_cfg)
    self.arg_sect = arg_sect
    self.arg_desc = arg_desc
    self.cfg = self.def_dict.gen_dict()

  def get_def_cfg(self):
    return self.def_dict

  def get_arg_cfg(self):
    return self.arg_dict

  def get_cfg_dict(self):
    return self.cfg

  def setup_args(self, argparse):
    if self.arg_sect:
      target = argparse.add_argument_group(self.arg_sect, self.arg_desc)
    else:
      target = argparse
    self.arg_dict.add_args(target)

  def parse_args(self, args):
    ad = self.arg_dict.gen_dict(args)
    self.def_dict.merge_cfg(self.cfg, ad)
    return ad

  def parse_config(self, cfg_dict, file_format):
    self.def_dict.merge_cfg(self.cfg, cfg_dict)
