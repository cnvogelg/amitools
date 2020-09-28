class Tool(object):
    def __init__(self, name, help=None):
        self.name = name
        self.help = help

    def get_name(self):
        return self.name

    def get_help(self):
        return self.help

    def add_parsers(self, main_parser):
        pass

    def add_args(self, arg_parser):
        pass

    def setup(self, args):
        return True

    def run(self, args):
        return 0

    def shutdown(self):
        pass
