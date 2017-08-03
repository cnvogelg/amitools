from __future__ import print_function

import os
import sys
import setuptools.command.build_ext

from subprocess import call
from setuptools import setup, find_packages
from distutils.extension import Extension

# has cython?
try:
    from Cython.Build import cythonize
    has_cython = True
except ImportError:
    has_cython = False

# use cython?
use_cython = has_cython
if '--no-cython' in sys.argv:
    use_cython = False
    sys.argv.remove('--no-cython')
print("use_cython:", use_cython)

# if generated file is missing cython is required
ext_file = 'musashi/emu.c'
if not os.path.exists(ext_file) and not use_cython:
  print("generated cython file missing! cython is essential to proceed!")
  print("please install with: pip install cyton")
  sys.exit(1)


class BuildPyCommand(setuptools.command.build_ext.build_ext):
  """Custom build command."""

  def run(self):
    call(['make', 'do_gen'])
    setuptools.command.build_ext.build_ext.run(self)

cython_file = 'musashi/emu.pyx'
sourcefiles = [
  'musashi/traps.c',
  'musashi/mem.c',
  'musashi/m68kcpu.c',
  'musashi/m68kdasm.c',
  'gen/m68kopac.c',
  'gen/m68kopdm.c',
  'gen/m68kopnz.c',
  'gen/m68kops.c'
]
depends = [
  'musashi/pycpu.pyx',
  'musashi/pymem.pyx',
  'musashi/pytraps.pyx'
]
inc_dirs = [
  'musashi',
  'gen'
]

extensions = [Extension("musashi.emu", sourcefiles,
  depends=depends, include_dirs=inc_dirs)]

# use cython?
if use_cython:
  sourcefiles.append(cython_file)
  extensions = cythonize(extensions)
else:
  sourcefiles.append(ext_file)

scripts = {
  'console_scripts' : [
    'fdtool = amitools.tools.fdtool:main',
    'geotool = amitools.tools.geotool:main',
    'hunktool = amitools.tools.hunktool:main',
    'rdbtool = amitools.tools.rdbtool:main',
    'romtool = amitools.tools.romtool:main',
    'typetool = amitools.tools.typetool:main',
    'vamos = amitools.tools.vamos:main',
    'vamospath = amitools.tools.vamospath:main',
    'xdfscan = amitools.tools.xdfscan:main',
    'xdftool = amitools.tools.xdftool:main'
  ]
}

setup(
    cmdclass = {
        'build_ext': BuildPyCommand,
    },
    name = "amitools",
    description='A package to support development with classic Amiga m68k systems',
    long_description=open("README.md").read(),
    version = "0.1.0",
    maintainer = "Christian Vogelgsang",
    maintainer_email = "chris@vogelgsang.org",
    url = "http://github.com/cnvogelg/amitools",
    classifiers = [
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Programming Language :: Python",
        "Topic :: System :: Emulators",
    ],
    license = "License :: OSI Approved :: GNU General Public License v2 (GPLv2)",
    packages = find_packages(),
    zip_safe = False,
    entry_points = scripts,
    setup_requires = ['pytest-runner'],
    tests_require= ['pytest'],
#    install_requires = ['lhafile==0.2.1'],
    dependency_links = [
      "http://github.com/FrodeSolheim/python-lhafile/zipball/master#egg=lhafile-0.2.1"
    ],
    ext_modules = extensions,
# win problems:
#    use_scm_version=True,
    include_package_data=True
)

