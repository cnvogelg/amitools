import json


class ProfDataFile(object):
    """profiling data stored in a json file"""

    def __init__(self):
        self.data = {}

    def save_json_file(self, name):
        with open(name, "w") as fh:
            self.save_json_fobj(fh)

    def save_json_fobj(self, fobj):
        # add header key
        self.data["vamos_profile"] = "1.0"
        json.dump(self.data, fobj, sort_keys=True, indent=2)

    def load_json_file(self, name):
        with open(name, "r") as fh:
            self.load_json_fobj(fh)

    def load_json_fobj(self, fobj):
        self.data = json.load(fobj)
        assert self.data["vamos_profile"] == "1.0"

    def get_prof_data(self, prof_name):
        if prof_name in self.data:
            return self.data[prof_name]

    def set_prof_data(self, prof_name, data):
        self.data[prof_name] = data
