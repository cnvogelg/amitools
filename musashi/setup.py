from distutils.core import setup
from Cython.Build import cythonize
from distutils.extension import Extension

sourcefiles = [
  'emu.pyx',
  'traps.c', 'mem.c',
  'm68kcpu.c', 'm68kdasm.c',
  'm68kopac.c', 'm68kopdm.c', 'm68kopnz.c', 'm68kops.c' # gen src
]
depends = [
  'pycpu.pyx', 'pymem.pyx', 'pytraps.pyx'
]

extensions = [Extension("emu", sourcefiles, depends=depends)]

setup(
    ext_modules = cythonize(extensions) #, output_dir=".", gdb_debug=True)
)
