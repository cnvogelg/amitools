import os
import sys
import subprocess

from setuptools import setup, Extension
from packaging import version
from distutils.command.build_ext import build_ext
from distutils.command.clean import clean
from distutils.core import Command
from distutils import ccompiler
from distutils.dir_util import remove_tree
from distutils import log

# has cython?
try:
    from Cython.Build import cythonize

    has_cython = True
except ImportError:
    has_cython = False

# use cython?
use_cython = has_cython
if "--no-cython" in sys.argv:
    use_cython = False
    sys.argv.remove("--no-cython")
print("use_cython:", use_cython)

# check cython version
if use_cython:
    try:
        from Cython import __version__ as cyver

        print("cython version:", cyver)
        if version.parse(cyver) < version.parse("3.0"):
            print("cython is too old < 3.0! please update first!")
            sys.exit(1)
    except ImportError:
        print("cython is too old! please update first!")
        sys.exit(1)

# if generated file is missing cython is required
ext_file = "machine/emu.c"
if not os.path.exists(ext_file) and not use_cython:
    print("generated cython file missing! cython is essential to proceed!")
    print("please install with: pip3 install cython")
    sys.exit(1)


gen_src = ["m68kopac.c", "m68kopdm.c", "m68kopnz.c", "m68kops.c"]

gen_tool = "build/m68kmake"
gen_tool_src = "machine/musashi/m68kmake.c"
gen_tool_obj = "build/machine/musashi/m68kmake.o"
gen_input = "machine/musashi/m68k_in.c"
gen_dir = "gen"
gen_src = list([os.path.join(gen_dir, x) for x in gen_src])
build_dir = "build"

# check compiler
is_msvc = sys.platform == "win32" and sys.version.lower().find("msc") != -1


class my_build_ext(build_ext):
    """overwrite build_ext to generate code first"""

    def run(self):
        self.run_command("gen")
        build_ext.run(self)


class my_clean(clean):
    """overwrite clean to clean_gen first"""

    def run(self):
        self.run_command("clean_gen")
        clean.run(self)


class GenCommand(Command):
    """my custom code generation command"""

    description = "generate code for Musashi CPU emulator"
    user_options = []

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def run(self):
        # ensure dir exists
        if not os.path.isdir(gen_dir):
            log.info("creating '{}' dir".format(gen_dir))
            os.mkdir(gen_dir)
        if not os.path.isdir(build_dir):
            log.info("creating '{}' dir".format(build_dir))
            os.mkdir(build_dir)
        # build tool first?
        if not os.path.exists(gen_tool):
            cc = ccompiler.new_compiler()
            log.info("building '{}' tool".format(gen_tool))
            # win fixes
            src = gen_tool_src.replace("/", os.path.sep)
            print("tool source:", src)
            obj = gen_tool_obj.replace(".o", cc.obj_extension)
            obj = obj.replace("/", os.path.sep)
            print("tool object:", obj)
            # compile
            if is_msvc:
                defines = [("_CRT_SECURE_NO_WARNINGS", None)]
            else:
                defines = None
            cc.compile(sources=[src], output_dir=build_dir, macros=defines)
            # link
            if is_msvc:
                ld_args = ["/MANIFEST"]
            else:
                ld_args = None
            cc.link_executable(
                objects=[obj], output_progname=gen_tool, extra_postargs=ld_args
            )
            # remove
            os.remove(obj)
        # generate source?
        if not os.path.exists(gen_src[0]):
            log.info("generating source files")
            cmd = [gen_tool, gen_dir, gen_input]
            subprocess.check_call(cmd)


class CleanGenCommand(Command):
    """my custom code generation cleanup command"""

    description = "remove generated code for Musashi CPU emulator"
    user_options = []

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def run(self):
        if os.path.exists(gen_dir):
            remove_tree(gen_dir, dry_run=self.dry_run)
        # remove tool
        if os.path.exists(gen_tool):
            os.remove(gen_tool)


# my custom commands
cmdclass = {
    "gen": GenCommand,
    "clean_gen": CleanGenCommand,
    "build_ext": my_build_ext,
    "clean": my_clean,
}
command_options = {}


cython_file = "machine/emu.pyx"
sourcefiles = [
    "machine/traps.c",
    "machine/mem.c",
    "machine/musashi/m68kcpu.c",
    "machine/musashi/m68kdasm.c",
    "machine/musashi/softfloat/softfloat.c",
    "gen/m68kops.c",
]
depends = [
    "machine/my_conf.h",
    "machine/pycpu.pyx",
    "machine/pymem.pyx",
    "machine/pytraps.pyx",
    "machine/musashi/m68k.h",
    "machine/musashi/m68kcpu.h",
    "machine/mem.h",
    "machine/traps.h",
    "machine/musashi/softfloat/mamesf.h",
    "machine/musashi/softfloat/milieu.h",
    "machine/musashi/softfloat/softfloat.h",
    "machine/musashi/softfloat/softfloat-macros",
    "machine/musashi/softfloat/softfloat-specialize",
]
inc_dirs = ["machine", "machine/musashi", "gen"]

# add missing vc headers
if is_msvc:
    inc_dirs.append("machine/win")
    defines = [("_CRT_SECURE_NO_WARNINGS", None), ("_USE_MATH_DEFINES", None)]
else:
    defines = []
# use own musashi config file
defines.append(("MUSASHI_CNF", '"my_conf.h"'))

extensions = [
    Extension(
        "machine.emu",
        sourcefiles,
        depends=depends,
        include_dirs=inc_dirs,
        define_macros=defines,
    )
]

# use cython?
if use_cython:
    sourcefiles.append(cython_file)
    extensions = cythonize(extensions, language_level="3str")
else:
    sourcefiles.append(ext_file)

setup(
    cmdclass=cmdclass,
    command_options=command_options,
    ext_modules=extensions,
)
