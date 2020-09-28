class CommandQueue:
    def __init__(self, cmd_list, sep, cmd_map):
        self.cmd_list = cmd_list
        self.sep = sep
        self.pos = 0
        self.cmd_map = cmd_map

    def get_sub_command(self):
        p = self.pos
        n = len(self.cmd_list)
        if self.pos == n:
            return None
        while p < n:
            if self.cmd_list[p] == self.sep:
                break
            p += 1
        cmd_len = p - self.pos
        cmd = self.cmd_list[self.pos : p]
        if p < n:
            p += 1
        self.pos = p
        if cmd_len == 0:
            return self.get_sub_command()
        else:
            return cmd

    def run(self):
        # get first command
        cmd_line = self.get_sub_command()
        if cmd_line == None:
            return 1
        self.cmd_line = cmd_line
        cmd = self.create_cmd_instance(cmd_line)
        if cmd == None:
            self.show_cmd_help(cmd_line[0])
            return 2

        # run first command
        exit_code = self.run_first(cmd_line, cmd)

        if exit_code == 0:
            cmd_line = self.get_sub_command()
            while cmd_line != None:
                cmd = self.create_cmd_instance(cmd_line)
                if cmd == None:
                    self.show_cmd_help(cmd_line[0])
                    return 2

                # run next command
                exit_code = self.run_next(cmd_line, cmd)
                if exit_code != 0:
                    break

                cmd_line = self.get_sub_command()
        return exit_code

    def run_first(self, cmd_line, cmd):
        return cmd.run()

    def run_next(self, cmd_line, cmd):
        return cmd.run()

    def create_cmd(self, cclass, name, opts):
        return cclass(name, opts)  # implement this!

    def create_cmd_instance(self, cmd_line):
        name = cmd_line[0]
        if name in self.cmd_map:
            if len(cmd_line) == 1:
                opts = []
            else:
                opts = cmd_line[1:]
            cclass = self.cmd_map[name]
            return self.create_cmd(cclass, name, opts)
        else:
            return None

    def show_cmd_help(self, name):
        print("INVALID COMMAND:", name)
        print("valid commands are:")
        for a in sorted(self.cmd_map):
            print("  ", a)
