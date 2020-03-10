import os
from amitools.vamos.log import log_prof
from amitools.vamos.cfgcore import ConfigDict
from .data import ProfDataFile


class MainProfiler(object):
    """main profiler manages a set of profilers"""

    def __init__(self, enabled=False, file=None, append=False, dump=False):
        self.enabled = enabled
        self.file = file
        self.append = append
        self.dump = dump
        # state
        self.cfg = None
        self.profilers = {}

    def parse_config(self, cfg):
        if cfg is None:
            return True
        self.cfg = cfg
        self.enabled = cfg.enabled
        self.file = cfg.output.file
        self.append = cfg.output.append
        self.dump = cfg.output.dump
        return True

    def add_profiler(self, prof):
        """add profiler and return if it was activated"""
        # a profile is always disabled if profiling itself is disabled
        if not self.enabled:
            return False
        # get and check name for duplicates
        name = prof.get_name()
        if name in self.profilers:
            raise ValueError("profiler '%s' already exists!" % name)
        # setup config of profiler (if any)
        if self.cfg and name in self.cfg:
            sub_cfg = self.cfg[name]
            if not prof.parse_config(sub_cfg):
                log_prof.warning("skipped profiler '%s'", name)
                return False
        log_prof.debug("added profiler '%s'", name)
        self.profilers[name] = prof
        return True

    def get_profiler(self, name):
        if name in self.profilers:
            return self.profilers[name]

    def setup(self):
        """after adding all profilers prepare profiling (if enabled)"""
        if not self.enabled:
            return

        # if profiling enabled and neither dump nor file is enabled then dump
        if self.file is None and self.dump is False:
            log_prof.warning(
                "profiling enabled, but no output selected. enabling dump!"
            )
            self.dump = True

        # load old data for appending first?
        if self.file and self.append:
            self._try_load_data()

        # prepare all profilers
        for prof in list(self.profilers.values()):
            prof.setup()

    def shutdown(self):
        """after collecting profiling data write data or dump it"""
        # shutdown all profilers
        for prof in list(self.profilers.values()):
            prof.shutdown()

        # save data?
        if self.file:
            self._save_data()

        # dump ?
        if self.dump:
            log_prof.info("---------- Profiling Results ----------")
            for name in self.profilers:
                prof = self.profilers[name]
                log_prof.info("----- profiler '%s' -----", name)
                prof.dump(log_prof.info)

    def _try_load_data(self):
        if os.path.exists(self.file):
            log_prof.debug("loading profile data from '%s'", self.file)
            df = ProfDataFile()
            df.load_json_file(self.file)
            # run through profilers and set data
            for name in self.profilers:
                prof = self.profilers[name]
                data = df.get_prof_data(name)
                if data:
                    prof.set_data(ConfigDict(data))
            log_prof.debug("done loading.")

    def _save_data(self):
        log_prof.debug("saving profile data to '%s'", self.file)
        df = ProfDataFile()
        # run through profilers and get data
        for name in self.profilers:
            prof = self.profilers[name]
            data = prof.get_data()
            if data:
                df.set_prof_data(name, data)
        df.save_json_file(self.file)
        log_prof.debug("done saving.")
