import os
import subprocess

PROG_BIN_DIR = "bin"
PROG_SRC_DIR = "src"
LIB_BIN_DIR = "bin/libs"
LIB_SRC_DIR = "src/libs"


class BinBuilder:
    def __init__(self, flavor, debug=False, auto_build=False):
        if flavor == "none":
            flavor = None
        self.flavor = flavor
        self.debug = debug
        self.auto_build = auto_build

    def make_prog(self, prog_name):
        return self.make_progs([prog_name])[0]

    def make_progs(self, prog_names):
        bins = {}
        for p in prog_names:
            bin_path = os.path.join(PROG_BIN_DIR, p + "_" + self.flavor)
            if self.debug:
                bin_path = bin_path + "_dbg"
            src_path = os.path.join(PROG_SRC_DIR, p + ".c")
            bins[bin_path] = src_path
        return self._build_bins(bins)

    def make_lib(self, lib_name):
        return self.make_libs([lib_name])[0]

    def make_libs(self, lib_names):
        bins = {}
        for name in lib_names:
            lib_name = name
            lib_bin_dir = LIB_BIN_DIR
            if self.flavor is not None:
                lib_bin_dir += "-" + self.flavor
            lib_name += ".library"
            bin_path = os.path.join(lib_bin_dir, lib_name)
            src_path = os.path.join(LIB_SRC_DIR, name + ".c")
            bins[bin_path] = src_path
        return self._build_bins(bins)

    def _build_bins(self, bin_paths):
        # check sources
        all_bins = []
        rebuild_bins = []
        for binp in bin_paths:
            all_bins.append(binp)
            srcp = bin_paths[binp]
            if not os.path.exists(srcp):
                raise ValueError("source does not exist: '%s'" % srcp)
            # if bin already exits check if its never
            if os.path.exists(binp):
                srct = os.path.getmtime(srcp)
                bint = os.path.getmtime(binp)
                # allow 10s delta
                if bint + 10 <= srct:
                    rebuild_bins.append(binp)
            else:
                rebuild_bins.append(binp)
                # create bin dir if its mising
                bin_dir = os.path.dirname(binp)
                if not os.path.exists(bin_dir):
                    os.makedirs(bin_dir)
        # call make to rebuild bins
        if len(rebuild_bins) > 0:
            info = " ".join(rebuild_bins)
            if self.auto_build:
                print(("BinBuilder: making", info))
                args = ["make"]
                args += rebuild_bins
                subprocess.check_call(args, stdout=subprocess.PIPE)
            else:
                raise RuntimeError("Rebuild needed for: " + info)
        return all_bins
