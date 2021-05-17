import os
import pytest
import subprocess
import hashlib
import inspect
from .builder import BinBuilder


class VamosTestRunner:
    def __init__(
        self,
        flavor,
        vamos_bin=None,
        vamos_args=None,
        use_debug_bins=False,
        dump_file=False,
        dump_console=False,
        generate_data=False,
        auto_build=False,
    ):
        self.flavor = flavor
        self.vamos_bin = vamos_bin
        self.vamos_args = vamos_args
        self.use_debug_bins = use_debug_bins
        self.dump_file = dump_file
        self.dump_console = dump_console
        self.generate_data = generate_data
        self.bin_builder = BinBuilder(flavor, use_debug_bins, auto_build)

    def _get_data_path(self, prog_name, kw_args):
        dat_path = ["data/" + prog_name]
        if "variant" in kw_args:
            dat_path.append("_")
            dat_path.append(kw_args["variant"])
        dat_path.append(".txt")
        return "".join(dat_path)

    def make_prog(self, prog_name):
        self.bin_builder.make_prog(prog_name)

    def get_prog_bin_name(self, prog_name):
        bin_name = "curdir:bin/" + prog_name + "_" + self.flavor
        if self.use_debug_bins:
            bin_name += "_dbg"
        return bin_name

    def run_prog(self, *prog_args, **kw_args):
        """run an AmigaOS binary with vamos

        kw_args:
        - stdin = string for stdin
        - no_ts = no timestamps
        - variant = a postfix string to append to data file

        returns:
        - returncode of process
        - stdout as line array
        - stderr as line array
        """

        # ensure that prog exists
        self.make_prog(prog_args[0])

        # stdin given?
        if "stdin" in kw_args:
            stdin = kw_args["stdin"]
        else:
            stdin = None

        # timestamps?
        if "no_ts" in kw_args:
            no_ts = kw_args["no_ts"]
        else:
            no_ts = True

        # run vamos with prog
        args = [self.vamos_bin] + self.vamos_args
        if no_ts:
            args.append("--no-ts")
        if "vargs" in kw_args:
            args = args + kw_args["vargs"]

        # terminate args
        args.append("--")

        # built binaries have special prog names
        prog_name = self.get_prog_bin_name(prog_args[0])
        args.append(prog_name)
        if len(prog_args) > 1:
            args = args + list(prog_args[1:])

        # run and get stdout/stderr
        print("running:", " ".join(args))
        if stdin:
            stdin_flag = subprocess.PIPE
            stdin = stdin.encode("latin-1")
        else:
            stdin_flag = None
        p = subprocess.Popen(
            args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=stdin_flag
        )
        (stdout, stderr) = p.communicate(stdin)

        # process stdout
        stdout = stdout.decode("latin-1").splitlines()
        stderr = stderr.decode("latin-1").splitlines()

        # show?
        if self.dump_file:
            fh = open("vamos.log", "a")
            fh.write(" ".join(args) + "\n")
            fh.write("---stdout---\n")
            for line in stdout:
                fh.write(line)
                fh.write("\n")
            fh.write("---stderr---\n")
            for line in stdout:
                fh.write(line)
                fh.write("\n")
            fh.write("---end---\n")
            fh.close()

        if self.dump_console:
            print("---stdout---")
            for line in stdout:
                print(line)
            print("---stderr---")
            for line in stderr:
                print(line)
            print("---end---")

        # generate data?
        if self.generate_data:
            dat_path = self._get_data_path(prog_args[0], kw_args)
            print("wrote output to '%s'" % dat_path)
            f = open(dat_path, "w")
            for line in stdout:
                f.write(line + "\n")
            f.close()

        return (p.returncode, stdout, stderr)

    def run_prog_checked(self, *prog_args, **kw_args):
        """like run_prog() but check return value and assume its 0"""
        retcode, stdout, stderr = self.run_prog(*prog_args, **kw_args)
        if retcode != 0:
            cmd = " ".join(prog_args)
            raise subprocess.CalledProcessError(retcode, cmd)
        return stdout, stderr

    def _compare(self, got, ok):
        for i in range(len(ok)):
            assert got[i] == ok[i]
        assert len(got) == len(ok), "stdout line count differs"

    def run_prog_check_data(self, *prog_args, **kw_args):
        """like run_prog_checked() but also verify the stdout
        and compare with the corresponding data file of the suite"""
        stdout, stderr = self.run_prog_checked(*prog_args, **kw_args)
        # compare stdout with data
        dat_path = self._get_data_path(prog_args[0], kw_args)
        f = open(dat_path, "r")
        ok_stdout = []
        for l in f:
            ok_stdout.append(l.strip())
        f.close()
        self._compare(stdout, ok_stdout)
        # asser stderr to be empty
        assert stderr == []

    def run_ctx_func(self, ctx_func, tmpdir, **kw_args):
        """use test_execpy binary to run the given func in a lib context"""
        func_name = ctx_func.__name__
        # write file with code of function
        src_code = inspect.getsource(ctx_func)
        script_file = tmpdir / (func_name + "_script.py")
        script_file.write_text(src_code, "utf-8")
        # now run 'test_execpy'
        prog_args = ["test_execpy", "-c", str(script_file), func_name]
        return self.run_prog(*prog_args, **kw_args)


class VamosRunner:
    def __init__(self, vamos_bin=None, vamos_args=None):
        self.vamos_bin = vamos_bin
        self.vamos_args = vamos_args

    def run_prog(self, *prog_args, **kw_args):
        # stdin given?
        if "stdin" in kw_args:
            stdin = kw_args["stdin"]
        else:
            stdin = None

        # timestamps?
        if "no_ts" in kw_args:
            no_ts = kw_args["no_ts"]
        else:
            no_ts = True

        # run vamos with prog
        args = [self.vamos_bin] + self.vamos_args
        if no_ts:
            args.append("--no-ts")
        if "vargs" in kw_args:
            args = args + kw_args["vargs"]

        args = args + list(prog_args)

        # run and get stdout/stderr
        print("running:", " ".join(args))
        print("stdin:", stdin)
        if stdin:
            stdin_flag = subprocess.PIPE
        else:
            stdin_flag = None
        p = subprocess.Popen(
            args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=stdin_flag
        )
        (stdout, stderr) = p.communicate(stdin)

        # process stdout
        stdout = stdout.splitlines()
        stderr = stderr.splitlines()
        return (p.returncode, stdout, stderr)

    def _get_sha1(self, file_name):
        h = hashlib.sha1()
        with open(file_name, "rb") as fh:
            data = fh.read()
            h.update(data)
            return h.hexdigest()

    def skip_if_prog_not_available(self, file_name, sha1_sum=None):
        if not os.path.exists(file_name):
            pytest.skip("prog not found: " + file_name)
        if sha1_sum:
            file_sum = self._get_sha1(file_name)
            print(file_sum, file_name)
            if file_sum != sha1_sum:
                raise RuntimeError(
                    "prog wrong hash: got=%s want=%s" % (file_sum, sha1_sum)
                )

    def add_volume_or_skip(self, vol_name, vol_path):
        if not os.path.exists(vol_path):
            pytest.skip("optional volume not found: " + vol_path)
        arg = "-V{}:{}".format(vol_name, vol_path)
        self.vamos_args.append(arg)


class ToolRunner:
    def run_checked(self, tool, *prog_args, raw_output=False, return_code=0):
        ret_code, stdout, stderr = self.run(tool, *prog_args, raw_output=raw_output)
        if stderr:
            for line in stderr:
                print(line)
        if stdout:
            for line in stdout:
                print(line)
        assert ret_code == return_code
        assert len(stderr) == 0
        return stdout

    def run(self, tool, *prog_args, raw_output=False):
        # setup args
        tool_path = os.path.join("..", "bin", tool)
        if not os.path.exists(tool_path):
            pytest.skip("tool not found: " + tool_path)
        args = [tool_path] + list(prog_args)
        print("running tool:", " ".join(args))
        p = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        (stdout, stderr) = p.communicate()

        # process stdout
        if not raw_output:
            stdout = stdout.decode("latin-1").splitlines()
            stderr = stderr.decode("latin-1").splitlines()
        return (p.returncode, stdout, stderr)

    def _get_sha1(self, file_name):
        h = hashlib.sha1()
        with open(file_name, "rb") as fh:
            data = fh.read()
            h.update(data)
            return h.hexdigest()

    def skip_if_data_file_not_available(self, file_name, sha1_sum=None):
        if not os.path.exists(file_name):
            print("data file not found:", file_name)
            pytest.skip("data file not found: " + file_name)
        if sha1_sum:
            file_sum = self._get_sha1(file_name)
            print(file_sum, file_name)
            if file_sum != sha1_sum:
                raise RuntimeError(
                    "data file has wrong hash: got=%s want=%s" % (file_sum, sha1_sum)
                )
