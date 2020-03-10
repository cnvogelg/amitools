class Profiler(object):
    """base class for all profilers"""

    def get_name(self):
        """return name of profiler"""
        return "foo"

    def parse_config(self, cfg):
        """parse sub config of a  profiler (if any)"""
        return True

    def set_data(self, data_dict):
        """set the internal state from data stored in a data file"""
        return True

    def get_data(self):
        """return the internal state as a data dictionary to be stored"""
        return {}

    def setup(self):
        """prepare for profiling"""
        pass

    def shutdown(self):
        """stop profiling"""
        pass

    def dump(self, write):
        """dump the state to the given log channel"""
        pass
