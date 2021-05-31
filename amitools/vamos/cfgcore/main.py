import argparse
import configparser
import json
import logging
import os
import pprint
import io
from .value import Value, ValueList, ValueDict
from .cfgdict import ConfigDict


# get and configure a config logger before all other loggers
# of the system are initialized. They are often configured by
# the config system itself...
log_cfg = logging.getLogger("config")


class MainParser(object):
    def __init__(self, debug=None, *args, **kwargs):
        if debug is None:
            debug = "AMITOOLS_CONFIG_DEBUG" in os.environ
        self.parsers = []
        self.ap = argparse.ArgumentParser(*args, **kwargs)
        self._patch_arg_exit()
        self._setup_logging(debug)
        self.args = None
        self.arg_grp = None
        self.file_arg_name = None
        self.skip_arg_name = None

    def _patch_arg_exit(self):
        self.ap_error = None

        def error(this, message):
            self.ap_error = message

        self.ap.error = error.__get__(self.ap, argparse.ArgumentParser)

    def add_parser(self, sub_parser):
        self.parsers.append(sub_parser)
        sub_parser.setup_args(self.ap)

    def get_arg_parser(self):
        return self.ap

    def get_args(self):
        return self.args

    def parse(self, paths=None, args=None, cfg_dict=None):
        """convenience function that combines all other calls.

        add file and skip args.
        pre-parse args.
        either load given config.
        if no skip args:
          try given paths for configs. first match wins.
        finally parse args.

        return True if parsing was without errors else False
        """
        self.add_file_arg()
        self.add_skip_arg()
        self.add_config_debug()
        ok, cfg_file, skip_cfgs = self.pre_parse_args(args)
        if not ok:
            return False
        # enable config debug
        log_cfg.info("input paths: %r, args: %r, cfg_dict: %r", paths, args, cfg_dict)
        log_cfg.info("args: cfg_file=%s, skip_cfgs=%s", cfg_file, skip_cfgs)
        # read config given in args
        if cfg_file:
            res = self.parse_config_auto(cfg_file)
            ok = res is not None
            log_cfg.info("args: cfg_file '%s' is ok: %s", cfg_file, ok)
        # try to read given config paths
        elif not skip_cfgs and paths:
            log_cfg.info("paths: try config files: %s", paths)
            cfg_file, res = self.parse_files(paths)
            ok = res is not None or cfg_file is None
            log_cfg.info("paths: cfg_file '%s' is ok: %s", cfg_file, ok)
        else:
            ok = True
        # additional config?
        if ok and cfg_dict:
            ok = self.parse_dict_config(cfg_dict)
            log_cfg.info("cfg_dict: ok: %s", ok)
        # handle args
        try:
            self.parse_args()
        except ValueError as e:
            log_cfg.error("args: parser failed: %s", e)
            return False
        # dump config?
        if getattr(self.args, "config_dump", False):
            self._dump_config()
        return ok

    def get_cfg_dict(self):
        res = ConfigDict()
        for parser in self.parsers:
            d = parser.get_cfg_dict()
            for key in d:
                if key in res:
                    raise ValueError("duplicate key in cfg: %s", key)
                res[key] = d[key]
        return res

    def add_file_arg(self, name=None, long_name=None, arg_name=None, args=None):
        """add a command line arg to specify a config file."""
        # setup default naming
        if name is None:
            name = "-c"
        if long_name is None:
            long_name = "--config-file"
        if arg_name is None:
            arg_name = "config_file"
        # add arg switch
        self._ensure_arg_group()
        self.arg_grp.add_argument(
            name,
            long_name,
            action="store",
            default=None,
            help="read configuration from specified file",
        )
        self.file_arg_name = arg_name

    def add_skip_arg(self, name=None, long_name=None, arg_name=None):
        """add a 'skip default config' switch."""
        # setup default naming
        if name is None:
            name = "-S"
        if long_name is None:
            long_name = "--skip-configs"
        if arg_name is None:
            arg_name = "skip_configs"
        # add arg switch
        self._ensure_arg_group()
        self.arg_grp.add_argument(
            name,
            long_name,
            action="store_true",
            default=False,
            help="do not read any configuration files",
        )
        self.skip_arg_name = arg_name

    def add_config_debug(self):
        self._ensure_arg_group()
        self.arg_grp.add_argument(
            "--config-debug",
            action="store_true",
            default=False,
            help="debug config parsing",
        )
        self.arg_grp.add_argument(
            "--config-dump",
            action="store_true",
            default=False,
            help="dump final config",
        )

    def _ensure_arg_group(self):
        if self.arg_grp is None:
            self.arg_grp = self.ap.add_argument_group(
                "Config Options", "control reading of config files"
            )

    def pre_parse_args(self, args=None):
        """parse args to get the values for file and skip arg.

        Returns (cfg_file, skip_cfg) or (None, False)
        """
        self.args = self.ap.parse_args(args)
        if self.ap_error:
            log_cfg.error("args: %s", self.ap_error)
            return False, None, False
        cfg_file = None
        skip_cfg = False
        if self.file_arg_name:
            cfg_file = getattr(self.args, self.file_arg_name, None)
        if self.skip_arg_name:
            skip_cfg = getattr(self.args, self.skip_arg_name, False)
        # enable config debug via arg?
        config_debug = getattr(self.args, "config_debug", False)
        if config_debug:
            self._enable_logging()
        return True, cfg_file, skip_cfg

    def parse_dict_config(self, cfg_dict, file_format=None):
        if file_format is None:
            file_format = "dict"
        for parser in self.parsers:
            try:
                parser.parse_config(cfg_dict, file_format)
            except ValueError as e:
                log_cfg.error("%s: failed: %s", parser.name, e)
                return False
        return True

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
        if file_format == "json":
            return self.parse_json_config(file)
        elif file_format == "ini":
            return self.parse_ini_config(file)

    def parse_ini_config(self, file_name):
        is_str = type(file_name) is str
        if is_str and not os.path.exists(file_name):
            log_cfg.info("ini config '%s' doest not exist!", file_name)
            return None
        cfg_dict = self._read_ini_file(file_name)
        # report to parsers
        if cfg_dict:
            log_cfg.debug("ini file input: %s", cfg_dict)
            for parser in self.parsers:
                try:
                    parser.parse_config(cfg_dict, "ini")
                except ValueError as e:
                    log_cfg.error("%s: failed: %s", parser.name, e)
                    return None
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
                try:
                    parser.parse_config(cfg_dict, "json")
                except ValueError as e:
                    log_cfg.error("%s: failed: %s", parser.name, e)
                    return None
        return cfg_dict

    def parse_args(self):
        # if args were not already parsed by pre_parse_args() above
        if self.args is None:
            raise RuntimeError("run pre_parse_args() first!")
        # notify parsers about args
        for parser in self.parsers:
            parser.parse_args(self.args)

    def _auto_detect_format(self, file_obj):
        for line in file_obj:
            l = line.strip()
            if l.startswith("{"):
                return "json"
            elif l.startswith("["):
                return "ini"
            elif l.startswith("#"):
                # ignore comment
                pass
            elif len(l) > 0:
                return None

    def _setup_logging(self, debug):
        ch = logging.StreamHandler()
        ch.setLevel(logging.DEBUG)
        formatter = logging.Formatter("%(name)10s:%(levelname)7s:  %(message)s")
        ch.setFormatter(formatter)
        log_cfg.addHandler(ch)
        if debug:
            log_cfg.setLevel(logging.DEBUG)
        else:
            log_cfg.setLevel(logging.WARN)
        log_cfg.debug("logging setup")

    def _enable_logging(self):
        log_cfg.setLevel(logging.DEBUG)

    def _read_ini_file(self, file_name):
        is_str = type(file_name) is str
        log_name = file_name if is_str else "???"
        p = configparser.ConfigParser()
        try:
            if is_str:
                p.read(file_name)
            else:
                p.read_file(file_name)
        except configparser.Error as e:
            txt = str(e).replace("\n", "  ")
            log_cfg.error("%s: ini parser failed: %s", log_name, txt)
            return None
        except IOError as e:
            log_cfg.error("%s: IO error: %s", log_name, e)
            return None
        # convert to dictionary
        list_sections = self._get_list_sections()
        res = {}
        for sec in p.sections():
            # create a section list
            if sec in list_sections:
                sec_list = []
                res[sec] = sec_list
                for key, val in p.items(sec):
                    sec_list.append([key, val])
            else:
                # create a section dictionary
                sec_dict = {}
                res[sec] = sec_dict
                for key, val in p.items(sec):
                    sec_dict[key] = val
        return res

    def _get_list_sections(self):
        # ask all parsers for sections to be converted to lists
        ls = set()
        for p in self.parsers:
            pls = p.get_ini_list_sections()
            if pls:
                for s in pls:
                    ls.add(s)
        return ls

    def _dump_config(self):
        out = io.StringIO()
        cfg = self.get_cfg_dict()
        pprint.pprint(cfg, out)
        res = out.getvalue()
        out.close()
        self._enable_logging()
        for line in res.splitlines():
            log_cfg.info(line)
