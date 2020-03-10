from .value import Value, ValueList, ValueDict
from .defdict import DefaultDict
from .argdict import ArgumentDict
from .trafo import DictTrafo


class Parser(object):
    def __init__(
        self,
        name,
        def_cfg=None,
        arg_cfg=None,
        arg_sect=None,
        arg_desc=None,
        ini_trafo=None,
        ini_prefix=None,
        ini_list_sections=None,
    ):
        self.name = name
        self.def_dict = DefaultDict(def_cfg)
        self.arg_dict = ArgumentDict(arg_cfg)
        self.arg_sect = arg_sect
        self.arg_desc = arg_desc
        self.ini_trafo = ini_trafo
        self.dict_trafo = DictTrafo(ini_trafo, ini_prefix)
        self.cfg = self.def_dict.gen_dict()
        self.ini_list_sections = ini_list_sections

    def get_def_cfg(self):
        return self.def_dict

    def get_arg_cfg(self):
        return self.arg_dict

    def get_cfg_dict(self):
        return self.cfg

    def get_ini_list_sections(self):
        return self.ini_list_sections

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
        if file_format == "ini" and self.ini_trafo:
            cfg_dict = self.dict_trafo.transform(cfg_dict)
        self.def_dict.merge_cfg(self.cfg, cfg_dict)
