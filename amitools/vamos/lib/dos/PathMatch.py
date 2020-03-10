from .PatternMatch import pattern_parse, pattern_match


class PathMatchChain:
    def __init__(self, lock, pattern, prefix="", parent=None):
        self.lock = lock
        self.pattern = pattern
        self.prefix = prefix
        self.parent = parent
        self.child = None
        if self.parent != None:
            self.parent.child = self

    def reset(self):
        self.pos = -1
        self.candidates = []
        if self.child != None:
            self.child.reset()

    def _join(self, a, b):
        if a == "":
            return b
        elif b == "":
            return a
        elif a[-1] in ("/", ":"):
            return a + b
        else:
            return a + "/" + b

    def next(self, path_mgr, prefix, postfix):
        full_prefix = self._join(prefix, self.prefix)

        # need candidates?
        if self.pos == -1:
            self.candidates = path_mgr.ami_list_dir(self.lock, full_prefix)
            # no dir?
            if self.candidates == None:
                return None
            self.pos = 0

        # try all candidates
        n = len(self.candidates)
        while self.pos < n:
            # get candidate and match
            name = self.candidates[self.pos]
            if pattern_match(self.pattern, name):
                if full_prefix != "":
                    ami_path = self._join(full_prefix, name)
                else:
                    ami_path = name

                # is tail?
                if self.child == None:
                    if postfix != "":
                        ami_path = self._join(ami_path, postfix)
                    if path_mgr.ami_path_exists(self.lock, ami_path):
                        self.pos += 1
                        return ami_path
                    else:
                        return None
                else:
                    # sub paths
                    match = self.child.next(path_mgr, ami_path, postfix)
                    if match != None:
                        return match

            # try next candidate
            self.pos += 1
            if self.child != None:
                self.child.reset()

        # nothing found
        return None

    def __str__(self):
        txt = "[prefix='%s' pattern='%s']" % (self.prefix, self.pattern)
        if self.child != None:
            txt += str(self.child)
        return txt


class PathMatch:
    def __init__(self, path_mgr, lock):
        self.path_mgr = path_mgr
        self.lock = lock
        self.head_chain = None

    def parse(self, in_str):
        self.head_chain = None

        # extract volume (if available)
        pos = in_str.find(":")
        if pos == -1:
            self.prefix = ""
        else:
            self.prefix = in_str[: pos + 1]
            in_str = in_str[pos + 1 :]

        # extrace preceeding slashes
        prefix_slashes = ""
        for a in in_str:
            if a != "/":
                break
            prefix_slashes += "/"
        self.prefix += prefix_slashes
        in_str = in_str[len(prefix_slashes) :]

        # split path segments by / and build chain
        segs = in_str.split("/")
        last = []
        prev_chain = None
        for s in segs:
            if s == "":
                last.append(s)
            else:
                pat = pattern_parse(s)
                if pat != None:
                    if pat.has_wildcard:
                        # prefix
                        if len(last) > 0:
                            prefix = "/".join(last)
                            last = []
                        else:
                            prefix = ""
                        chain = PathMatchChain(
                            self.lock, pat, prefix=prefix, parent=prev_chain
                        )
                        if prev_chain == None:
                            self.head_chain = chain
                        prev_chain = chain
                    else:
                        last.append(pat.pat_str)
                        # thor: even if there is no wild-card, do not append the string directly
                        # since the escape-character ' still needs to be removed
                else:
                    return False

        # postfix
        if len(last) > 0:
            self.postfix = "/".join(last)
            if len(self.postfix) > 0 and self.postfix[-1] == "/":
                self.postfix = self.postfix[:-1]
        else:
            self.postfix = ""

        return True

    def __str__(self):
        return "prefix='%s' chain=%s postfix='%s'" % (
            self.prefix,
            self.head_chain,
            self.postfix,
        )

    def has_wildcards(self):
        return self.head_chain != None

    def begin(self):
        # no wildcard?
        if self.head_chain == None:
            ami_path = self.prefix + self.postfix
            if self.path_mgr.ami_path_exists(self.lock, ami_path):
                return ami_path
            else:
                return None
        # has wildcards
        else:
            self.head_chain.reset()
            return self.head_chain.next(self.path_mgr, self.prefix, self.postfix)

    def __next__(self):
        # no wildcard?
        if self.head_chain == None:
            return None
        # has wildcards
        else:
            return self.head_chain.next(self.path_mgr, self.prefix, self.postfix)


# ----- test -----
if __name__ == "__main__":
    import sys

    pm = PathMatch(None)
    pm.parse(sys.argv[1])
    print(pm)
