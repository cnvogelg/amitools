from setuptools import setup, find_packages
from Cython.Build import cythonize
from distutils.extension import Extension

sourcefiles = [
  'musashi/emu.pyx',
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
    ext_modules = cythonize(extensions),
# win problems:
#    use_scm_version=True,
    include_package_data=True
)

