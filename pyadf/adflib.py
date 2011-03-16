'''Wrapper for adflib.h

Generated with:
/mnt/hda4/home/python/ctypesgen/trunk/ctypesgen.py -a -l adf -o adflib.py adflib.h

Do not modify this file.
'''

__docformat__ =  'restructuredtext'

# Begin preamble

import ctypes, os, sys
from ctypes import *

_int_types = (c_int16, c_int32)
if hasattr(ctypes, 'c_int64'):
    # Some builds of ctypes apparently do not have c_int64
    # defined; it's a pretty good bet that these builds do not
    # have 64-bit pointers.
    _int_types += (c_int64,)
for t in _int_types:
    if sizeof(t) == sizeof(c_size_t):
        c_ptrdiff_t = t
del t
del _int_types

class c_void(Structure):
    # c_void_p is a buggy return type, converting to int, so
    # POINTER(None) == c_void_p is actually written as
    # POINTER(c_void), so it can be treated as a real pointer.
    _fields_ = [('dummy', c_int)]

def POINTER(obj):
    p = ctypes.POINTER(obj)

    # Convert None to a real NULL pointer to work around bugs
    # in how ctypes handles None on 64-bit platforms
    if not isinstance(p.from_param, classmethod):
        def from_param(cls, x):
            if x is None:
                return cls()
            else:
                return x
        p.from_param = classmethod(from_param)

    return p

class UserString:
    def __init__(self, seq):
        if isinstance(seq, basestring):
            self.data = seq
        elif isinstance(seq, UserString):
            self.data = seq.data[:]
        else:
            self.data = str(seq)
    def __str__(self): return str(self.data)
    def __repr__(self): return repr(self.data)
    def __int__(self): return int(self.data)
    def __long__(self): return long(self.data)
    def __float__(self): return float(self.data)
    def __complex__(self): return complex(self.data)
    def __hash__(self): return hash(self.data)

    def __cmp__(self, string):
        if isinstance(string, UserString):
            return cmp(self.data, string.data)
        else:
            return cmp(self.data, string)
    def __contains__(self, char):
        return char in self.data

    def __len__(self): return len(self.data)
    def __getitem__(self, index): return self.__class__(self.data[index])
    def __getslice__(self, start, end):
        start = max(start, 0); end = max(end, 0)
        return self.__class__(self.data[start:end])

    def __add__(self, other):
        if isinstance(other, UserString):
            return self.__class__(self.data + other.data)
        elif isinstance(other, basestring):
            return self.__class__(self.data + other)
        else:
            return self.__class__(self.data + str(other))
    def __radd__(self, other):
        if isinstance(other, basestring):
            return self.__class__(other + self.data)
        else:
            return self.__class__(str(other) + self.data)
    def __mul__(self, n):
        return self.__class__(self.data*n)
    __rmul__ = __mul__
    def __mod__(self, args):
        return self.__class__(self.data % args)

    # the following methods are defined in alphabetical order:
    def capitalize(self): return self.__class__(self.data.capitalize())
    def center(self, width, *args):
        return self.__class__(self.data.center(width, *args))
    def count(self, sub, start=0, end=sys.maxint):
        return self.data.count(sub, start, end)
    def decode(self, encoding=None, errors=None): # XXX improve this?
        if encoding:
            if errors:
                return self.__class__(self.data.decode(encoding, errors))
            else:
                return self.__class__(self.data.decode(encoding))
        else:
            return self.__class__(self.data.decode())
    def encode(self, encoding=None, errors=None): # XXX improve this?
        if encoding:
            if errors:
                return self.__class__(self.data.encode(encoding, errors))
            else:
                return self.__class__(self.data.encode(encoding))
        else:
            return self.__class__(self.data.encode())
    def endswith(self, suffix, start=0, end=sys.maxint):
        return self.data.endswith(suffix, start, end)
    def expandtabs(self, tabsize=8):
        return self.__class__(self.data.expandtabs(tabsize))
    def find(self, sub, start=0, end=sys.maxint):
        return self.data.find(sub, start, end)
    def index(self, sub, start=0, end=sys.maxint):
        return self.data.index(sub, start, end)
    def isalpha(self): return self.data.isalpha()
    def isalnum(self): return self.data.isalnum()
    def isdecimal(self): return self.data.isdecimal()
    def isdigit(self): return self.data.isdigit()
    def islower(self): return self.data.islower()
    def isnumeric(self): return self.data.isnumeric()
    def isspace(self): return self.data.isspace()
    def istitle(self): return self.data.istitle()
    def isupper(self): return self.data.isupper()
    def join(self, seq): return self.data.join(seq)
    def ljust(self, width, *args):
        return self.__class__(self.data.ljust(width, *args))
    def lower(self): return self.__class__(self.data.lower())
    def lstrip(self, chars=None): return self.__class__(self.data.lstrip(chars))
    def partition(self, sep):
        return self.data.partition(sep)
    def replace(self, old, new, maxsplit=-1):
        return self.__class__(self.data.replace(old, new, maxsplit))
    def rfind(self, sub, start=0, end=sys.maxint):
        return self.data.rfind(sub, start, end)
    def rindex(self, sub, start=0, end=sys.maxint):
        return self.data.rindex(sub, start, end)
    def rjust(self, width, *args):
        return self.__class__(self.data.rjust(width, *args))
    def rpartition(self, sep):
        return self.data.rpartition(sep)
    def rstrip(self, chars=None): return self.__class__(self.data.rstrip(chars))
    def split(self, sep=None, maxsplit=-1):
        return self.data.split(sep, maxsplit)
    def rsplit(self, sep=None, maxsplit=-1):
        return self.data.rsplit(sep, maxsplit)
    def splitlines(self, keepends=0): return self.data.splitlines(keepends)
    def startswith(self, prefix, start=0, end=sys.maxint):
        return self.data.startswith(prefix, start, end)
    def strip(self, chars=None): return self.__class__(self.data.strip(chars))
    def swapcase(self): return self.__class__(self.data.swapcase())
    def title(self): return self.__class__(self.data.title())
    def translate(self, *args):
        return self.__class__(self.data.translate(*args))
    def upper(self): return self.__class__(self.data.upper())
    def zfill(self, width): return self.__class__(self.data.zfill(width))

class MutableString(UserString):
    """mutable string objects

    Python strings are immutable objects.  This has the advantage, that
    strings may be used as dictionary keys.  If this property isn't needed
    and you insist on changing string values in place instead, you may cheat
    and use MutableString.

    But the purpose of this class is an educational one: to prevent
    people from inventing their own mutable string class derived
    from UserString and than forget thereby to remove (override) the
    __hash__ method inherited from UserString.  This would lead to
    errors that would be very hard to track down.

    A faster and better solution is to rewrite your program using lists."""
    def __init__(self, string=""):
        self.data = string
    def __hash__(self):
        raise TypeError("unhashable type (it is mutable)")
    def __setitem__(self, index, sub):
        if index < 0:
            index += len(self.data)
        if index < 0 or index >= len(self.data): raise IndexError
        self.data = self.data[:index] + sub + self.data[index+1:]
    def __delitem__(self, index):
        if index < 0:
            index += len(self.data)
        if index < 0 or index >= len(self.data): raise IndexError
        self.data = self.data[:index] + self.data[index+1:]
    def __setslice__(self, start, end, sub):
        start = max(start, 0); end = max(end, 0)
        if isinstance(sub, UserString):
            self.data = self.data[:start]+sub.data+self.data[end:]
        elif isinstance(sub, basestring):
            self.data = self.data[:start]+sub+self.data[end:]
        else:
            self.data =  self.data[:start]+str(sub)+self.data[end:]
    def __delslice__(self, start, end):
        start = max(start, 0); end = max(end, 0)
        self.data = self.data[:start] + self.data[end:]
    def immutable(self):
        return UserString(self.data)
    def __iadd__(self, other):
        if isinstance(other, UserString):
            self.data += other.data
        elif isinstance(other, basestring):
            self.data += other
        else:
            self.data += str(other)
        return self
    def __imul__(self, n):
        self.data *= n
        return self

class String(MutableString, Union):

    _fields_ = [('raw', POINTER(c_char)),
                ('data', c_char_p)]

    def __init__(self, obj=""):
        if isinstance(obj, (str, unicode, UserString)):
            self.data = str(obj)
        else:
            self.raw = obj

    def __len__(self):
        return self.data and len(self.data) or 0

    def from_param(cls, obj):
        # Convert None or 0
        if obj is None or obj == 0:
            return cls(POINTER(c_char)())

        # Convert from String
        elif isinstance(obj, String):
            return obj

        # Convert from str
        elif isinstance(obj, str):
            return cls(obj)

        # Convert from c_char_p
        elif isinstance(obj, c_char_p):
            return obj

        # Convert from POINTER(c_char)
        elif isinstance(obj, POINTER(c_char)):
            return obj

        # Convert from raw pointer
        elif isinstance(obj, int):
            return cls(cast(obj, POINTER(c_char)))

        # Convert from object
        else:
            return String.from_param(obj._as_parameter_)
    from_param = classmethod(from_param)

def ReturnString(obj, func, arguments):
    return String.from_param(obj)

# As of ctypes 1.0, ctypes does not support custom error-checking
# functions on callbacks, nor does it support custom datatypes on
# callbacks, so we must ensure that all callbacks return
# primitive datatypes.
#
# Non-primitive return values wrapped with UNCHECKED won't be
# typechecked, and will be converted to c_void_p.
def UNCHECKED(type):
    if (hasattr(type, "_type_") and isinstance(type._type_, str)
        and type._type_ != "P"):
        return type
    else:
        return c_void_p

# ctypes doesn't have direct support for variadic functions, so we have to write
# our own wrapper class
class _variadic_function(object):
    def __init__(self,func,restype,argtypes):
        self.func=func
        self.func.restype=restype
        self.argtypes=argtypes
    def _as_parameter_(self):
        # So we can pass this variadic function as a function pointer
        return self.func
    def __call__(self,*args):
        fixed_args=[]
        i=0
        for argtype in self.argtypes:
            # Typecheck what we can
            fixed_args.append(argtype.from_param(args[i]))
            i+=1
        return self.func(*fixed_args+list(args[i:]))

# End preamble

_libs = {}
_libdirs = []

# Begin loader

# ----------------------------------------------------------------------------
# Copyright (c) 2008 David James
# Copyright (c) 2006-2008 Alex Holkner
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
#
#  * Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
#  * Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in
#    the documentation and/or other materials provided with the
#    distribution.
#  * Neither the name of pyglet nor the names of its
#    contributors may be used to endorse or promote products
#    derived from this software without specific prior written
#    permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS
# FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE
# COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT,
# INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING,
# BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
# LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN
# ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.
# ----------------------------------------------------------------------------

import os.path, re, sys, glob
import ctypes
import ctypes.util

def _environ_path(name):
    if name in os.environ:
        return os.environ[name].split(":")
    else:
        return []

class LibraryLoader(object):
    def __init__(self):
        self.other_dirs=[]

    def load_library(self,libname):
        """Given the name of a library, load it."""
        paths = self.getpaths(libname)

        for path in paths:
            if os.path.exists(path):
                return self.load(path)

        raise ImportError("%s not found." % libname)

    def load(self,path):
        """Given a path to a library, load it."""
        try:
            # Darwin requires dlopen to be called with mode RTLD_GLOBAL instead
            # of the default RTLD_LOCAL.  Without this, you end up with
            # libraries not being loadable, resulting in "Symbol not found"
            # errors
            if sys.platform == 'darwin':
                return ctypes.CDLL(path, ctypes.RTLD_GLOBAL)
            else:
                return ctypes.cdll.LoadLibrary(path)
        except OSError,e:
            raise ImportError(e)

    def getpaths(self,libname):
        """Return a list of paths where the library might be found."""
        if os.path.isabs(libname):
            yield libname

        else:
            for path in self.getplatformpaths(libname):
                yield path

            path = ctypes.util.find_library(libname)
            if path: yield path

    def getplatformpaths(self, libname):
        return []

# Darwin (Mac OS X)

class DarwinLibraryLoader(LibraryLoader):
    name_formats = ["lib%s.dylib", "lib%s.so", "lib%s.bundle", "%s.dylib",
                "%s.so", "%s.bundle", "%s"]

    def getplatformpaths(self,libname):
        if os.path.pathsep in libname:
            names = [libname]
        else:
            names = [format % libname for format in self.name_formats]

        for dir in self.getdirs(libname):
            for name in names:
                yield os.path.join(dir,name)

    def getdirs(self,libname):
        '''Implements the dylib search as specified in Apple documentation:

        http://developer.apple.com/documentation/DeveloperTools/Conceptual/
            DynamicLibraries/Articles/DynamicLibraryUsageGuidelines.html

        Before commencing the standard search, the method first checks
        the bundle's ``Frameworks`` directory if the application is running
        within a bundle (OS X .app).
        '''

        dyld_fallback_library_path = _environ_path("DYLD_FALLBACK_LIBRARY_PATH")
        if not dyld_fallback_library_path:
            dyld_fallback_library_path = [os.path.expanduser('~/lib'),
                                          '/usr/local/lib', '/usr/lib']

        dirs = []

        if '/' in libname:
            dirs.extend(_environ_path("DYLD_LIBRARY_PATH"))
        else:
            dirs.extend(_environ_path("LD_LIBRARY_PATH"))
            dirs.extend(_environ_path("DYLD_LIBRARY_PATH"))

        dirs.extend(self.other_dirs)
        dirs.append(".")

        if hasattr(sys, 'frozen') and sys.frozen == 'macosx_app':
            dirs.append(os.path.join(
                os.environ['RESOURCEPATH'],
                '..',
                'Frameworks'))

        dirs.extend(dyld_fallback_library_path)

        return dirs

# Posix

class PosixLibraryLoader(LibraryLoader):
    _ld_so_cache = None

    def _create_ld_so_cache(self):
        # Recreate search path followed by ld.so.  This is going to be
        # slow to build, and incorrect (ld.so uses ld.so.cache, which may
        # not be up-to-date).  Used only as fallback for distros without
        # /sbin/ldconfig.
        #
        # We assume the DT_RPATH and DT_RUNPATH binary sections are omitted.

        directories = []
        for name in ("LD_LIBRARY_PATH",
                     "SHLIB_PATH", # HPUX
                     "LIBPATH", # OS/2, AIX
                     "LIBRARY_PATH", # BE/OS
                    ):
            if name in os.environ:
                directories.extend(os.environ[name].split(os.pathsep))
        directories.extend(self.other_dirs)
        directories.append(".")

        try: directories.extend([dir.strip() for dir in open('/etc/ld.so.conf')])
        except IOError: pass

        directories.extend(['/lib', '/usr/lib', '/lib64', '/usr/lib64'])

        cache = {}
        lib_re = re.compile(r'lib(.*)\.s[ol]')
        ext_re = re.compile(r'\.s[ol]$')
        for dir in directories:
            try:
                for path in glob.glob("%s/*.s[ol]*" % dir):
                    file = os.path.basename(path)

                    # Index by filename
                    if file not in cache:
                        cache[file] = path

                    # Index by library name
                    match = lib_re.match(file)
                    if match:
                        library = match.group(1)
                        if library not in cache:
                            cache[library] = path
            except OSError:
                pass

        self._ld_so_cache = cache

    def getplatformpaths(self, libname):
        if self._ld_so_cache is None:
            self._create_ld_so_cache()

        result = self._ld_so_cache.get(libname)
        if result: yield result

        path = ctypes.util.find_library(libname)
        if path: yield os.path.join("/lib",path)

# Windows

class _WindowsLibrary(object):
    def __init__(self, path):
        self.cdll = ctypes.cdll.LoadLibrary(path)
        self.windll = ctypes.windll.LoadLibrary(path)

    def __getattr__(self, name):
        try: return getattr(self.cdll,name)
        except AttributeError:
            try: return getattr(self.windll,name)
            except AttributeError:
                raise

class WindowsLibraryLoader(LibraryLoader):
    name_formats = ["%s.dll", "lib%s.dll", "%slib.dll"]

    def load_library(self, libname):
        try:
            result = LibraryLoader.load_library(self, libname)
        except ImportError:
            result = None
            if os.path.sep not in libname:
                for name in self.name_formats:
                    try:
                        result = getattr(ctypes.cdll, name % libname)
                        if result:
                            break
                    except WindowsError:
                        result = None
            if result is None:
                try:
                    result = getattr(ctypes.cdll, libname)
                except WindowsError:
                    result = None
            if result is None:
                raise ImportError("%s not found." % libname)
        return result

    def load(self, path):
        return _WindowsLibrary(path)

    def getplatformpaths(self, libname):
        if os.path.sep not in libname:
            for name in self.name_formats:
                path = ctypes.util.find_library(name % libname)
                if path:
                    yield path

# Platform switching

# If your value of sys.platform does not appear in this dict, please contact
# the Ctypesgen maintainers.

loaderclass = {
    "darwin":   DarwinLibraryLoader,
    "cygwin":   WindowsLibraryLoader,
    "win32":    WindowsLibraryLoader
}

loader = loaderclass.get(sys.platform, PosixLibraryLoader)()

def add_library_search_dirs(other_dirs):
    loader.other_dirs = other_dirs

load_library = loader.load_library

del loaderclass

# End loader

add_library_search_dirs([])

# Begin libraries

_libs["adf"] = load_library("adf")

# 1 libraries
# End libraries

# No modules

int8_t = c_char # /usr/include/stdint.h: 37

int16_t = c_int # /usr/include/stdint.h: 38

int32_t = c_int # /usr/include/stdint.h: 39

int64_t = c_longlong # /usr/include/stdint.h: 44

uint8_t = c_ubyte # /usr/include/stdint.h: 49

uint16_t = c_uint # /usr/include/stdint.h: 50

uint32_t = c_uint # /usr/include/stdint.h: 52

uint64_t = c_ulonglong # /usr/include/stdint.h: 59

int_least8_t = c_char # /usr/include/stdint.h: 66

int_least16_t = c_int # /usr/include/stdint.h: 67

int_least32_t = c_int # /usr/include/stdint.h: 68

int_least64_t = c_longlong # /usr/include/stdint.h: 73

uint_least8_t = c_ubyte # /usr/include/stdint.h: 77

uint_least16_t = c_uint # /usr/include/stdint.h: 78

uint_least32_t = c_uint # /usr/include/stdint.h: 79

uint_least64_t = c_ulonglong # /usr/include/stdint.h: 84

int_fast8_t = c_char # /usr/include/stdint.h: 91

int_fast16_t = c_int # /usr/include/stdint.h: 97

int_fast32_t = c_int # /usr/include/stdint.h: 98

int_fast64_t = c_longlong # /usr/include/stdint.h: 100

uint_fast8_t = c_ubyte # /usr/include/stdint.h: 104

uint_fast16_t = c_uint # /usr/include/stdint.h: 110

uint_fast32_t = c_uint # /usr/include/stdint.h: 111

uint_fast64_t = c_ulonglong # /usr/include/stdint.h: 113

intptr_t = c_int # /usr/include/stdint.h: 126

uintptr_t = c_uint # /usr/include/stdint.h: 129

intmax_t = c_longlong # /usr/include/stdint.h: 139

uintmax_t = c_ulonglong # /usr/include/stdint.h: 141

__u_char = c_ubyte # /usr/include/bits/types.h: 31

__u_short = c_uint # /usr/include/bits/types.h: 32

__u_int = c_uint # /usr/include/bits/types.h: 33

__u_long = c_ulong # /usr/include/bits/types.h: 34

__int8_t = c_char # /usr/include/bits/types.h: 37

__uint8_t = c_ubyte # /usr/include/bits/types.h: 38

__int16_t = c_int # /usr/include/bits/types.h: 39

__uint16_t = c_uint # /usr/include/bits/types.h: 40

__int32_t = c_int # /usr/include/bits/types.h: 41

__uint32_t = c_uint # /usr/include/bits/types.h: 42

# /usr/include/bits/types.h: 62
class struct_anon_1(Structure):
    pass

struct_anon_1.__slots__ = [
    '__val',
]
struct_anon_1._fields_ = [
    ('__val', c_long * 2),
]

__quad_t = struct_anon_1 # /usr/include/bits/types.h: 62

# /usr/include/bits/types.h: 66
class struct_anon_2(Structure):
    pass

struct_anon_2.__slots__ = [
    '__val',
]
struct_anon_2._fields_ = [
    ('__val', __u_long * 2),
]

__u_quad_t = struct_anon_2 # /usr/include/bits/types.h: 66

__dev_t = __u_quad_t # /usr/include/bits/types.h: 134

__uid_t = c_uint # /usr/include/bits/types.h: 135

__gid_t = c_uint # /usr/include/bits/types.h: 136

__ino_t = c_ulong # /usr/include/bits/types.h: 137

__ino64_t = __u_quad_t # /usr/include/bits/types.h: 138

__mode_t = c_uint # /usr/include/bits/types.h: 139

__nlink_t = c_uint # /usr/include/bits/types.h: 140

__off_t = c_long # /usr/include/bits/types.h: 141

__off64_t = __quad_t # /usr/include/bits/types.h: 142

__pid_t = c_int # /usr/include/bits/types.h: 143

# /usr/include/bits/types.h: 144
class struct_anon_3(Structure):
    pass

struct_anon_3.__slots__ = [
    '__val',
]
struct_anon_3._fields_ = [
    ('__val', c_int * 2),
]

__fsid_t = struct_anon_3 # /usr/include/bits/types.h: 144

__clock_t = c_long # /usr/include/bits/types.h: 145

__rlim_t = c_ulong # /usr/include/bits/types.h: 146

__rlim64_t = __u_quad_t # /usr/include/bits/types.h: 147

__id_t = c_uint # /usr/include/bits/types.h: 148

__time_t = c_long # /usr/include/bits/types.h: 149

__useconds_t = c_uint # /usr/include/bits/types.h: 150

__suseconds_t = c_long # /usr/include/bits/types.h: 151

__daddr_t = c_int # /usr/include/bits/types.h: 153

__swblk_t = c_long # /usr/include/bits/types.h: 154

__key_t = c_int # /usr/include/bits/types.h: 155

__clockid_t = c_int # /usr/include/bits/types.h: 158

__timer_t = POINTER(None) # /usr/include/bits/types.h: 161

__blksize_t = c_long # /usr/include/bits/types.h: 164

__blkcnt_t = c_long # /usr/include/bits/types.h: 169

__blkcnt64_t = __quad_t # /usr/include/bits/types.h: 170

__fsblkcnt_t = c_ulong # /usr/include/bits/types.h: 173

__fsblkcnt64_t = __u_quad_t # /usr/include/bits/types.h: 174

__fsfilcnt_t = c_ulong # /usr/include/bits/types.h: 177

__fsfilcnt64_t = __u_quad_t # /usr/include/bits/types.h: 178

__ssize_t = c_int # /usr/include/bits/types.h: 180

__loff_t = __off64_t # /usr/include/bits/types.h: 184

__qaddr_t = POINTER(__quad_t) # /usr/include/bits/types.h: 185

__caddr_t = String # /usr/include/bits/types.h: 186

__intptr_t = c_int # /usr/include/bits/types.h: 189

__socklen_t = c_uint # /usr/include/bits/types.h: 192

# /usr/include/libio.h: 271
class struct__IO_FILE(Structure):
    pass

FILE = struct__IO_FILE # /usr/include/stdio.h: 49

__FILE = struct__IO_FILE # /usr/include/stdio.h: 65

# /usr/include/wchar.h: 81
class union_anon_4(Union):
    pass

union_anon_4.__slots__ = [
    '__wch',
    '__wchb',
]
union_anon_4._fields_ = [
    ('__wch', c_uint),
    ('__wchb', c_char * 4),
]

# /usr/include/wchar.h: 90
class struct_anon_5(Structure):
    pass

struct_anon_5.__slots__ = [
    '__count',
    '__value',
]
struct_anon_5._fields_ = [
    ('__count', c_int),
    ('__value', union_anon_4),
]

__mbstate_t = struct_anon_5 # /usr/include/wchar.h: 90

# /usr/include/_G_config.h: 26
class struct_anon_6(Structure):
    pass

struct_anon_6.__slots__ = [
    '__pos',
    '__state',
]
struct_anon_6._fields_ = [
    ('__pos', __off_t),
    ('__state', __mbstate_t),
]

_G_fpos_t = struct_anon_6 # /usr/include/_G_config.h: 26

# /usr/include/_G_config.h: 31
class struct_anon_7(Structure):
    pass

struct_anon_7.__slots__ = [
    '__pos',
    '__state',
]
struct_anon_7._fields_ = [
    ('__pos', __off64_t),
    ('__state', __mbstate_t),
]

_G_fpos64_t = struct_anon_7 # /usr/include/_G_config.h: 31

_G_int16_t = c_int # /usr/include/_G_config.h: 53

_G_int32_t = c_int # /usr/include/_G_config.h: 54

_G_uint16_t = c_uint # /usr/include/_G_config.h: 55

_G_uint32_t = c_uint # /usr/include/_G_config.h: 56

# /usr/include/libio.h: 170
class struct__IO_jump_t(Structure):
    pass

_IO_lock_t = None # /usr/include/libio.h: 180

# /usr/include/libio.h: 186
class struct__IO_marker(Structure):
    pass

struct__IO_marker.__slots__ = [
    '_next',
    '_sbuf',
    '_pos',
]
struct__IO_marker._fields_ = [
    ('_next', POINTER(struct__IO_marker)),
    ('_sbuf', POINTER(struct__IO_FILE)),
    ('_pos', c_int),
]

enum___codecvt_result = c_int # /usr/include/libio.h: 206

__codecvt_ok = 0 # /usr/include/libio.h: 206

__codecvt_partial = (__codecvt_ok + 1) # /usr/include/libio.h: 206

__codecvt_error = (__codecvt_partial + 1) # /usr/include/libio.h: 206

__codecvt_noconv = (__codecvt_error + 1) # /usr/include/libio.h: 206

struct__IO_FILE.__slots__ = [
    '_flags',
    '_IO_read_ptr',
    '_IO_read_end',
    '_IO_read_base',
    '_IO_write_base',
    '_IO_write_ptr',
    '_IO_write_end',
    '_IO_buf_base',
    '_IO_buf_end',
    '_IO_save_base',
    '_IO_backup_base',
    '_IO_save_end',
    '_markers',
    '_chain',
    '_fileno',
    '_flags2',
    '_old_offset',
    '_cur_column',
    '_vtable_offset',
    '_shortbuf',
    '_lock',
    '_offset',
    '__pad1',
    '__pad2',
    '__pad3',
    '__pad4',
    '__pad5',
    '_mode',
    '_unused2',
]
struct__IO_FILE._fields_ = [
    ('_flags', c_int),
    ('_IO_read_ptr', String),
    ('_IO_read_end', String),
    ('_IO_read_base', String),
    ('_IO_write_base', String),
    ('_IO_write_ptr', String),
    ('_IO_write_end', String),
    ('_IO_buf_base', String),
    ('_IO_buf_end', String),
    ('_IO_save_base', String),
    ('_IO_backup_base', String),
    ('_IO_save_end', String),
    ('_markers', POINTER(struct__IO_marker)),
    ('_chain', POINTER(struct__IO_FILE)),
    ('_fileno', c_int),
    ('_flags2', c_int),
    ('_old_offset', __off_t),
    ('_cur_column', c_ushort),
    ('_vtable_offset', c_char),
    ('_shortbuf', c_char * 1),
    ('_lock', POINTER(_IO_lock_t)),
    ('_offset', __off64_t),
    ('__pad1', POINTER(None)),
    ('__pad2', POINTER(None)),
    ('__pad3', POINTER(None)),
    ('__pad4', POINTER(None)),
    ('__pad5', c_size_t),
    ('_mode', c_int),
    ('_unused2', c_char * (((15 * sizeof(c_int)) - (4 * sizeof(POINTER(None)))) - sizeof(c_size_t))),
]

_IO_FILE = struct__IO_FILE # /usr/include/libio.h: 341

# /usr/include/libio.h: 344
class struct__IO_FILE_plus(Structure):
    pass

# /usr/include/libio.h: 346
for _lib in _libs.values():
    try:
        _IO_2_1_stdin_ = (struct__IO_FILE_plus).in_dll(_lib, '_IO_2_1_stdin_')
        break
    except:
        pass

# /usr/include/libio.h: 347
for _lib in _libs.values():
    try:
        _IO_2_1_stdout_ = (struct__IO_FILE_plus).in_dll(_lib, '_IO_2_1_stdout_')
        break
    except:
        pass

# /usr/include/libio.h: 348
for _lib in _libs.values():
    try:
        _IO_2_1_stderr_ = (struct__IO_FILE_plus).in_dll(_lib, '_IO_2_1_stderr_')
        break
    except:
        pass

__io_read_fn = CFUNCTYPE(UNCHECKED(__ssize_t), POINTER(None), String, c_size_t) # /usr/include/libio.h: 364

__io_write_fn = CFUNCTYPE(UNCHECKED(__ssize_t), POINTER(None), String, c_size_t) # /usr/include/libio.h: 372

__io_seek_fn = CFUNCTYPE(UNCHECKED(c_int), POINTER(None), POINTER(__off64_t), c_int) # /usr/include/libio.h: 381

__io_close_fn = CFUNCTYPE(UNCHECKED(c_int), POINTER(None)) # /usr/include/libio.h: 384

# /usr/include/libio.h: 416
for _lib in _libs.values():
    if hasattr(_lib, '__underflow'):
        __underflow = _lib.__underflow
        __underflow.restype = c_int
        __underflow.argtypes = [POINTER(_IO_FILE)]
        break

# /usr/include/libio.h: 417
for _lib in _libs.values():
    if hasattr(_lib, '__uflow'):
        __uflow = _lib.__uflow
        __uflow.restype = c_int
        __uflow.argtypes = [POINTER(_IO_FILE)]
        break

# /usr/include/libio.h: 418
for _lib in _libs.values():
    if hasattr(_lib, '__overflow'):
        __overflow = _lib.__overflow
        __overflow.restype = c_int
        __overflow.argtypes = [POINTER(_IO_FILE), c_int]
        break

# /usr/include/libio.h: 458
for _lib in _libs.values():
    if hasattr(_lib, '_IO_getc'):
        _IO_getc = _lib._IO_getc
        _IO_getc.restype = c_int
        _IO_getc.argtypes = [POINTER(_IO_FILE)]
        break

# /usr/include/libio.h: 459
for _lib in _libs.values():
    if hasattr(_lib, '_IO_putc'):
        _IO_putc = _lib._IO_putc
        _IO_putc.restype = c_int
        _IO_putc.argtypes = [c_int, POINTER(_IO_FILE)]
        break

# /usr/include/libio.h: 460
for _lib in _libs.values():
    if hasattr(_lib, '_IO_feof'):
        _IO_feof = _lib._IO_feof
        _IO_feof.restype = c_int
        _IO_feof.argtypes = [POINTER(_IO_FILE)]
        break

# /usr/include/libio.h: 461
for _lib in _libs.values():
    if hasattr(_lib, '_IO_ferror'):
        _IO_ferror = _lib._IO_ferror
        _IO_ferror.restype = c_int
        _IO_ferror.argtypes = [POINTER(_IO_FILE)]
        break

# /usr/include/libio.h: 463
for _lib in _libs.values():
    if hasattr(_lib, '_IO_peekc_locked'):
        _IO_peekc_locked = _lib._IO_peekc_locked
        _IO_peekc_locked.restype = c_int
        _IO_peekc_locked.argtypes = [POINTER(_IO_FILE)]
        break

# /usr/include/libio.h: 469
for _lib in _libs.values():
    if hasattr(_lib, '_IO_flockfile'):
        _IO_flockfile = _lib._IO_flockfile
        _IO_flockfile.restype = None
        _IO_flockfile.argtypes = [POINTER(_IO_FILE)]
        break

# /usr/include/libio.h: 470
for _lib in _libs.values():
    if hasattr(_lib, '_IO_funlockfile'):
        _IO_funlockfile = _lib._IO_funlockfile
        _IO_funlockfile.restype = None
        _IO_funlockfile.argtypes = [POINTER(_IO_FILE)]
        break

# /usr/include/libio.h: 471
for _lib in _libs.values():
    if hasattr(_lib, '_IO_ftrylockfile'):
        _IO_ftrylockfile = _lib._IO_ftrylockfile
        _IO_ftrylockfile.restype = c_int
        _IO_ftrylockfile.argtypes = [POINTER(_IO_FILE)]
        break

# /usr/include/libio.h: 492
for _lib in _libs.values():
    if hasattr(_lib, '_IO_padn'):
        _IO_padn = _lib._IO_padn
        _IO_padn.restype = __ssize_t
        _IO_padn.argtypes = [POINTER(_IO_FILE), c_int, __ssize_t]
        break

# /usr/include/libio.h: 493
for _lib in _libs.values():
    if hasattr(_lib, '_IO_sgetn'):
        _IO_sgetn = _lib._IO_sgetn
        _IO_sgetn.restype = c_size_t
        _IO_sgetn.argtypes = [POINTER(_IO_FILE), POINTER(None), c_size_t]
        break

# /usr/include/libio.h: 495
for _lib in _libs.values():
    if hasattr(_lib, '_IO_seekoff'):
        _IO_seekoff = _lib._IO_seekoff
        _IO_seekoff.restype = __off64_t
        _IO_seekoff.argtypes = [POINTER(_IO_FILE), __off64_t, c_int, c_int]
        break

# /usr/include/libio.h: 496
for _lib in _libs.values():
    if hasattr(_lib, '_IO_seekpos'):
        _IO_seekpos = _lib._IO_seekpos
        _IO_seekpos.restype = __off64_t
        _IO_seekpos.argtypes = [POINTER(_IO_FILE), __off64_t, c_int]
        break

# /usr/include/libio.h: 498
for _lib in _libs.values():
    if hasattr(_lib, '_IO_free_backup_area'):
        _IO_free_backup_area = _lib._IO_free_backup_area
        _IO_free_backup_area.restype = None
        _IO_free_backup_area.argtypes = [POINTER(_IO_FILE)]
        break

fpos_t = _G_fpos_t # /usr/include/stdio.h: 91

# /usr/include/stdio.h: 145
for _lib in _libs.values():
    try:
        stdin = (POINTER(struct__IO_FILE)).in_dll(_lib, 'stdin')
        break
    except:
        pass

# /usr/include/stdio.h: 146
for _lib in _libs.values():
    try:
        stdout = (POINTER(struct__IO_FILE)).in_dll(_lib, 'stdout')
        break
    except:
        pass

# /usr/include/stdio.h: 147
for _lib in _libs.values():
    try:
        stderr = (POINTER(struct__IO_FILE)).in_dll(_lib, 'stderr')
        break
    except:
        pass

# /usr/include/stdio.h: 155
for _lib in _libs.values():
    if hasattr(_lib, 'remove'):
        remove = _lib.remove
        remove.restype = c_int
        remove.argtypes = [String]
        break

# /usr/include/stdio.h: 157
for _lib in _libs.values():
    if hasattr(_lib, 'rename'):
        rename = _lib.rename
        rename.restype = c_int
        rename.argtypes = [String, String]
        break

# /usr/include/stdio.h: 172
for _lib in _libs.values():
    if hasattr(_lib, 'tmpfile'):
        tmpfile = _lib.tmpfile
        tmpfile.restype = POINTER(FILE)
        tmpfile.argtypes = []
        break

# /usr/include/stdio.h: 186
for _lib in _libs.values():
    if hasattr(_lib, 'tmpnam'):
        tmpnam = _lib.tmpnam
        tmpnam.restype = String
        tmpnam.argtypes = [String]
        tmpnam.errcheck = ReturnString
        break

# /usr/include/stdio.h: 192
for _lib in _libs.values():
    if hasattr(_lib, 'tmpnam_r'):
        tmpnam_r = _lib.tmpnam_r
        tmpnam_r.restype = String
        tmpnam_r.argtypes = [String]
        tmpnam_r.errcheck = ReturnString
        break

# /usr/include/stdio.h: 204
for _lib in _libs.values():
    if hasattr(_lib, 'tempnam'):
        tempnam = _lib.tempnam
        tempnam.restype = String
        tempnam.argtypes = [String, String]
        tempnam.errcheck = ReturnString
        break

# /usr/include/stdio.h: 214
for _lib in _libs.values():
    if hasattr(_lib, 'fclose'):
        fclose = _lib.fclose
        fclose.restype = c_int
        fclose.argtypes = [POINTER(FILE)]
        break

# /usr/include/stdio.h: 219
for _lib in _libs.values():
    if hasattr(_lib, 'fflush'):
        fflush = _lib.fflush
        fflush.restype = c_int
        fflush.argtypes = [POINTER(FILE)]
        break

# /usr/include/stdio.h: 229
for _lib in _libs.values():
    if hasattr(_lib, 'fflush_unlocked'):
        fflush_unlocked = _lib.fflush_unlocked
        fflush_unlocked.restype = c_int
        fflush_unlocked.argtypes = [POINTER(FILE)]
        break

# /usr/include/stdio.h: 249
for _lib in _libs.values():
    if hasattr(_lib, 'fopen'):
        fopen = _lib.fopen
        fopen.restype = POINTER(FILE)
        fopen.argtypes = [String, String]
        break

# /usr/include/stdio.h: 255
for _lib in _libs.values():
    if hasattr(_lib, 'freopen'):
        freopen = _lib.freopen
        freopen.restype = POINTER(FILE)
        freopen.argtypes = [String, String, POINTER(FILE)]
        break

# /usr/include/stdio.h: 283
for _lib in _libs.values():
    if hasattr(_lib, 'fdopen'):
        fdopen = _lib.fdopen
        fdopen.restype = POINTER(FILE)
        fdopen.argtypes = [c_int, String]
        break

# /usr/include/stdio.h: 307
for _lib in _libs.values():
    if hasattr(_lib, 'setbuf'):
        setbuf = _lib.setbuf
        setbuf.restype = None
        setbuf.argtypes = [POINTER(FILE), String]
        break

# /usr/include/stdio.h: 311
for _lib in _libs.values():
    if hasattr(_lib, 'setvbuf'):
        setvbuf = _lib.setvbuf
        setvbuf.restype = c_int
        setvbuf.argtypes = [POINTER(FILE), String, c_int, c_size_t]
        break

# /usr/include/stdio.h: 318
for _lib in _libs.values():
    if hasattr(_lib, 'setbuffer'):
        setbuffer = _lib.setbuffer
        setbuffer.restype = None
        setbuffer.argtypes = [POINTER(FILE), String, c_size_t]
        break

# /usr/include/stdio.h: 322
for _lib in _libs.values():
    if hasattr(_lib, 'setlinebuf'):
        setlinebuf = _lib.setlinebuf
        setlinebuf.restype = None
        setlinebuf.argtypes = [POINTER(FILE)]
        break

# /usr/include/stdio.h: 331
for _lib in _libs.values():
    if hasattr(_lib, 'fprintf'):
        _func = _lib.fprintf
        _restype = c_int
        _argtypes = [POINTER(FILE), String]
        fprintf = _variadic_function(_func,_restype,_argtypes)

# /usr/include/stdio.h: 337
for _lib in _libs.values():
    if hasattr(_lib, 'printf'):
        _func = _lib.printf
        _restype = c_int
        _argtypes = [String]
        printf = _variadic_function(_func,_restype,_argtypes)

# /usr/include/stdio.h: 339
for _lib in _libs.values():
    if hasattr(_lib, 'sprintf'):
        _func = _lib.sprintf
        _restype = c_int
        _argtypes = [String, String]
        sprintf = _variadic_function(_func,_restype,_argtypes)

# /usr/include/stdio.h: 361
for _lib in _libs.values():
    if hasattr(_lib, 'snprintf'):
        _func = _lib.snprintf
        _restype = c_int
        _argtypes = [String, c_size_t, String]
        snprintf = _variadic_function(_func,_restype,_argtypes)

# /usr/include/stdio.h: 403
for _lib in _libs.values():
    if hasattr(_lib, 'fscanf'):
        _func = _lib.fscanf
        _restype = c_int
        _argtypes = [POINTER(FILE), String]
        fscanf = _variadic_function(_func,_restype,_argtypes)

# /usr/include/stdio.h: 409
for _lib in _libs.values():
    if hasattr(_lib, 'scanf'):
        _func = _lib.scanf
        _restype = c_int
        _argtypes = [String]
        scanf = _variadic_function(_func,_restype,_argtypes)

# /usr/include/stdio.h: 411
for _lib in _libs.values():
    if hasattr(_lib, 'sscanf'):
        _func = _lib.sscanf
        _restype = c_int
        _argtypes = [String, String]
        sscanf = _variadic_function(_func,_restype,_argtypes)

# /usr/include/stdio.h: 509
for _lib in _libs.values():
    if hasattr(_lib, 'fgetc'):
        fgetc = _lib.fgetc
        fgetc.restype = c_int
        fgetc.argtypes = [POINTER(FILE)]
        break

# /usr/include/stdio.h: 510
for _lib in _libs.values():
    if hasattr(_lib, 'getc'):
        getc = _lib.getc
        getc.restype = c_int
        getc.argtypes = [POINTER(FILE)]
        break

# /usr/include/stdio.h: 516
for _lib in _libs.values():
    if hasattr(_lib, 'getchar'):
        getchar = _lib.getchar
        getchar.restype = c_int
        getchar.argtypes = []
        break

# /usr/include/stdio.h: 528
for _lib in _libs.values():
    if hasattr(_lib, 'getc_unlocked'):
        getc_unlocked = _lib.getc_unlocked
        getc_unlocked.restype = c_int
        getc_unlocked.argtypes = [POINTER(FILE)]
        break

# /usr/include/stdio.h: 529
for _lib in _libs.values():
    if hasattr(_lib, 'getchar_unlocked'):
        getchar_unlocked = _lib.getchar_unlocked
        getchar_unlocked.restype = c_int
        getchar_unlocked.argtypes = []
        break

# /usr/include/stdio.h: 539
for _lib in _libs.values():
    if hasattr(_lib, 'fgetc_unlocked'):
        fgetc_unlocked = _lib.fgetc_unlocked
        fgetc_unlocked.restype = c_int
        fgetc_unlocked.argtypes = [POINTER(FILE)]
        break

# /usr/include/stdio.h: 551
for _lib in _libs.values():
    if hasattr(_lib, 'fputc'):
        fputc = _lib.fputc
        fputc.restype = c_int
        fputc.argtypes = [c_int, POINTER(FILE)]
        break

# /usr/include/stdio.h: 552
for _lib in _libs.values():
    if hasattr(_lib, 'putc'):
        putc = _lib.putc
        putc.restype = c_int
        putc.argtypes = [c_int, POINTER(FILE)]
        break

# /usr/include/stdio.h: 558
for _lib in _libs.values():
    if hasattr(_lib, 'putchar'):
        putchar = _lib.putchar
        putchar.restype = c_int
        putchar.argtypes = [c_int]
        break

# /usr/include/stdio.h: 572
for _lib in _libs.values():
    if hasattr(_lib, 'fputc_unlocked'):
        fputc_unlocked = _lib.fputc_unlocked
        fputc_unlocked.restype = c_int
        fputc_unlocked.argtypes = [c_int, POINTER(FILE)]
        break

# /usr/include/stdio.h: 580
for _lib in _libs.values():
    if hasattr(_lib, 'putc_unlocked'):
        putc_unlocked = _lib.putc_unlocked
        putc_unlocked.restype = c_int
        putc_unlocked.argtypes = [c_int, POINTER(FILE)]
        break

# /usr/include/stdio.h: 581
for _lib in _libs.values():
    if hasattr(_lib, 'putchar_unlocked'):
        putchar_unlocked = _lib.putchar_unlocked
        putchar_unlocked.restype = c_int
        putchar_unlocked.argtypes = [c_int]
        break

# /usr/include/stdio.h: 588
for _lib in _libs.values():
    if hasattr(_lib, 'getw'):
        getw = _lib.getw
        getw.restype = c_int
        getw.argtypes = [POINTER(FILE)]
        break

# /usr/include/stdio.h: 591
for _lib in _libs.values():
    if hasattr(_lib, 'putw'):
        putw = _lib.putw
        putw.restype = c_int
        putw.argtypes = [c_int, POINTER(FILE)]
        break

# /usr/include/stdio.h: 600
for _lib in _libs.values():
    if hasattr(_lib, 'fgets'):
        fgets = _lib.fgets
        fgets.restype = String
        fgets.argtypes = [String, c_int, POINTER(FILE)]
        fgets.errcheck = ReturnString
        break

# /usr/include/stdio.h: 608
for _lib in _libs.values():
    if hasattr(_lib, 'gets'):
        gets = _lib.gets
        gets.restype = String
        gets.argtypes = [String]
        gets.errcheck = ReturnString
        break

# /usr/include/stdio.h: 658
for _lib in _libs.values():
    if hasattr(_lib, 'fputs'):
        fputs = _lib.fputs
        fputs.restype = c_int
        fputs.argtypes = [String, POINTER(FILE)]
        break

# /usr/include/stdio.h: 664
for _lib in _libs.values():
    if hasattr(_lib, 'puts'):
        puts = _lib.puts
        puts.restype = c_int
        puts.argtypes = [String]
        break

# /usr/include/stdio.h: 671
for _lib in _libs.values():
    if hasattr(_lib, 'ungetc'):
        ungetc = _lib.ungetc
        ungetc.restype = c_int
        ungetc.argtypes = [c_int, POINTER(FILE)]
        break

# /usr/include/stdio.h: 678
for _lib in _libs.values():
    if hasattr(_lib, 'fread'):
        fread = _lib.fread
        fread.restype = c_size_t
        fread.argtypes = [POINTER(None), c_size_t, c_size_t, POINTER(FILE)]
        break

# /usr/include/stdio.h: 684
for _lib in _libs.values():
    if hasattr(_lib, 'fwrite'):
        fwrite = _lib.fwrite
        fwrite.restype = c_size_t
        fwrite.argtypes = [POINTER(None), c_size_t, c_size_t, POINTER(FILE)]
        break

# /usr/include/stdio.h: 706
for _lib in _libs.values():
    if hasattr(_lib, 'fread_unlocked'):
        fread_unlocked = _lib.fread_unlocked
        fread_unlocked.restype = c_size_t
        fread_unlocked.argtypes = [POINTER(None), c_size_t, c_size_t, POINTER(FILE)]
        break

# /usr/include/stdio.h: 708
for _lib in _libs.values():
    if hasattr(_lib, 'fwrite_unlocked'):
        fwrite_unlocked = _lib.fwrite_unlocked
        fwrite_unlocked.restype = c_size_t
        fwrite_unlocked.argtypes = [POINTER(None), c_size_t, c_size_t, POINTER(FILE)]
        break

# /usr/include/stdio.h: 718
for _lib in _libs.values():
    if hasattr(_lib, 'fseek'):
        fseek = _lib.fseek
        fseek.restype = c_int
        fseek.argtypes = [POINTER(FILE), c_long, c_int]
        break

# /usr/include/stdio.h: 723
for _lib in _libs.values():
    if hasattr(_lib, 'ftell'):
        ftell = _lib.ftell
        ftell.restype = c_long
        ftell.argtypes = [POINTER(FILE)]
        break

# /usr/include/stdio.h: 728
for _lib in _libs.values():
    if hasattr(_lib, 'rewind'):
        rewind = _lib.rewind
        rewind.restype = None
        rewind.argtypes = [POINTER(FILE)]
        break

# /usr/include/stdio.h: 742
for _lib in _libs.values():
    if hasattr(_lib, 'fseeko'):
        fseeko = _lib.fseeko
        fseeko.restype = c_int
        fseeko.argtypes = [POINTER(FILE), __off_t, c_int]
        break

# /usr/include/stdio.h: 747
for _lib in _libs.values():
    if hasattr(_lib, 'ftello'):
        ftello = _lib.ftello
        ftello.restype = __off_t
        ftello.argtypes = [POINTER(FILE)]
        break

# /usr/include/stdio.h: 767
for _lib in _libs.values():
    if hasattr(_lib, 'fgetpos'):
        fgetpos = _lib.fgetpos
        fgetpos.restype = c_int
        fgetpos.argtypes = [POINTER(FILE), POINTER(fpos_t)]
        break

# /usr/include/stdio.h: 772
for _lib in _libs.values():
    if hasattr(_lib, 'fsetpos'):
        fsetpos = _lib.fsetpos
        fsetpos.restype = c_int
        fsetpos.argtypes = [POINTER(FILE), POINTER(fpos_t)]
        break

# /usr/include/stdio.h: 795
for _lib in _libs.values():
    if hasattr(_lib, 'clearerr'):
        clearerr = _lib.clearerr
        clearerr.restype = None
        clearerr.argtypes = [POINTER(FILE)]
        break

# /usr/include/stdio.h: 797
for _lib in _libs.values():
    if hasattr(_lib, 'feof'):
        feof = _lib.feof
        feof.restype = c_int
        feof.argtypes = [POINTER(FILE)]
        break

# /usr/include/stdio.h: 799
for _lib in _libs.values():
    if hasattr(_lib, 'ferror'):
        ferror = _lib.ferror
        ferror.restype = c_int
        ferror.argtypes = [POINTER(FILE)]
        break

# /usr/include/stdio.h: 804
for _lib in _libs.values():
    if hasattr(_lib, 'clearerr_unlocked'):
        clearerr_unlocked = _lib.clearerr_unlocked
        clearerr_unlocked.restype = None
        clearerr_unlocked.argtypes = [POINTER(FILE)]
        break

# /usr/include/stdio.h: 805
for _lib in _libs.values():
    if hasattr(_lib, 'feof_unlocked'):
        feof_unlocked = _lib.feof_unlocked
        feof_unlocked.restype = c_int
        feof_unlocked.argtypes = [POINTER(FILE)]
        break

# /usr/include/stdio.h: 806
for _lib in _libs.values():
    if hasattr(_lib, 'ferror_unlocked'):
        ferror_unlocked = _lib.ferror_unlocked
        ferror_unlocked.restype = c_int
        ferror_unlocked.argtypes = [POINTER(FILE)]
        break

# /usr/include/stdio.h: 815
for _lib in _libs.values():
    if hasattr(_lib, 'perror'):
        perror = _lib.perror
        perror.restype = None
        perror.argtypes = [String]
        break

# /usr/include/bits/sys_errlist.h: 27
for _lib in _libs.values():
    try:
        sys_nerr = (c_int).in_dll(_lib, 'sys_nerr')
        break
    except:
        pass

# /usr/include/bits/sys_errlist.h: 28
for _lib in _libs.values():
    try:
        sys_errlist = (POINTER(POINTER(c_char))).in_dll(_lib, 'sys_errlist')
        break
    except:
        pass

# /usr/include/stdio.h: 827
for _lib in _libs.values():
    if hasattr(_lib, 'fileno'):
        fileno = _lib.fileno
        fileno.restype = c_int
        fileno.argtypes = [POINTER(FILE)]
        break

# /usr/include/stdio.h: 832
for _lib in _libs.values():
    if hasattr(_lib, 'fileno_unlocked'):
        fileno_unlocked = _lib.fileno_unlocked
        fileno_unlocked.restype = c_int
        fileno_unlocked.argtypes = [POINTER(FILE)]
        break

# /usr/include/stdio.h: 842
for _lib in _libs.values():
    if hasattr(_lib, 'popen'):
        popen = _lib.popen
        popen.restype = POINTER(FILE)
        popen.argtypes = [String, String]
        break

# /usr/include/stdio.h: 848
for _lib in _libs.values():
    if hasattr(_lib, 'pclose'):
        pclose = _lib.pclose
        pclose.restype = c_int
        pclose.argtypes = [POINTER(FILE)]
        break

# /usr/include/stdio.h: 854
for _lib in _libs.values():
    if hasattr(_lib, 'ctermid'):
        ctermid = _lib.ctermid
        ctermid.restype = String
        ctermid.argtypes = [String]
        ctermid.errcheck = ReturnString
        break

# /usr/include/stdio.h: 882
for _lib in _libs.values():
    if hasattr(_lib, 'flockfile'):
        flockfile = _lib.flockfile
        flockfile.restype = None
        flockfile.argtypes = [POINTER(FILE)]
        break

# /usr/include/stdio.h: 886
for _lib in _libs.values():
    if hasattr(_lib, 'ftrylockfile'):
        ftrylockfile = _lib.ftrylockfile
        ftrylockfile.restype = c_int
        ftrylockfile.argtypes = [POINTER(FILE)]
        break

# /usr/include/stdio.h: 889
for _lib in _libs.values():
    if hasattr(_lib, 'funlockfile'):
        funlockfile = _lib.funlockfile
        funlockfile.restype = None
        funlockfile.argtypes = [POINTER(FILE)]
        break

# /mnt/hda4/home/c/adflib/src/adf_blk.h: 105
class struct_bBootBlock(Structure):
    pass

struct_bBootBlock.__slots__ = [
    'dosType',
    'checkSum',
    'rootBlock',
    'data',
]
struct_bBootBlock._fields_ = [
    ('dosType', c_char * 4),
    ('checkSum', c_uint32),
    ('rootBlock', c_int32),
    ('data', c_uint8 * (500 + 512)),
]

# /mnt/hda4/home/c/adflib/src/adf_blk.h: 113
class struct_bRootBlock(Structure):
    pass

struct_bRootBlock.__slots__ = [
    'type',
    'headerKey',
    'highSeq',
    'hashTableSize',
    'firstData',
    'checkSum',
    'hashTable',
    'bmFlag',
    'bmPages',
    'bmExt',
    'cDays',
    'cMins',
    'cTicks',
    'nameLen',
    'diskName',
    'r2',
    'days',
    'mins',
    'ticks',
    'coDays',
    'coMins',
    'coTicks',
    'nextSameHash',
    'parent',
    'extension',
    'secType',
]
struct_bRootBlock._fields_ = [
    ('type', c_int32),
    ('headerKey', c_int32),
    ('highSeq', c_int32),
    ('hashTableSize', c_int32),
    ('firstData', c_int32),
    ('checkSum', c_uint32),
    ('hashTable', c_int32 * 72),
    ('bmFlag', c_int32),
    ('bmPages', c_int32 * 25),
    ('bmExt', c_int32),
    ('cDays', c_int32),
    ('cMins', c_int32),
    ('cTicks', c_int32),
    ('nameLen', c_char),
    ('diskName', c_char * (30 + 1)),
    ('r2', c_char * 8),
    ('days', c_int32),
    ('mins', c_int32),
    ('ticks', c_int32),
    ('coDays', c_int32),
    ('coMins', c_int32),
    ('coTicks', c_int32),
    ('nextSameHash', c_int32),
    ('parent', c_int32),
    ('extension', c_int32),
    ('secType', c_int32),
]

# /mnt/hda4/home/c/adflib/src/adf_blk.h: 143
class struct_bFileHeaderBlock(Structure):
    pass

struct_bFileHeaderBlock.__slots__ = [
    'type',
    'headerKey',
    'highSeq',
    'dataSize',
    'firstData',
    'checkSum',
    'dataBlocks',
    'r1',
    'r2',
    'access',
    'byteSize',
    'commLen',
    'comment',
    'r3',
    'days',
    'mins',
    'ticks',
    'nameLen',
    'fileName',
    'r4',
    'real',
    'nextLink',
    'r5',
    'nextSameHash',
    'parent',
    'extension',
    'secType',
]
struct_bFileHeaderBlock._fields_ = [
    ('type', c_int32),
    ('headerKey', c_int32),
    ('highSeq', c_int32),
    ('dataSize', c_int32),
    ('firstData', c_int32),
    ('checkSum', c_uint32),
    ('dataBlocks', c_int32 * 72),
    ('r1', c_int32),
    ('r2', c_int32),
    ('access', c_int32),
    ('byteSize', c_uint32),
    ('commLen', c_char),
    ('comment', c_char * (79 + 1)),
    ('r3', c_char * (91 - (79 + 1))),
    ('days', c_int32),
    ('mins', c_int32),
    ('ticks', c_int32),
    ('nameLen', c_char),
    ('fileName', c_char * (30 + 1)),
    ('r4', c_int32),
    ('real', c_int32),
    ('nextLink', c_int32),
    ('r5', c_int32 * 5),
    ('nextSameHash', c_int32),
    ('parent', c_int32),
    ('extension', c_int32),
    ('secType', c_int32),
]

# /mnt/hda4/home/c/adflib/src/adf_blk.h: 176
class struct_bFileExtBlock(Structure):
    pass

struct_bFileExtBlock.__slots__ = [
    'type',
    'headerKey',
    'highSeq',
    'dataSize',
    'firstData',
    'checkSum',
    'dataBlocks',
    'r',
    'info',
    'nextSameHash',
    'parent',
    'extension',
    'secType',
]
struct_bFileExtBlock._fields_ = [
    ('type', c_int32),
    ('headerKey', c_int32),
    ('highSeq', c_int32),
    ('dataSize', c_int32),
    ('firstData', c_int32),
    ('checkSum', c_uint32),
    ('dataBlocks', c_int32 * 72),
    ('r', c_int32 * 45),
    ('info', c_int32),
    ('nextSameHash', c_int32),
    ('parent', c_int32),
    ('extension', c_int32),
    ('secType', c_int32),
]

# /mnt/hda4/home/c/adflib/src/adf_blk.h: 194
class struct_bDirBlock(Structure):
    pass

struct_bDirBlock.__slots__ = [
    'type',
    'headerKey',
    'highSeq',
    'hashTableSize',
    'r1',
    'checkSum',
    'hashTable',
    'r2',
    'access',
    'r4',
    'commLen',
    'comment',
    'r5',
    'days',
    'mins',
    'ticks',
    'nameLen',
    'dirName',
    'r6',
    'real',
    'nextLink',
    'r7',
    'nextSameHash',
    'parent',
    'extension',
    'secType',
]
struct_bDirBlock._fields_ = [
    ('type', c_int32),
    ('headerKey', c_int32),
    ('highSeq', c_int32),
    ('hashTableSize', c_int32),
    ('r1', c_int32),
    ('checkSum', c_uint32),
    ('hashTable', c_int32 * 72),
    ('r2', c_int32 * 2),
    ('access', c_int32),
    ('r4', c_int32),
    ('commLen', c_char),
    ('comment', c_char * (79 + 1)),
    ('r5', c_char * (91 - (79 + 1))),
    ('days', c_int32),
    ('mins', c_int32),
    ('ticks', c_int32),
    ('nameLen', c_char),
    ('dirName', c_char * (30 + 1)),
    ('r6', c_int32),
    ('real', c_int32),
    ('nextLink', c_int32),
    ('r7', c_int32 * 5),
    ('nextSameHash', c_int32),
    ('parent', c_int32),
    ('extension', c_int32),
    ('secType', c_int32),
]

# /mnt/hda4/home/c/adflib/src/adf_blk.h: 225
class struct_bOFSDataBlock(Structure):
    pass

struct_bOFSDataBlock.__slots__ = [
    'type',
    'headerKey',
    'seqNum',
    'dataSize',
    'nextData',
    'checkSum',
    'data',
]
struct_bOFSDataBlock._fields_ = [
    ('type', c_int32),
    ('headerKey', c_int32),
    ('seqNum', c_int32),
    ('dataSize', c_int32),
    ('nextData', c_int32),
    ('checkSum', c_uint32),
    ('data', c_uint8 * 488),
]

# /mnt/hda4/home/c/adflib/src/adf_blk.h: 238
class struct_bBitmapBlock(Structure):
    pass

struct_bBitmapBlock.__slots__ = [
    'checkSum',
    'map',
]
struct_bBitmapBlock._fields_ = [
    ('checkSum', c_uint32),
    ('map', c_uint32 * 127),
]

# /mnt/hda4/home/c/adflib/src/adf_blk.h: 244
class struct_bBitmapExtBlock(Structure):
    pass

struct_bBitmapExtBlock.__slots__ = [
    'bmPages',
    'nextBlock',
]
struct_bBitmapExtBlock._fields_ = [
    ('bmPages', c_int32 * 127),
    ('nextBlock', c_int32),
]

# /mnt/hda4/home/c/adflib/src/adf_blk.h: 250
class struct_bLinkBlock(Structure):
    pass

struct_bLinkBlock.__slots__ = [
    'type',
    'headerKey',
    'r1',
    'checkSum',
    'realName',
    'r2',
    'days',
    'mins',
    'ticks',
    'nameLen',
    'name',
    'r3',
    'realEntry',
    'nextLink',
    'r4',
    'nextSameHash',
    'parent',
    'r5',
    'secType',
]
struct_bLinkBlock._fields_ = [
    ('type', c_int32),
    ('headerKey', c_int32),
    ('r1', c_int32 * 3),
    ('checkSum', c_uint32),
    ('realName', c_char * 64),
    ('r2', c_int32 * 83),
    ('days', c_int32),
    ('mins', c_int32),
    ('ticks', c_int32),
    ('nameLen', c_char),
    ('name', c_char * (30 + 1)),
    ('r3', c_int32),
    ('realEntry', c_int32),
    ('nextLink', c_int32),
    ('r4', c_int32 * 5),
    ('nextSameHash', c_int32),
    ('parent', c_int32),
    ('r5', c_int32),
    ('secType', c_int32),
]

# /mnt/hda4/home/c/adflib/src/adf_blk.h: 276
class struct_bDirCacheBlock(Structure):
    pass

struct_bDirCacheBlock.__slots__ = [
    'type',
    'headerKey',
    'parent',
    'recordsNb',
    'nextDirC',
    'checkSum',
    'records',
]
struct_bDirCacheBlock._fields_ = [
    ('type', c_int32),
    ('headerKey', c_int32),
    ('parent', c_int32),
    ('recordsNb', c_int32),
    ('nextDirC', c_int32),
    ('checkSum', c_uint32),
    ('records', c_uint8 * 488),
]

# /mnt/hda4/home/c/adflib/src/adf_str.h: 79
class struct_Device(Structure):
    pass

# /mnt/hda4/home/c/adflib/src/adf_str.h: 39
class struct_Volume(Structure):
    pass

struct_Volume.__slots__ = [
    'dev',
    'firstBlock',
    'lastBlock',
    'rootBlock',
    'dosType',
    'bootCode',
    'readOnly',
    'datablockSize',
    'blockSize',
    'volName',
    'mounted',
    'bitmapSize',
    'bitmapBlocks',
    'bitmapTable',
    'bitmapBlocksChg',
    'curDirPtr',
]
struct_Volume._fields_ = [
    ('dev', POINTER(struct_Device)),
    ('firstBlock', c_int32),
    ('lastBlock', c_int32),
    ('rootBlock', c_int32),
    ('dosType', c_char),
    ('bootCode', c_int),
    ('readOnly', c_int),
    ('datablockSize', c_int),
    ('blockSize', c_int),
    ('volName', String),
    ('mounted', c_int),
    ('bitmapSize', c_int32),
    ('bitmapBlocks', POINTER(c_int32)),
    ('bitmapTable', POINTER(POINTER(struct_bBitmapBlock))),
    ('bitmapBlocksChg', POINTER(c_int)),
    ('curDirPtr', c_int32),
]

# /mnt/hda4/home/c/adflib/src/adf_str.h: 65
class struct_Partition(Structure):
    pass

struct_Partition.__slots__ = [
    'startCyl',
    'lenCyl',
    'volName',
    'volType',
]
struct_Partition._fields_ = [
    ('startCyl', c_int32),
    ('lenCyl', c_int32),
    ('volName', String),
    ('volType', c_int),
]

struct_Device.__slots__ = [
    'devType',
    'readOnly',
    'size',
    'nVol',
    'volList',
    'cylinders',
    'heads',
    'sectors',
    'isNativeDev',
    'nativeDev',
]
struct_Device._fields_ = [
    ('devType', c_int),
    ('readOnly', c_int),
    ('size', c_int32),
    ('nVol', c_int),
    ('volList', POINTER(POINTER(struct_Volume))),
    ('cylinders', c_int32),
    ('heads', c_int32),
    ('sectors', c_int32),
    ('isNativeDev', c_int),
    ('nativeDev', POINTER(None)),
]

# /mnt/hda4/home/c/adflib/src/adf_str.h: 98
class struct_File(Structure):
    pass

struct_File.__slots__ = [
    'volume',
    'fileHdr',
    'currentData',
    'currentExt',
    'nDataBlock',
    'curDataPtr',
    'pos',
    'posInDataBlk',
    'posInExtBlk',
    'eof',
    'writeMode',
]
struct_File._fields_ = [
    ('volume', POINTER(struct_Volume)),
    ('fileHdr', POINTER(struct_bFileHeaderBlock)),
    ('currentData', POINTER(None)),
    ('currentExt', POINTER(struct_bFileExtBlock)),
    ('nDataBlock', c_int32),
    ('curDataPtr', c_int32),
    ('pos', c_uint32),
    ('posInDataBlk', c_int),
    ('posInExtBlk', c_int),
    ('eof', c_int),
    ('writeMode', c_int),
]

# /mnt/hda4/home/c/adflib/src/adf_str.h: 117
class struct_Entry(Structure):
    pass

struct_Entry.__slots__ = [
    'type',
    'name',
    'sector',
    'real',
    'parent',
    'comment',
    'size',
    'access',
    'year',
    'month',
    'days',
    'hour',
    'mins',
    'secs',
]
struct_Entry._fields_ = [
    ('type', c_int),
    ('name', String),
    ('sector', c_int32),
    ('real', c_int32),
    ('parent', c_int32),
    ('comment', String),
    ('size', c_uint32),
    ('access', c_int32),
    ('year', c_int),
    ('month', c_int),
    ('days', c_int),
    ('hour', c_int),
    ('mins', c_int),
    ('secs', c_int),
]

# /mnt/hda4/home/c/adflib/src/adf_str.h: 130
class struct_CacheEntry(Structure):
    pass

struct_CacheEntry.__slots__ = [
    'header',
    'size',
    'protect',
    'days',
    'mins',
    'ticks',
    'type',
    'nLen',
    'cLen',
    'name',
    'comm',
]
struct_CacheEntry._fields_ = [
    ('header', c_int32),
    ('size', c_int32),
    ('protect', c_int32),
    ('days', c_short),
    ('mins', c_short),
    ('ticks', c_short),
    ('type', c_char),
    ('nLen', c_char),
    ('cLen', c_char),
    ('name', c_char * (30 + 1)),
    ('comm', c_char * (79 + 1)),
]

# /mnt/hda4/home/c/adflib/src/adf_str.h: 143
class struct_DateTime(Structure):
    pass

struct_DateTime.__slots__ = [
    'year',
    'mon',
    'day',
    'hour',
    'min',
    'sec',
]
struct_DateTime._fields_ = [
    ('year', c_int),
    ('mon', c_int),
    ('day', c_int),
    ('hour', c_int),
    ('min', c_int),
    ('sec', c_int),
]

# /mnt/hda4/home/c/adflib/src/adf_str.h: 160
class struct_Env(Structure):
    pass

struct_Env.__slots__ = [
    'vFct',
    'wFct',
    'eFct',
    'notifyFct',
    'useNotify',
    'rwhAccess',
    'useRWAccess',
    'progressBar',
    'useProgressBar',
    'useDirCache',
    'nativeFct',
]
struct_Env._fields_ = [
    ('vFct', CFUNCTYPE(UNCHECKED(None), String)),
    ('wFct', CFUNCTYPE(UNCHECKED(None), String)),
    ('eFct', CFUNCTYPE(UNCHECKED(None), String)),
    ('notifyFct', CFUNCTYPE(UNCHECKED(None), c_int32, c_int)),
    ('useNotify', c_int),
    ('rwhAccess', CFUNCTYPE(UNCHECKED(None), c_int32, c_int32, c_int)),
    ('useRWAccess', c_int),
    ('progressBar', CFUNCTYPE(UNCHECKED(None), c_int)),
    ('useProgressBar', c_int),
    ('useDirCache', c_int),
    ('nativeFct', POINTER(None)),
]

# /mnt/hda4/home/c/adflib/src/adf_str.h: 181
class struct_List(Structure):
    pass

struct_List.__slots__ = [
    'content',
    'subdir',
    'next',
]
struct_List._fields_ = [
    ('content', POINTER(None)),
    ('subdir', POINTER(struct_List)),
    ('next', POINTER(struct_List)),
]

# /mnt/hda4/home/c/adflib/src/adf_str.h: 187
class struct_GenBlock(Structure):
    pass

struct_GenBlock.__slots__ = [
    'sect',
    'parent',
    'type',
    'secType',
    'name',
]
struct_GenBlock._fields_ = [
    ('sect', c_int32),
    ('parent', c_int32),
    ('type', c_int),
    ('secType', c_int),
    ('name', String),
]

# /mnt/hda4/home/c/adflib/src/adf_str.h: 195
class struct_FileBlocks(Structure):
    pass

struct_FileBlocks.__slots__ = [
    'header',
    'nbExtens',
    'extens',
    'nbData',
    'data',
]
struct_FileBlocks._fields_ = [
    ('header', c_int32),
    ('nbExtens', c_int32),
    ('extens', POINTER(c_int32)),
    ('nbData', c_int32),
    ('data', POINTER(c_int32)),
]

# /mnt/hda4/home/c/adflib/src/adf_str.h: 203
class struct_bEntryBlock(Structure):
    pass

struct_bEntryBlock.__slots__ = [
    'type',
    'headerKey',
    'r1',
    'checkSum',
    'hashTable',
    'r2',
    'access',
    'byteSize',
    'commLen',
    'comment',
    'r3',
    'days',
    'mins',
    'ticks',
    'nameLen',
    'name',
    'r4',
    'realEntry',
    'nextLink',
    'r5',
    'nextSameHash',
    'parent',
    'extension',
    'secType',
]
struct_bEntryBlock._fields_ = [
    ('type', c_int32),
    ('headerKey', c_int32),
    ('r1', c_int32 * 3),
    ('checkSum', c_uint32),
    ('hashTable', c_int32 * 72),
    ('r2', c_int32 * 2),
    ('access', c_int32),
    ('byteSize', c_int32),
    ('commLen', c_char),
    ('comment', c_char * (79 + 1)),
    ('r3', c_char * (91 - (79 + 1))),
    ('days', c_int32),
    ('mins', c_int32),
    ('ticks', c_int32),
    ('nameLen', c_char),
    ('name', c_char * (30 + 1)),
    ('r4', c_int32),
    ('realEntry', c_int32),
    ('nextLink', c_int32),
    ('r5', c_int32 * 5),
    ('nextSameHash', c_int32),
    ('parent', c_int32),
    ('extension', c_int32),
    ('secType', c_int32),
]

# /mnt/hda4/home/c/adflib/src/adflib.h: 48
for _lib in _libs.values():
    if hasattr(_lib, 'newCell'):
        newCell = _lib.newCell
        newCell.restype = POINTER(struct_List)
        newCell.argtypes = [POINTER(struct_List), POINTER(None)]
        break

# /mnt/hda4/home/c/adflib/src/adflib.h: 49
for _lib in _libs.values():
    if hasattr(_lib, 'freeList'):
        freeList = _lib.freeList
        freeList.restype = None
        freeList.argtypes = [POINTER(struct_List)]
        break

# /mnt/hda4/home/c/adflib/src/adflib.h: 52
for _lib in _libs.values():
    if hasattr(_lib, 'adfToRootDir'):
        adfToRootDir = _lib.adfToRootDir
        adfToRootDir.restype = c_int32
        adfToRootDir.argtypes = [POINTER(struct_Volume)]
        break

# /mnt/hda4/home/c/adflib/src/adflib.h: 53
for _lib in _libs.values():
    if hasattr(_lib, 'adfCreateDir'):
        adfCreateDir = _lib.adfCreateDir
        adfCreateDir.restype = c_int32
        adfCreateDir.argtypes = [POINTER(struct_Volume), c_int32, String]
        break

# /mnt/hda4/home/c/adflib/src/adflib.h: 54
for _lib in _libs.values():
    if hasattr(_lib, 'adfChangeDir'):
        adfChangeDir = _lib.adfChangeDir
        adfChangeDir.restype = c_int32
        adfChangeDir.argtypes = [POINTER(struct_Volume), String]
        break

# /mnt/hda4/home/c/adflib/src/adflib.h: 55
for _lib in _libs.values():
    if hasattr(_lib, 'adfParentDir'):
        adfParentDir = _lib.adfParentDir
        adfParentDir.restype = c_int32
        adfParentDir.argtypes = [POINTER(struct_Volume)]
        break

# /mnt/hda4/home/c/adflib/src/adflib.h: 56
for _lib in _libs.values():
    if hasattr(_lib, 'adfRemoveEntry'):
        adfRemoveEntry = _lib.adfRemoveEntry
        adfRemoveEntry.restype = c_int32
        adfRemoveEntry.argtypes = [POINTER(struct_Volume), c_int32, String]
        break

# /mnt/hda4/home/c/adflib/src/adflib.h: 57
for _lib in _libs.values():
    if hasattr(_lib, 'adfGetDirEnt'):
        adfGetDirEnt = _lib.adfGetDirEnt
        adfGetDirEnt.restype = POINTER(struct_List)
        adfGetDirEnt.argtypes = [POINTER(struct_Volume), c_int32]
        break

# /mnt/hda4/home/c/adflib/src/adflib.h: 58
for _lib in _libs.values():
    if hasattr(_lib, 'adfGetRDirEnt'):
        adfGetRDirEnt = _lib.adfGetRDirEnt
        adfGetRDirEnt.restype = POINTER(struct_List)
        adfGetRDirEnt.argtypes = [POINTER(struct_Volume), c_int32, c_int]
        break

# /mnt/hda4/home/c/adflib/src/adflib.h: 59
for _lib in _libs.values():
    if hasattr(_lib, 'printEntry'):
        printEntry = _lib.printEntry
        printEntry.restype = None
        printEntry.argtypes = [POINTER(struct_Entry)]
        break

# /mnt/hda4/home/c/adflib/src/adflib.h: 60
for _lib in _libs.values():
    if hasattr(_lib, 'adfFreeDirList'):
        adfFreeDirList = _lib.adfFreeDirList
        adfFreeDirList.restype = None
        adfFreeDirList.argtypes = [POINTER(struct_List)]
        break

# /mnt/hda4/home/c/adflib/src/adflib.h: 61
for _lib in _libs.values():
    if hasattr(_lib, 'adfFreeEntry'):
        adfFreeEntry = _lib.adfFreeEntry
        adfFreeEntry.restype = None
        adfFreeEntry.argtypes = [POINTER(struct_Entry)]
        break

# /mnt/hda4/home/c/adflib/src/adflib.h: 62
for _lib in _libs.values():
    if hasattr(_lib, 'adfRenameEntry'):
        adfRenameEntry = _lib.adfRenameEntry
        adfRenameEntry.restype = c_int32
        adfRenameEntry.argtypes = [POINTER(struct_Volume), c_int32, String, c_int32, String]
        break

# /mnt/hda4/home/c/adflib/src/adflib.h: 63
for _lib in _libs.values():
    if hasattr(_lib, 'adfSetEntryAccess'):
        adfSetEntryAccess = _lib.adfSetEntryAccess
        adfSetEntryAccess.restype = c_int32
        adfSetEntryAccess.argtypes = [POINTER(struct_Volume), c_int32, String, c_int32]
        break

# /mnt/hda4/home/c/adflib/src/adflib.h: 64
for _lib in _libs.values():
    if hasattr(_lib, 'adfSetEntryComment'):
        adfSetEntryComment = _lib.adfSetEntryComment
        adfSetEntryComment.restype = c_int32
        adfSetEntryComment.argtypes = [POINTER(struct_Volume), c_int32, String, String]
        break

# /mnt/hda4/home/c/adflib/src/adflib.h: 67
for _lib in _libs.values():
    if hasattr(_lib, 'adfFileRealSize'):
        adfFileRealSize = _lib.adfFileRealSize
        adfFileRealSize.restype = c_int32
        adfFileRealSize.argtypes = [c_uint32, c_int, POINTER(c_int32), POINTER(c_int32)]
        break

# /mnt/hda4/home/c/adflib/src/adflib.h: 68
for _lib in _libs.values():
    if hasattr(_lib, 'adfOpenFile'):
        adfOpenFile = _lib.adfOpenFile
        adfOpenFile.restype = POINTER(struct_File)
        adfOpenFile.argtypes = [POINTER(struct_Volume), String, String]
        break

# /mnt/hda4/home/c/adflib/src/adflib.h: 69
for _lib in _libs.values():
    if hasattr(_lib, 'adfCloseFile'):
        adfCloseFile = _lib.adfCloseFile
        adfCloseFile.restype = None
        adfCloseFile.argtypes = [POINTER(struct_File)]
        break

# /mnt/hda4/home/c/adflib/src/adflib.h: 70
for _lib in _libs.values():
    if hasattr(_lib, 'adfReadFile'):
        adfReadFile = _lib.adfReadFile
        adfReadFile.restype = c_int32
        adfReadFile.argtypes = [POINTER(struct_File), c_int32, POINTER(c_uint8)]
        break

# /mnt/hda4/home/c/adflib/src/adflib.h: 71
for _lib in _libs.values():
    if hasattr(_lib, 'adfEndOfFile'):
        adfEndOfFile = _lib.adfEndOfFile
        adfEndOfFile.restype = c_int
        adfEndOfFile.argtypes = [POINTER(struct_File)]
        break

# /mnt/hda4/home/c/adflib/src/adflib.h: 72
for _lib in _libs.values():
    if hasattr(_lib, 'adfWriteFile'):
        adfWriteFile = _lib.adfWriteFile
        adfWriteFile.restype = c_int32
        adfWriteFile.argtypes = [POINTER(struct_File), c_int32, POINTER(c_uint8)]
        break

# /mnt/hda4/home/c/adflib/src/adflib.h: 73
for _lib in _libs.values():
    if hasattr(_lib, 'adfFlushFile'):
        adfFlushFile = _lib.adfFlushFile
        adfFlushFile.restype = None
        adfFlushFile.argtypes = [POINTER(struct_File)]
        break

# /mnt/hda4/home/c/adflib/src/adflib.h: 74
for _lib in _libs.values():
    if hasattr(_lib, 'adfFileSeek'):
        adfFileSeek = _lib.adfFileSeek
        adfFileSeek.restype = None
        adfFileSeek.argtypes = [POINTER(struct_File), c_uint32]
        break

# /mnt/hda4/home/c/adflib/src/adflib.h: 77
for _lib in _libs.values():
    if hasattr(_lib, 'adfInstallBootBlock'):
        adfInstallBootBlock = _lib.adfInstallBootBlock
        adfInstallBootBlock.restype = c_int32
        adfInstallBootBlock.argtypes = [POINTER(struct_Volume), POINTER(c_uint8)]
        break

# /mnt/hda4/home/c/adflib/src/adflib.h: 78
for _lib in _libs.values():
    if hasattr(_lib, 'adfMount'):
        adfMount = _lib.adfMount
        adfMount.restype = POINTER(struct_Volume)
        adfMount.argtypes = [POINTER(struct_Device), c_int, c_int]
        break

# /mnt/hda4/home/c/adflib/src/adflib.h: 79
for _lib in _libs.values():
    if hasattr(_lib, 'adfUnMount'):
        adfUnMount = _lib.adfUnMount
        adfUnMount.restype = None
        adfUnMount.argtypes = [POINTER(struct_Volume)]
        break

# /mnt/hda4/home/c/adflib/src/adflib.h: 80
for _lib in _libs.values():
    if hasattr(_lib, 'adfVolumeInfo'):
        adfVolumeInfo = _lib.adfVolumeInfo
        adfVolumeInfo.restype = None
        adfVolumeInfo.argtypes = [POINTER(struct_Volume)]
        break

# /mnt/hda4/home/c/adflib/src/adflib.h: 83
for _lib in _libs.values():
    if hasattr(_lib, 'adfDeviceInfo'):
        adfDeviceInfo = _lib.adfDeviceInfo
        adfDeviceInfo.restype = None
        adfDeviceInfo.argtypes = [POINTER(struct_Device)]
        break

# /mnt/hda4/home/c/adflib/src/adflib.h: 84
for _lib in _libs.values():
    if hasattr(_lib, 'adfMountDev'):
        adfMountDev = _lib.adfMountDev
        adfMountDev.restype = POINTER(struct_Device)
        adfMountDev.argtypes = [String, c_int]
        break

# /mnt/hda4/home/c/adflib/src/adflib.h: 85
for _lib in _libs.values():
    if hasattr(_lib, 'adfUnMountDev'):
        adfUnMountDev = _lib.adfUnMountDev
        adfUnMountDev.restype = None
        adfUnMountDev.argtypes = [POINTER(struct_Device)]
        break

# /mnt/hda4/home/c/adflib/src/adflib.h: 86
for _lib in _libs.values():
    if hasattr(_lib, 'adfCreateHd'):
        adfCreateHd = _lib.adfCreateHd
        adfCreateHd.restype = c_int32
        adfCreateHd.argtypes = [POINTER(struct_Device), c_int, POINTER(POINTER(struct_Partition))]
        break

# /mnt/hda4/home/c/adflib/src/adflib.h: 87
for _lib in _libs.values():
    if hasattr(_lib, 'adfCreateFlop'):
        adfCreateFlop = _lib.adfCreateFlop
        adfCreateFlop.restype = c_int32
        adfCreateFlop.argtypes = [POINTER(struct_Device), String, c_int]
        break

# /mnt/hda4/home/c/adflib/src/adflib.h: 88
for _lib in _libs.values():
    if hasattr(_lib, 'adfCreateHdFile'):
        adfCreateHdFile = _lib.adfCreateHdFile
        adfCreateHdFile.restype = c_int32
        adfCreateHdFile.argtypes = [POINTER(struct_Device), String, c_int]
        break

# /mnt/hda4/home/c/adflib/src/adflib.h: 91
for _lib in _libs.values():
    if hasattr(_lib, 'adfCreateDumpDevice'):
        adfCreateDumpDevice = _lib.adfCreateDumpDevice
        adfCreateDumpDevice.restype = POINTER(struct_Device)
        adfCreateDumpDevice.argtypes = [String, c_int32, c_int32, c_int32]
        break

# /mnt/hda4/home/c/adflib/src/adflib.h: 94
for _lib in _libs.values():
    if hasattr(_lib, 'adfEnvInitDefault'):
        adfEnvInitDefault = _lib.adfEnvInitDefault
        adfEnvInitDefault.restype = None
        adfEnvInitDefault.argtypes = []
        break

# /mnt/hda4/home/c/adflib/src/adflib.h: 95
for _lib in _libs.values():
    if hasattr(_lib, 'adfEnvCleanUp'):
        adfEnvCleanUp = _lib.adfEnvCleanUp
        adfEnvCleanUp.restype = None
        adfEnvCleanUp.argtypes = []
        break

# /mnt/hda4/home/c/adflib/src/adflib.h: 96
for _lib in _libs.values():
    if hasattr(_lib, 'adfChgEnvProp'):
        adfChgEnvProp = _lib.adfChgEnvProp
        adfChgEnvProp.restype = None
        adfChgEnvProp.argtypes = [c_int, POINTER(None)]
        break

# /mnt/hda4/home/c/adflib/src/adflib.h: 97
for _lib in _libs.values():
    if hasattr(_lib, 'adfGetVersionNumber'):
        adfGetVersionNumber = _lib.adfGetVersionNumber
        adfGetVersionNumber.restype = String
        adfGetVersionNumber.argtypes = []
        adfGetVersionNumber.errcheck = ReturnString
        break

# /mnt/hda4/home/c/adflib/src/adflib.h: 98
for _lib in _libs.values():
    if hasattr(_lib, 'adfGetVersionDate'):
        adfGetVersionDate = _lib.adfGetVersionDate
        adfGetVersionDate.restype = String
        adfGetVersionDate.argtypes = []
        adfGetVersionDate.errcheck = ReturnString
        break

# /mnt/hda4/home/c/adflib/src/adflib.h: 100
for _lib in _libs.values():
    if hasattr(_lib, 'adfSetEnvFct'):
        adfSetEnvFct = _lib.adfSetEnvFct
        adfSetEnvFct.restype = None
        adfSetEnvFct.argtypes = [CFUNCTYPE(UNCHECKED(None), String), CFUNCTYPE(UNCHECKED(None), String), CFUNCTYPE(UNCHECKED(None), String)]
        break

# /mnt/hda4/home/c/adflib/src/adflib.h: 103
for _lib in _libs.values():
    if hasattr(_lib, 'adfBlockPtr2EntryName'):
        adfBlockPtr2EntryName = _lib.adfBlockPtr2EntryName
        adfBlockPtr2EntryName.restype = c_int32
        adfBlockPtr2EntryName.argtypes = [POINTER(struct_Volume), c_int32, c_int32, POINTER(POINTER(c_char)), POINTER(c_int32)]
        break

# /mnt/hda4/home/c/adflib/src/adflib.h: 106
for _lib in _libs.values():
    if hasattr(_lib, 'adfGetDelEnt'):
        adfGetDelEnt = _lib.adfGetDelEnt
        adfGetDelEnt.restype = POINTER(struct_List)
        adfGetDelEnt.argtypes = [POINTER(struct_Volume)]
        break

# /mnt/hda4/home/c/adflib/src/adflib.h: 107
for _lib in _libs.values():
    if hasattr(_lib, 'adfUndelEntry'):
        adfUndelEntry = _lib.adfUndelEntry
        adfUndelEntry.restype = c_int32
        adfUndelEntry.argtypes = [POINTER(struct_Volume), c_int32, c_int32]
        break

# /mnt/hda4/home/c/adflib/src/adflib.h: 108
for _lib in _libs.values():
    if hasattr(_lib, 'adfFreeDelList'):
        adfFreeDelList = _lib.adfFreeDelList
        adfFreeDelList.restype = None
        adfFreeDelList.argtypes = [POINTER(struct_List)]
        break

# /mnt/hda4/home/c/adflib/src/adflib.h: 109
for _lib in _libs.values():
    if hasattr(_lib, 'adfCheckEntry'):
        adfCheckEntry = _lib.adfCheckEntry
        adfCheckEntry.restype = c_int32
        adfCheckEntry.argtypes = [POINTER(struct_Volume), c_int32, c_int]
        break

# /mnt/hda4/home/c/adflib/src/adflib.h: 113
for _lib in _libs.values():
    if hasattr(_lib, 'isSectNumValid'):
        isSectNumValid = _lib.isSectNumValid
        isSectNumValid.restype = c_int
        isSectNumValid.argtypes = [POINTER(struct_Volume), c_int32]
        break

# /mnt/hda4/home/c/adflib/src/adflib.h: 117
for _lib in _libs.values():
    if hasattr(_lib, 'adfReadBlock'):
        adfReadBlock = _lib.adfReadBlock
        adfReadBlock.restype = c_int32
        adfReadBlock.argtypes = [POINTER(struct_Volume), c_int32, POINTER(c_uint8)]
        break

# /mnt/hda4/home/c/adflib/src/adflib.h: 118
for _lib in _libs.values():
    if hasattr(_lib, 'adfWriteBlock'):
        adfWriteBlock = _lib.adfWriteBlock
        adfWriteBlock.restype = c_int32
        adfWriteBlock.argtypes = [POINTER(struct_Volume), c_int32, POINTER(c_uint8)]
        break

# /mnt/hda4/home/c/adflib/src/adflib.h: 119
for _lib in _libs.values():
    if hasattr(_lib, 'adfCountFreeBlocks'):
        adfCountFreeBlocks = _lib.adfCountFreeBlocks
        adfCountFreeBlocks.restype = c_int32
        adfCountFreeBlocks.argtypes = [POINTER(struct_Volume)]
        break

_Bool = c_uint8 # <command-line>: 4

__const = c_int # <command-line>: 5

# <command-line>: 8
try:
    CTYPESGEN = 1
except:
    pass

# /mnt/hda4/home/c/adflib/src/adflib.h: 2
try:
    ADFLIB_H = 1
except:
    pass

# /mnt/hda4/home/c/adflib/src/adf_defs.h: 29
try:
    _ADF_DEFS_H = 1
except:
    pass

# /mnt/hda4/home/c/adflib/src/adf_defs.h: 31
try:
    ADFLIB_VERSION = '0.7.11a'
except:
    pass

# /mnt/hda4/home/c/adflib/src/adf_defs.h: 32
try:
    ADFLIB_DATE = 'January 20th, 2007'
except:
    pass

SECTNUM = c_int32 # /mnt/hda4/home/c/adflib/src/adf_defs.h: 34

RETCODE = c_int32 # /mnt/hda4/home/c/adflib/src/adf_defs.h: 35

# /mnt/hda4/home/c/adflib/src/adf_defs.h: 37
try:
    TRUE = 1
except:
    pass

# /mnt/hda4/home/c/adflib/src/adf_defs.h: 38
try:
    FALSE = 0
except:
    pass

# /usr/include/stdint.h: 24
try:
    _STDINT_H = 1
except:
    pass

# /usr/include/features.h: 20
try:
    _FEATURES_H = 1
except:
    pass

# /usr/include/features.h: 123
try:
    __USE_ANSI = 1
except:
    pass

# /usr/include/features.h: 136
def __GNUC_PREREQ(maj, min):
    return 0

# /usr/include/features.h: 176
try:
    _BSD_SOURCE = 1
except:
    pass

# /usr/include/features.h: 177
try:
    _SVID_SOURCE = 1
except:
    pass

# /usr/include/features.h: 199
try:
    _POSIX_SOURCE = 1
except:
    pass

# /usr/include/features.h: 205
try:
    _POSIX_C_SOURCE = 200112L
except:
    pass

# /usr/include/features.h: 210
try:
    __USE_POSIX = 1
except:
    pass

# /usr/include/features.h: 214
try:
    __USE_POSIX2 = 1
except:
    pass

# /usr/include/features.h: 218
try:
    __USE_POSIX199309 = 1
except:
    pass

# /usr/include/features.h: 222
try:
    __USE_POSIX199506 = 1
except:
    pass

# /usr/include/features.h: 226
try:
    __USE_XOPEN2K = 1
except:
    pass

# /usr/include/features.h: 261
try:
    __USE_MISC = 1
except:
    pass

# /usr/include/features.h: 265
try:
    __USE_BSD = 1
except:
    pass

# /usr/include/features.h: 269
try:
    __USE_SVID = 1
except:
    pass

# /usr/include/features.h: 292
try:
    __USE_FORTIFY_LEVEL = 0
except:
    pass

# /usr/include/features.h: 296
try:
    __STDC_IEC_559__ = 1
except:
    pass

# /usr/include/features.h: 297
try:
    __STDC_IEC_559_COMPLEX__ = 1
except:
    pass

# /usr/include/features.h: 300
try:
    __STDC_ISO_10646__ = 200009L
except:
    pass

# /usr/include/features.h: 309
try:
    __GNU_LIBRARY__ = 6
except:
    pass

# /usr/include/features.h: 313
try:
    __GLIBC__ = 2
except:
    pass

# /usr/include/features.h: 314
try:
    __GLIBC_MINOR__ = 9
except:
    pass

# /usr/include/features.h: 316
def __GLIBC_PREREQ(maj, min):
    return (((__GLIBC__ << 16) + __GLIBC_MINOR__) >= ((maj << 16) + min))

# /usr/include/sys/cdefs.h: 21
try:
    _SYS_CDEFS_H = 1
except:
    pass

# /usr/include/sys/cdefs.h: 64
def __NTH(fct):
    return fct

__const = c_int # /usr/include/sys/cdefs.h: 66

__signed = c_int # /usr/include/sys/cdefs.h: 67

__volatile = c_int # /usr/include/sys/cdefs.h: 68

# /usr/include/sys/cdefs.h: 74
def __P(args):
    return args

# /usr/include/sys/cdefs.h: 75
def __PMT(args):
    return args

# /usr/include/sys/cdefs.h: 81
def __STRING(x):
    return x

__ptr_t = POINTER(None) # /usr/include/sys/cdefs.h: 84

# /usr/include/bits/wordsize.h: 19
try:
    __WORDSIZE = 32
except:
    pass

# /usr/include/sys/cdefs.h: 370
def __LDBL_REDIR1(name, proto, alias):
    return (name + proto)

# /usr/include/sys/cdefs.h: 371
def __LDBL_REDIR(name, proto):
    return (name + proto)

# /usr/include/bits/wordsize.h: 19
try:
    __WORDSIZE = 32
except:
    pass

# /usr/include/bits/wchar.h: 21
try:
    _BITS_WCHAR_H = 1
except:
    pass

# /usr/include/bits/wchar.h: 23
try:
    __WCHAR_MIN = ((-2147483647L) - 1L)
except:
    pass

# /usr/include/bits/wchar.h: 24
try:
    __WCHAR_MAX = 2147483647L
except:
    pass

# /usr/include/bits/wordsize.h: 19
try:
    __WORDSIZE = 32
except:
    pass

# /usr/include/stdint.h: 160
try:
    INT8_MIN = (-128)
except:
    pass

# /usr/include/stdint.h: 161
try:
    INT16_MIN = ((-32767) - 1)
except:
    pass

# /usr/include/stdint.h: 162
try:
    INT32_MIN = ((-2147483647) - 1)
except:
    pass

# /usr/include/stdint.h: 165
try:
    INT8_MAX = 127
except:
    pass

# /usr/include/stdint.h: 166
try:
    INT16_MAX = 32767
except:
    pass

# /usr/include/stdint.h: 167
try:
    INT32_MAX = 2147483647
except:
    pass

# /usr/include/stdint.h: 171
try:
    UINT8_MAX = 255
except:
    pass

# /usr/include/stdint.h: 172
try:
    UINT16_MAX = 65535
except:
    pass

# /usr/include/stdint.h: 173
try:
    UINT32_MAX = 4294967295L
except:
    pass

# /usr/include/stdint.h: 178
try:
    INT_LEAST8_MIN = (-128)
except:
    pass

# /usr/include/stdint.h: 179
try:
    INT_LEAST16_MIN = ((-32767) - 1)
except:
    pass

# /usr/include/stdint.h: 180
try:
    INT_LEAST32_MIN = ((-2147483647) - 1)
except:
    pass

# /usr/include/stdint.h: 183
try:
    INT_LEAST8_MAX = 127
except:
    pass

# /usr/include/stdint.h: 184
try:
    INT_LEAST16_MAX = 32767
except:
    pass

# /usr/include/stdint.h: 185
try:
    INT_LEAST32_MAX = 2147483647
except:
    pass

# /usr/include/stdint.h: 189
try:
    UINT_LEAST8_MAX = 255
except:
    pass

# /usr/include/stdint.h: 190
try:
    UINT_LEAST16_MAX = 65535
except:
    pass

# /usr/include/stdint.h: 191
try:
    UINT_LEAST32_MAX = 4294967295L
except:
    pass

# /usr/include/stdint.h: 196
try:
    INT_FAST8_MIN = (-128)
except:
    pass

# /usr/include/stdint.h: 201
try:
    INT_FAST16_MIN = ((-2147483647) - 1)
except:
    pass

# /usr/include/stdint.h: 202
try:
    INT_FAST32_MIN = ((-2147483647) - 1)
except:
    pass

# /usr/include/stdint.h: 206
try:
    INT_FAST8_MAX = 127
except:
    pass

# /usr/include/stdint.h: 211
try:
    INT_FAST16_MAX = 2147483647
except:
    pass

# /usr/include/stdint.h: 212
try:
    INT_FAST32_MAX = 2147483647
except:
    pass

# /usr/include/stdint.h: 217
try:
    UINT_FAST8_MAX = 255
except:
    pass

# /usr/include/stdint.h: 222
try:
    UINT_FAST16_MAX = 4294967295L
except:
    pass

# /usr/include/stdint.h: 223
try:
    UINT_FAST32_MAX = 4294967295L
except:
    pass

# /usr/include/stdint.h: 234
try:
    INTPTR_MIN = ((-2147483647) - 1)
except:
    pass

# /usr/include/stdint.h: 235
try:
    INTPTR_MAX = 2147483647
except:
    pass

# /usr/include/stdint.h: 236
try:
    UINTPTR_MAX = 4294967295L
except:
    pass

# /usr/include/stdint.h: 256
try:
    PTRDIFF_MIN = ((-2147483647) - 1)
except:
    pass

# /usr/include/stdint.h: 257
try:
    PTRDIFF_MAX = 2147483647
except:
    pass

# /usr/include/stdint.h: 261
try:
    SIG_ATOMIC_MIN = ((-2147483647) - 1)
except:
    pass

# /usr/include/stdint.h: 262
try:
    SIG_ATOMIC_MAX = 2147483647
except:
    pass

# /usr/include/stdint.h: 268
try:
    SIZE_MAX = 4294967295L
except:
    pass

# /usr/include/stdint.h: 274
try:
    WCHAR_MIN = __WCHAR_MIN
except:
    pass

# /usr/include/stdint.h: 275
try:
    WCHAR_MAX = __WCHAR_MAX
except:
    pass

# /usr/include/stdint.h: 279
try:
    WINT_MIN = 0
except:
    pass

# /usr/include/stdint.h: 280
try:
    WINT_MAX = 4294967295L
except:
    pass

# /usr/include/stdint.h: 290
def INT8_C(c):
    return c

# /usr/include/stdint.h: 291
def INT16_C(c):
    return c

# /usr/include/stdint.h: 292
def INT32_C(c):
    return c

# /usr/include/stdint.h: 300
def UINT8_C(c):
    return c

# /usr/include/stdint.h: 301
def UINT16_C(c):
    return c

ULONG = c_uint32 # /mnt/hda4/home/c/adflib/src/adf_defs.h: 41

USHORT = c_uint16 # /mnt/hda4/home/c/adflib/src/adf_defs.h: 42

UCHAR = c_uint8 # /mnt/hda4/home/c/adflib/src/adf_defs.h: 43

BOOL = c_int # /mnt/hda4/home/c/adflib/src/adf_defs.h: 44

# /mnt/hda4/home/c/adflib/src/adf_defs.h: 50
def max(a, b):
    return (a > b) and a or b

# /mnt/hda4/home/c/adflib/src/adf_defs.h: 53
def min(a, b):
    return (a < b) and a or b

# /mnt/hda4/home/c/adflib/src/adf_defs.h: 59
def Short(p):
    return (((p [0]) << 8) | (p [1]))

# /mnt/hda4/home/c/adflib/src/adf_defs.h: 60
def Long(p):
    return ((((Short (p)).value) << 16) | ((Short ((p + 2))).value))

# /mnt/hda4/home/c/adflib/src/adf_defs.h: 65
def swapShort(p):
    return (((p [0]) << 8) | (p [1]))

# /mnt/hda4/home/c/adflib/src/adf_defs.h: 66
def swapLong(p):
    return ((((swapShort (p)).value) << 16) | ((swapShort ((p + 2))).value))

# /mnt/hda4/home/c/adflib/src/adf_str.h: 2
try:
    _ADF_STR_H = 1
except:
    pass

# /usr/include/stdio.h: 27
try:
    _STDIO_H = 1
except:
    pass

# /usr/include/bits/types.h: 25
try:
    _BITS_TYPES_H = 1
except:
    pass

# /usr/include/bits/wordsize.h: 19
try:
    __WORDSIZE = 32
except:
    pass

__S16_TYPE = c_int # /usr/include/bits/types.h: 99

__U16_TYPE = c_uint # /usr/include/bits/types.h: 100

__S32_TYPE = c_int # /usr/include/bits/types.h: 101

__U32_TYPE = c_uint # /usr/include/bits/types.h: 102

__SLONGWORD_TYPE = c_long # /usr/include/bits/types.h: 103

__ULONGWORD_TYPE = c_ulong # /usr/include/bits/types.h: 104

__SQUAD_TYPE = __quad_t # /usr/include/bits/types.h: 106

__UQUAD_TYPE = __u_quad_t # /usr/include/bits/types.h: 107

__SWORD_TYPE = c_int # /usr/include/bits/types.h: 108

__UWORD_TYPE = c_uint # /usr/include/bits/types.h: 109

__SLONG32_TYPE = c_long # /usr/include/bits/types.h: 110

__ULONG32_TYPE = c_ulong # /usr/include/bits/types.h: 111

__S64_TYPE = __quad_t # /usr/include/bits/types.h: 112

__U64_TYPE = __u_quad_t # /usr/include/bits/types.h: 113

# /usr/include/bits/typesizes.h: 25
try:
    _BITS_TYPESIZES_H = 1
except:
    pass

__TIMER_T_TYPE = POINTER(None) # /usr/include/bits/typesizes.h: 57

# /usr/include/bits/typesizes.h: 59
class struct_anon_8(Structure):
    pass

struct_anon_8.__slots__ = [
    '__val',
]
struct_anon_8._fields_ = [
    ('__val', c_int * 2),
]

__FSID_T_TYPE = struct_anon_8 # /usr/include/bits/typesizes.h: 59

# /usr/include/bits/typesizes.h: 63
try:
    __FD_SETSIZE = 1024
except:
    pass

# /usr/include/stdio.h: 57
try:
    __FILE_defined = 1
except:
    pass

# /usr/include/stdio.h: 67
try:
    ____FILE_defined = 1
except:
    pass

# /usr/include/_G_config.h: 5
try:
    _G_config_h = 1
except:
    pass

# /usr/include/wchar.h: 76
try:
    __mbstate_t_defined = 1
except:
    pass

_G_size_t = c_size_t # /usr/include/_G_config.h: 21

_G_ssize_t = __ssize_t # /usr/include/_G_config.h: 32

_G_off_t = __off_t # /usr/include/_G_config.h: 33

_G_off64_t = __off64_t # /usr/include/_G_config.h: 34

_G_pid_t = __pid_t # /usr/include/_G_config.h: 35

_G_uid_t = __uid_t # /usr/include/_G_config.h: 36

_G_wchar_t = c_wchar # /usr/include/_G_config.h: 37

# /usr/include/_G_config.h: 58
try:
    _G_HAVE_BOOL = 1
except:
    pass

# /usr/include/_G_config.h: 62
try:
    _G_HAVE_ATEXIT = 1
except:
    pass

# /usr/include/_G_config.h: 63
try:
    _G_HAVE_SYS_CDEFS = 1
except:
    pass

# /usr/include/_G_config.h: 64
try:
    _G_HAVE_SYS_WAIT = 1
except:
    pass

# /usr/include/_G_config.h: 65
try:
    _G_NEED_STDARG_H = 1
except:
    pass

# /usr/include/_G_config.h: 68
try:
    _G_HAVE_PRINTF_FP = 1
except:
    pass

# /usr/include/_G_config.h: 69
try:
    _G_HAVE_MMAP = 1
except:
    pass

# /usr/include/_G_config.h: 70
try:
    _G_HAVE_MREMAP = 1
except:
    pass

# /usr/include/_G_config.h: 71
try:
    _G_HAVE_LONG_DOUBLE_IO = 1
except:
    pass

# /usr/include/_G_config.h: 72
try:
    _G_HAVE_IO_FILE_OPEN = 1
except:
    pass

# /usr/include/_G_config.h: 73
try:
    _G_HAVE_IO_GETLINE_INFO = 1
except:
    pass

# /usr/include/_G_config.h: 75
try:
    _G_IO_IO_FILE_VERSION = 131073
except:
    pass

# /usr/include/_G_config.h: 85
try:
    _G_BUFSIZ = 8192
except:
    pass

# /usr/include/_G_config.h: 88
try:
    _G_NAMES_HAVE_UNDERSCORE = 0
except:
    pass

# /usr/include/_G_config.h: 89
try:
    _G_VTABLE_LABEL_HAS_LENGTH = 1
except:
    pass

# /usr/include/_G_config.h: 90
try:
    _G_USING_THUNKS = 1
except:
    pass

# /usr/include/_G_config.h: 91
try:
    _G_VTABLE_LABEL_PREFIX = '__vt_'
except:
    pass

# /usr/include/_G_config.h: 96
def _G_ARGS(ARGLIST):
    return ARGLIST

_IO_pos_t = _G_fpos_t # /usr/include/libio.h: 34

_IO_fpos_t = _G_fpos_t # /usr/include/libio.h: 35

_IO_fpos64_t = _G_fpos64_t # /usr/include/libio.h: 36

# /usr/include/libio.h: 44
try:
    _IO_HAVE_SYS_WAIT = _G_HAVE_SYS_WAIT
except:
    pass

# /usr/include/libio.h: 46
try:
    _IO_BUFSIZ = _G_BUFSIZ
except:
    pass

# /usr/include/libio.h: 76
def _PARAMS(protos):
    return (__P (protos))

# /usr/include/libio.h: 84
try:
    _IO_UNIFIED_JUMPTABLES = 1
except:
    pass

# /usr/include/libio.h: 90
try:
    EOF = (-1)
except:
    pass

# /usr/include/libio.h: 105
try:
    _IOS_INPUT = 1
except:
    pass

# /usr/include/libio.h: 106
try:
    _IOS_OUTPUT = 2
except:
    pass

# /usr/include/libio.h: 107
try:
    _IOS_ATEND = 4
except:
    pass

# /usr/include/libio.h: 108
try:
    _IOS_APPEND = 8
except:
    pass

# /usr/include/libio.h: 109
try:
    _IOS_TRUNC = 16
except:
    pass

# /usr/include/libio.h: 110
try:
    _IOS_NOCREATE = 32
except:
    pass

# /usr/include/libio.h: 111
try:
    _IOS_NOREPLACE = 64
except:
    pass

# /usr/include/libio.h: 112
try:
    _IOS_BIN = 128
except:
    pass

# /usr/include/libio.h: 120
try:
    _IO_MAGIC = 4222418944L
except:
    pass

# /usr/include/libio.h: 121
try:
    _OLD_STDIO_MAGIC = 4206624768L
except:
    pass

# /usr/include/libio.h: 122
try:
    _IO_MAGIC_MASK = 4294901760L
except:
    pass

# /usr/include/libio.h: 123
try:
    _IO_USER_BUF = 1
except:
    pass

# /usr/include/libio.h: 124
try:
    _IO_UNBUFFERED = 2
except:
    pass

# /usr/include/libio.h: 125
try:
    _IO_NO_READS = 4
except:
    pass

# /usr/include/libio.h: 126
try:
    _IO_NO_WRITES = 8
except:
    pass

# /usr/include/libio.h: 127
try:
    _IO_EOF_SEEN = 16
except:
    pass

# /usr/include/libio.h: 128
try:
    _IO_ERR_SEEN = 32
except:
    pass

# /usr/include/libio.h: 129
try:
    _IO_DELETE_DONT_CLOSE = 64
except:
    pass

# /usr/include/libio.h: 130
try:
    _IO_LINKED = 128
except:
    pass

# /usr/include/libio.h: 131
try:
    _IO_IN_BACKUP = 256
except:
    pass

# /usr/include/libio.h: 132
try:
    _IO_LINE_BUF = 512
except:
    pass

# /usr/include/libio.h: 133
try:
    _IO_TIED_PUT_GET = 1024
except:
    pass

# /usr/include/libio.h: 134
try:
    _IO_CURRENTLY_PUTTING = 2048
except:
    pass

# /usr/include/libio.h: 135
try:
    _IO_IS_APPENDING = 4096
except:
    pass

# /usr/include/libio.h: 136
try:
    _IO_IS_FILEBUF = 8192
except:
    pass

# /usr/include/libio.h: 137
try:
    _IO_BAD_SEEN = 16384
except:
    pass

# /usr/include/libio.h: 138
try:
    _IO_USER_LOCK = 32768
except:
    pass

# /usr/include/libio.h: 140
try:
    _IO_FLAGS2_MMAP = 1
except:
    pass

# /usr/include/libio.h: 141
try:
    _IO_FLAGS2_NOTCANCEL = 2
except:
    pass

# /usr/include/libio.h: 145
try:
    _IO_FLAGS2_USER_WBUF = 8
except:
    pass

# /usr/include/libio.h: 151
try:
    _IO_SKIPWS = 1
except:
    pass

# /usr/include/libio.h: 152
try:
    _IO_LEFT = 2
except:
    pass

# /usr/include/libio.h: 153
try:
    _IO_RIGHT = 4
except:
    pass

# /usr/include/libio.h: 154
try:
    _IO_INTERNAL = 10
except:
    pass

# /usr/include/libio.h: 155
try:
    _IO_DEC = 20
except:
    pass

# /usr/include/libio.h: 156
try:
    _IO_OCT = 40
except:
    pass

# /usr/include/libio.h: 157
try:
    _IO_HEX = 100
except:
    pass

# /usr/include/libio.h: 158
try:
    _IO_SHOWBASE = 200
except:
    pass

# /usr/include/libio.h: 159
try:
    _IO_SHOWPOINT = 400
except:
    pass

# /usr/include/libio.h: 160
try:
    _IO_UPPERCASE = 1000
except:
    pass

# /usr/include/libio.h: 161
try:
    _IO_SHOWPOS = 2000
except:
    pass

# /usr/include/libio.h: 162
try:
    _IO_SCIENTIFIC = 4000
except:
    pass

# /usr/include/libio.h: 163
try:
    _IO_FIXED = 10000
except:
    pass

# /usr/include/libio.h: 164
try:
    _IO_UNITBUF = 20000
except:
    pass

# /usr/include/libio.h: 165
try:
    _IO_STDIO = 40000
except:
    pass

# /usr/include/libio.h: 166
try:
    _IO_DONT_CLOSE = 100000
except:
    pass

# /usr/include/libio.h: 167
try:
    _IO_BOOLALPHA = 200000
except:
    pass

# /usr/include/libio.h: 350
try:
    _IO_stdin = pointer(_IO_2_1_stdin_)
except:
    pass

# /usr/include/libio.h: 351
try:
    _IO_stdout = pointer(_IO_2_1_stdout_)
except:
    pass

# /usr/include/libio.h: 352
try:
    _IO_stderr = pointer(_IO_2_1_stderr_)
except:
    pass

# /usr/include/libio.h: 428
def _IO_BE(expr, res):
    return expr

# /usr/include/libio.h: 431
def _IO_getc_unlocked(_fp):
    return (_IO_BE ((((_fp.contents._IO_read_ptr).value) >= ((_fp.contents._IO_read_end).value)), 0)) and (__uflow (_fp)) or ((((_fp.contents._IO_read_ptr).value) + 1)[0])

# /usr/include/libio.h: 434
def _IO_peekc_unlocked(_fp):
    return ((_IO_BE ((((_fp.contents._IO_read_ptr).value) >= ((_fp.contents._IO_read_end).value)), 0)) and (((__underflow (_fp)).value) == EOF)) and EOF or ((_fp.contents._IO_read_ptr)[0])

# /usr/include/libio.h: 438
def _IO_putc_unlocked(_ch, _fp):
    return (_IO_BE ((((_fp.contents._IO_write_ptr).value) >= ((_fp.contents._IO_write_end).value)), 0)) and (__overflow (_fp, _ch)) or _ch

# /usr/include/libio.h: 455
def _IO_feof_unlocked(__fp):
    return ((((__fp.contents._flags).value) & _IO_EOF_SEEN) != 0)

# /usr/include/libio.h: 456
def _IO_ferror_unlocked(__fp):
    return ((((__fp.contents._flags).value) & _IO_ERR_SEEN) != 0)

# /usr/include/libio.h: 466
def _IO_PENDING_OUTPUT_COUNT(_fp):
    return (((_fp.contents._IO_write_ptr).value) - ((_fp.contents._IO_write_base).value))

# /usr/include/libio.h: 480
def _IO_peekc(_fp):
    return (_IO_peekc_unlocked (_fp))

# /usr/include/stdio.h: 101
try:
    _IOFBF = 0
except:
    pass

# /usr/include/stdio.h: 102
try:
    _IOLBF = 1
except:
    pass

# /usr/include/stdio.h: 103
try:
    _IONBF = 2
except:
    pass

# /usr/include/stdio.h: 108
try:
    BUFSIZ = _IO_BUFSIZ
except:
    pass

# /usr/include/stdio.h: 121
try:
    SEEK_SET = 0
except:
    pass

# /usr/include/stdio.h: 122
try:
    SEEK_CUR = 1
except:
    pass

# /usr/include/stdio.h: 123
try:
    SEEK_END = 2
except:
    pass

# /usr/include/stdio.h: 128
try:
    P_tmpdir = '/tmp'
except:
    pass

# /usr/include/bits/stdio_lim.h: 24
try:
    L_tmpnam = 20
except:
    pass

# /usr/include/bits/stdio_lim.h: 25
try:
    TMP_MAX = 238328
except:
    pass

# /usr/include/bits/stdio_lim.h: 26
try:
    FILENAME_MAX = 4096
except:
    pass

# /usr/include/bits/stdio_lim.h: 29
try:
    L_ctermid = 9
except:
    pass

# /usr/include/bits/stdio_lim.h: 30
try:
    L_cuserid = 9
except:
    pass

# /usr/include/bits/stdio_lim.h: 36
try:
    FOPEN_MAX = 16
except:
    pass

# /usr/include/stdio.h: 149
try:
    stdin = stdin
except:
    pass

# /usr/include/stdio.h: 150
try:
    stdout = stdout
except:
    pass

# /usr/include/stdio.h: 151
try:
    stderr = stderr
except:
    pass

# /usr/include/stdio.h: 521
def getc(_fp):
    return (_IO_getc (_fp))

# /usr/include/stdio.h: 563
def putc(_ch, _fp):
    return (_IO_putc (_ch, _fp))

# /mnt/hda4/home/c/adflib/src/adf_blk.h: 30
try:
    ADF_BLK_H = 1
except:
    pass

ULONG = c_uint32 # /mnt/hda4/home/c/adflib/src/adf_blk.h: 32

USHORT = c_uint16 # /mnt/hda4/home/c/adflib/src/adf_blk.h: 33

UCHAR = c_uint8 # /mnt/hda4/home/c/adflib/src/adf_blk.h: 34

# /mnt/hda4/home/c/adflib/src/adf_blk.h: 36
try:
    LOGICAL_BLOCK_SIZE = 512
except:
    pass

# /mnt/hda4/home/c/adflib/src/adf_blk.h: 40
try:
    FSMASK_FFS = 1
except:
    pass

# /mnt/hda4/home/c/adflib/src/adf_blk.h: 41
try:
    FSMASK_INTL = 2
except:
    pass

# /mnt/hda4/home/c/adflib/src/adf_blk.h: 42
try:
    FSMASK_DIRCACHE = 4
except:
    pass

# /mnt/hda4/home/c/adflib/src/adf_blk.h: 44
def isFFS(c):
    return (c & FSMASK_FFS)

# /mnt/hda4/home/c/adflib/src/adf_blk.h: 45
def isOFS(c):
    return (not (c & FSMASK_FFS))

# /mnt/hda4/home/c/adflib/src/adf_blk.h: 46
def isINTL(c):
    return (c & FSMASK_INTL)

# /mnt/hda4/home/c/adflib/src/adf_blk.h: 47
def isDIRCACHE(c):
    return (c & FSMASK_DIRCACHE)

# /mnt/hda4/home/c/adflib/src/adf_blk.h: 54
try:
    ACCMASK_D = (1 << 0)
except:
    pass

# /mnt/hda4/home/c/adflib/src/adf_blk.h: 55
try:
    ACCMASK_E = (1 << 1)
except:
    pass

# /mnt/hda4/home/c/adflib/src/adf_blk.h: 56
try:
    ACCMASK_W = (1 << 2)
except:
    pass

# /mnt/hda4/home/c/adflib/src/adf_blk.h: 57
try:
    ACCMASK_R = (1 << 3)
except:
    pass

# /mnt/hda4/home/c/adflib/src/adf_blk.h: 58
try:
    ACCMASK_A = (1 << 4)
except:
    pass

# /mnt/hda4/home/c/adflib/src/adf_blk.h: 59
try:
    ACCMASK_P = (1 << 5)
except:
    pass

# /mnt/hda4/home/c/adflib/src/adf_blk.h: 60
try:
    ACCMASK_S = (1 << 6)
except:
    pass

# /mnt/hda4/home/c/adflib/src/adf_blk.h: 61
try:
    ACCMASK_H = (1 << 7)
except:
    pass

# /mnt/hda4/home/c/adflib/src/adf_blk.h: 63
def hasD(c):
    return (c & ACCMASK_D)

# /mnt/hda4/home/c/adflib/src/adf_blk.h: 64
def hasE(c):
    return (c & ACCMASK_E)

# /mnt/hda4/home/c/adflib/src/adf_blk.h: 65
def hasW(c):
    return (c & ACCMASK_W)

# /mnt/hda4/home/c/adflib/src/adf_blk.h: 66
def hasR(c):
    return (c & ACCMASK_R)

# /mnt/hda4/home/c/adflib/src/adf_blk.h: 67
def hasA(c):
    return (c & ACCMASK_A)

# /mnt/hda4/home/c/adflib/src/adf_blk.h: 68
def hasP(c):
    return (c & ACCMASK_P)

# /mnt/hda4/home/c/adflib/src/adf_blk.h: 69
def hasS(c):
    return (c & ACCMASK_S)

# /mnt/hda4/home/c/adflib/src/adf_blk.h: 70
def hasH(c):
    return (c & ACCMASK_H)

# /mnt/hda4/home/c/adflib/src/adf_blk.h: 77
try:
    BM_VALID = (-1)
except:
    pass

# /mnt/hda4/home/c/adflib/src/adf_blk.h: 78
try:
    BM_INVALID = 0
except:
    pass

# /mnt/hda4/home/c/adflib/src/adf_blk.h: 80
try:
    HT_SIZE = 72
except:
    pass

# /mnt/hda4/home/c/adflib/src/adf_blk.h: 81
try:
    BM_SIZE = 25
except:
    pass

# /mnt/hda4/home/c/adflib/src/adf_blk.h: 82
try:
    MAX_DATABLK = 72
except:
    pass

# /mnt/hda4/home/c/adflib/src/adf_blk.h: 84
try:
    MAXNAMELEN = 30
except:
    pass

# /mnt/hda4/home/c/adflib/src/adf_blk.h: 85
try:
    MAXCMMTLEN = 79
except:
    pass

# /mnt/hda4/home/c/adflib/src/adf_blk.h: 90
try:
    T_HEADER = 2
except:
    pass

# /mnt/hda4/home/c/adflib/src/adf_blk.h: 91
try:
    ST_ROOT = 1
except:
    pass

# /mnt/hda4/home/c/adflib/src/adf_blk.h: 92
try:
    ST_DIR = 2
except:
    pass

# /mnt/hda4/home/c/adflib/src/adf_blk.h: 93
try:
    ST_FILE = (-3)
except:
    pass

# /mnt/hda4/home/c/adflib/src/adf_blk.h: 94
try:
    ST_LFILE = (-4)
except:
    pass

# /mnt/hda4/home/c/adflib/src/adf_blk.h: 95
try:
    ST_LDIR = 4
except:
    pass

# /mnt/hda4/home/c/adflib/src/adf_blk.h: 96
try:
    ST_LSOFT = 3
except:
    pass

# /mnt/hda4/home/c/adflib/src/adf_blk.h: 97
try:
    T_LIST = 16
except:
    pass

# /mnt/hda4/home/c/adflib/src/adf_blk.h: 98
try:
    T_DATA = 8
except:
    pass

# /mnt/hda4/home/c/adflib/src/adf_blk.h: 99
try:
    T_DIRC = 33
except:
    pass

# /mnt/hda4/home/c/adflib/src/adf_err.h: 30
def hasRC(rc, c):
    return (rc & c)

# /mnt/hda4/home/c/adflib/src/adf_err.h: 32
try:
    RC_OK = 0
except:
    pass

# /mnt/hda4/home/c/adflib/src/adf_err.h: 33
try:
    RC_ERROR = (-1)
except:
    pass

# /mnt/hda4/home/c/adflib/src/adf_err.h: 35
try:
    RC_MALLOC = 1
except:
    pass

# /mnt/hda4/home/c/adflib/src/adf_err.h: 36
try:
    RC_VOLFULL = 2
except:
    pass

# /mnt/hda4/home/c/adflib/src/adf_err.h: 39
try:
    RC_FOPEN = (1 << 10)
except:
    pass

# /mnt/hda4/home/c/adflib/src/adf_err.h: 40
try:
    RC_NULLPTR = (1 << 12)
except:
    pass

# /mnt/hda4/home/c/adflib/src/adf_err.h: 44
try:
    RC_BLOCKTYPE = 1
except:
    pass

# /mnt/hda4/home/c/adflib/src/adf_err.h: 45
try:
    RC_BLOCKSTYPE = (1 << 1)
except:
    pass

# /mnt/hda4/home/c/adflib/src/adf_err.h: 46
try:
    RC_BLOCKSUM = (1 << 2)
except:
    pass

# /mnt/hda4/home/c/adflib/src/adf_err.h: 47
try:
    RC_HEADERKEY = (1 << 3)
except:
    pass

# /mnt/hda4/home/c/adflib/src/adf_err.h: 48
try:
    RC_BLOCKREAD = (1 << 4)
except:
    pass

# /mnt/hda4/home/c/adflib/src/adf_err.h: 51
try:
    RC_BLOCKWRITE = (1 << 4)
except:
    pass

# /mnt/hda4/home/c/adflib/src/adf_err.h: 55
try:
    RC_BLOCKOUTOFRANGE = 1
except:
    pass

# /mnt/hda4/home/c/adflib/src/adf_err.h: 56
try:
    RC_BLOCKNATREAD = (1 << 1)
except:
    pass

# /mnt/hda4/home/c/adflib/src/adf_err.h: 60
try:
    RC_BLOCKNATWRITE = (1 << 1)
except:
    pass

# /mnt/hda4/home/c/adflib/src/adf_err.h: 61
try:
    RC_BLOCKREADONLY = (1 << 2)
except:
    pass

# /mnt/hda4/home/c/adflib/src/adf_err.h: 69
try:
    RC_BLOCKSHORTREAD = 1
except:
    pass

# /mnt/hda4/home/c/adflib/src/adf_err.h: 70
try:
    RC_BLOCKFSEEK = (1 << 1)
except:
    pass

# /mnt/hda4/home/c/adflib/src/adf_err.h: 74
try:
    RC_BLOCKSHORTWRITE = 1
except:
    pass

# /mnt/hda4/home/c/adflib/src/adf_err.h: 79
try:
    RC_BLOCKID = (1 << 5)
except:
    pass

# /mnt/hda4/home/c/adflib/src/adf_str.h: 74
try:
    DEVTYPE_FLOPDD = 1
except:
    pass

# /mnt/hda4/home/c/adflib/src/adf_str.h: 75
try:
    DEVTYPE_FLOPHD = 2
except:
    pass

# /mnt/hda4/home/c/adflib/src/adf_str.h: 76
try:
    DEVTYPE_HARDDISK = 3
except:
    pass

# /mnt/hda4/home/c/adflib/src/adf_str.h: 77
try:
    DEVTYPE_HARDFILE = 4
except:
    pass

# /mnt/hda4/home/c/adflib/src/adf_str.h: 149
try:
    PR_VFCT = 1
except:
    pass

# /mnt/hda4/home/c/adflib/src/adf_str.h: 150
try:
    PR_WFCT = 2
except:
    pass

# /mnt/hda4/home/c/adflib/src/adf_str.h: 151
try:
    PR_EFCT = 3
except:
    pass

# /mnt/hda4/home/c/adflib/src/adf_str.h: 152
try:
    PR_NOTFCT = 4
except:
    pass

# /mnt/hda4/home/c/adflib/src/adf_str.h: 153
try:
    PR_USEDIRC = 5
except:
    pass

# /mnt/hda4/home/c/adflib/src/adf_str.h: 154
try:
    PR_USE_NOTFCT = 6
except:
    pass

# /mnt/hda4/home/c/adflib/src/adf_str.h: 155
try:
    PR_PROGBAR = 7
except:
    pass

# /mnt/hda4/home/c/adflib/src/adf_str.h: 156
try:
    PR_USE_PROGBAR = 8
except:
    pass

# /mnt/hda4/home/c/adflib/src/adf_str.h: 157
try:
    PR_RWACCESS = 9
except:
    pass

# /mnt/hda4/home/c/adflib/src/adf_str.h: 158
try:
    PR_USE_RWACCESS = 10
except:
    pass

_IO_FILE = struct__IO_FILE # /usr/include/libio.h: 271

_IO_jump_t = struct__IO_jump_t # /usr/include/libio.h: 170

_IO_marker = struct__IO_marker # /usr/include/libio.h: 186

_IO_FILE_plus = struct__IO_FILE_plus # /usr/include/libio.h: 344

bBootBlock = struct_bBootBlock # /mnt/hda4/home/c/adflib/src/adf_blk.h: 105

bRootBlock = struct_bRootBlock # /mnt/hda4/home/c/adflib/src/adf_blk.h: 113

bFileHeaderBlock = struct_bFileHeaderBlock # /mnt/hda4/home/c/adflib/src/adf_blk.h: 143

bFileExtBlock = struct_bFileExtBlock # /mnt/hda4/home/c/adflib/src/adf_blk.h: 176

bDirBlock = struct_bDirBlock # /mnt/hda4/home/c/adflib/src/adf_blk.h: 194

bOFSDataBlock = struct_bOFSDataBlock # /mnt/hda4/home/c/adflib/src/adf_blk.h: 225

bBitmapBlock = struct_bBitmapBlock # /mnt/hda4/home/c/adflib/src/adf_blk.h: 238

bBitmapExtBlock = struct_bBitmapExtBlock # /mnt/hda4/home/c/adflib/src/adf_blk.h: 244

bLinkBlock = struct_bLinkBlock # /mnt/hda4/home/c/adflib/src/adf_blk.h: 250

bDirCacheBlock = struct_bDirCacheBlock # /mnt/hda4/home/c/adflib/src/adf_blk.h: 276

Device = struct_Device # /mnt/hda4/home/c/adflib/src/adf_str.h: 79

Volume = struct_Volume # /mnt/hda4/home/c/adflib/src/adf_str.h: 39

Partition = struct_Partition # /mnt/hda4/home/c/adflib/src/adf_str.h: 65

File = struct_File # /mnt/hda4/home/c/adflib/src/adf_str.h: 98

Entry = struct_Entry # /mnt/hda4/home/c/adflib/src/adf_str.h: 117

CacheEntry = struct_CacheEntry # /mnt/hda4/home/c/adflib/src/adf_str.h: 130

DateTime = struct_DateTime # /mnt/hda4/home/c/adflib/src/adf_str.h: 143

Env = struct_Env # /mnt/hda4/home/c/adflib/src/adf_str.h: 160

List = struct_List # /mnt/hda4/home/c/adflib/src/adf_str.h: 181

GenBlock = struct_GenBlock # /mnt/hda4/home/c/adflib/src/adf_str.h: 187

FileBlocks = struct_FileBlocks # /mnt/hda4/home/c/adflib/src/adf_str.h: 195

bEntryBlock = struct_bEntryBlock # /mnt/hda4/home/c/adflib/src/adf_str.h: 203

# No inserted files

