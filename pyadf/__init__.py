#!/bin/env python
# -*- coding: ascii -*-
# vim:ts=4:sw=4:softtabstop=4:smarttab:expandtab
#

import os
import ctypes

import adflib

class AdfBaseException(Exception):
    '''Base ADF I/O exception'''

class AdfIOException(AdfBaseException):
    '''I/O exception'''

class AdfVersionInfo(object):
    """There are 2 kinds of version information available:
        * what verson of ADFLib was adflib.py created with?
        * what verson of adflib.dll or adf.so (etc.) are we running with?
    """
    def __init__(self):
        # what was adflib.py "created" with?
        self.headers_version = adflib.ADFLIB_VERSION
        self.headers_date = adflib.ADFLIB_DATE
        
        # what version of adflib are we running with?
        self.lib_version = adflib.adfGetVersionNumber()
        self.lib_date = adflib.adfGetVersionDate()
    
    def __repr__(self):
        return repr(self.__dict__)


class _InternalAdfEnv(object):
    """whislt this is NOT a singleton, only create one.
    I.e. singleton is not yet enforced
    
    Still naive but doesn't allocate environment unless adf file is opened
    clean up happens at (modue) desconstruction time when single_internaladfenv is destroyed.
    Should allow multiple adf's to be opened
    """
    def __init__(self):
        self.adflib_init = False
        self.counter = 0
    
    def acquire(self):
        # simulate a Semaphore, only one in python lib is in threading module
        self.counter += 1
        if not self.adflib_init:
            adflib.adfEnvInitDefault()
            self.adflib_init = True
    
    def release(self):
        # do nothing for now, let deconstructor handle this
        # may not work with Jython.
        self.counter -= 1
        pass
    
    def __del__(self):
        if not self.adflib_init:
            adflib.adfEnvCleanUp()
            self.adflib_init = False

_single_internaladfenv = _InternalAdfEnv()

def adf_setup():
    _single_internaladfenv.acquire()

def adf_cleanup():
    _single_internaladfenv.release()


class AdfFileInfo(object):
    """Right now this is basically an expensive named tuple
    """
    def __init__(self, ftype, fsize, fdate, fpath, fname, fcomment=None, fsector=None):
        """fdate is a tuple (year, month, days, hour, mins, secs)
        """
        self.ftype = ftype
        self.fsize = fsize
        self.fdate = fdate
        self.fpath = fpath
        self.fsector = fsector
        self.fname = fname
        self.fcomment = fcomment
    
    def __repr__(self):
        return repr(self.__dict__)
    
    def pretty_str(self):
        """return pretty output for the file entry"""
        date_str = "%4d/%02d/%02d  %2d:%02d:%02d" % self.fdate
        if self.fpath:
            name_str = "%s/"%(self.fpath,)
        else:
            name_str = ""
        if self.ftype == adflib.ST_DIR:
            name_str += "%s/"%(self.fname,)
            size_str = ' ' * 7
        else:
            name_str += "%s"%(self.fname,)
            size_str = "%7d" %(self.fsize,)
        
        return date_str + ' ' + size_str + ' ' + name_str 
    

def process_entry(vol_ptr, entry_ptr, file_path):
    """Simple print file information (uses print) output goes to stdout
    """
    vol = vol_ptr[0]
    entry = entry_ptr[0]
    # do not print the links entries, ADFlib do not support them yet properly
    if entry.type==adflib.ST_LFILE or entry.type==adflib.ST_LDIR or entry.type==adflib.ST_LSOFT:
        return
    
    tmp_comment = None
    if entry.comment and len(entry.comment)>0:
        tmp_comment = str(entry.comment)
    
    #print type(entry.type), type(entry.size), type(entry.year), type(entry.month), type(entry.days), type(entry.hour), type(entry.mins), type(entry.secs), type(file_path), type(entry.name), type(tmp_comment), type(entry.sector)
    result = AdfFileInfo(entry.type, entry.size, (entry.year, entry.month, entry.days, entry.hour, entry.mins, entry.secs), file_path, str(entry.name), tmp_comment, entry.sector)
    return result

class Adf(object):
    """A pythonic api wrapper around ADFlib
    """
    def __init__(self, adf_filename, volnum=0, mode='r'):
        self.adf_filename = adf_filename
        self.env = None
        self.vol = None
        self.dev = None
        self.volnum = volnum
        self.readonly_mode = True
        if mode == 'w':
            self.readonly_mode = False
        
        self._curdir = '/'
        
        if not os.path.exists(adf_filename):
            raise AdfIOException('%s filename does not exist' % adf_filename)
        
        self.open()  # kinda nasty doing work in the constructor....
    
    def normpath(self, filepath):
        filepath = filepath.replace('\\', '/')  # Allow Windows style paths (just in case they slip in)
        filepath = filepath.replace(':', '/')  # Allow Amiga style paths (just in case they slip in)
        return filepath
    
    def splitpath(self, filepath):
        filepath = self.normpath(filepath)
        result = []
        for tmpdir in filepath.split('/'):
            if tmpdir:
                result.append(tmpdir)
        return result
    
    def chdir(self, dirname, ignore_error=False):
        vol = self.vol
        return self._chdir(dirname, ignore_error=ignore_error)
        
    def _chdir(self, dirname, update_curdir=True, ignore_error=False):
        vol = self.vol
        dirname = self.normpath(dirname)
        if dirname.startswith('/'):
            adflib.adfToRootDir(vol)
            if update_curdir:
                self._curdir = '/'
        if dirname == '/':
            return True
        else:
            for tmpdir in dirname.split('/'):
                if tmpdir:
                    result = adflib.adfChangeDir(vol, tmpdir)
                    if result == -1:
                        # FAIL
                        if ignore_error:
                            return False
                        else:
                            raise AdfIOException('error changing directory to %s in %s' % (tmpdir, dirname))
                    else:
                        if update_curdir:
                            self._curdir += dirname+'/'
        return True
    
    def ls_dir(self, dirname=None):
        vol = self.vol
        if dirname:
            self._chdir(dirname, update_curdir=False)
        else:
            self._chdir(self._curdir)
        result = []
        Entry_Ptr = adflib.POINTER(adflib.Entry)
        list = adflib.adfGetDirEnt(vol, vol[0].curDirPtr)
        cell = list 
        while cell:
            tmp_content = cell[0].content
            tmp_content = adflib.cast(tmp_content, Entry_Ptr)
            fentry = process_entry(vol, tmp_content, "")
            if fentry:
                result.append(fentry)
            cell = cell[0].next
        
        adflib.adfFreeDirList(list)
        if dirname:
            self._chdir(self._curdir)
        return result
    
    def get_file(self, filename):
        """return Python string which is the file contents.
        NOTE/FIXME filename needs to be a file in the current directory at the moment.
        FIXME if a directory name is passed in need to fail!
        """
        vol = self.vol
        filename = self.normpath(filename)
        splitpaths = self.splitpath(filename)
        if len(splitpaths) >1:
            #if filename.startswith('/'):
            # trim leading slash
            #filename = filename[1:]
            filename = splitpaths[-1]
            tmp_dirname = splitpaths[:-1]
            tmp_dirname= '/'.join(tmp_dirname)
            self._chdir(tmp_dirname, update_curdir=False, ignore_error=False)
        file_in_adf = adflib.adfOpenFile(vol, filename, "r");
        if not file_in_adf:
            # file probably not there
            self._chdir(self._curdir)
            raise AdfIOException('unable to filename %s for read' % filename)
            return
        
        #print 'adffile', repr(file_in_adf)
        #print 'type adffile', type(file_in_adf)
        #print 'dir adffile', dir(file_in_adf)
        #print 'adffile[0]', repr(file_in_adf[0])
        #adffile = adffile[0]
        tmp_buffer_size = 1024*8
        mybuff_type = ctypes.c_ubyte * tmp_buffer_size
        mybuff = mybuff_type() ## probably a better way than this
        #mybuff_ptr = ctypes.pointer(mybuff)
        eof_yet = adflib.adfEndOfFile(file_in_adf)
        #print 'eof_yet ', eof_yet 
        #print 'eof_yet ', type(eof_yet )
        tmp_str = []
        while not eof_yet:
            n = adflib.adfReadFile(file_in_adf, tmp_buffer_size, ctypes.byref(mybuff))
            eof_yet = adflib.adfEndOfFile(file_in_adf)
            #print 'eof_yet ', eof_yet 
            #print 'eof_yet ', type(eof_yet )
            #print 'n', n
            #print 'mybuff', mybuff
            #print 'mybuff', dir(mybuff)
            #print 'mybuff', str(mybuff)
            # FIXME performance of this is poor
            for x in mybuff[:n]:
                tmp_str.append(chr(x))
            #print 'tmp_str', tmp_str
            #print 'len tmp_str', len(tmp_str)
        adflib.adfCloseFile(file_in_adf)
        self._chdir(self._curdir)
        return ''.join(tmp_str)

    def push_file(self, filename, file_contents):
        """writes file_contents into filename
        NOTE/FIXME filename needs to be a file in the current directory at the moment.
        FIXME if a directory name is passed in need to fail!
        """
        vol = self.vol
        filename = self.normpath(filename)
        splitpaths = self.splitpath(filename)
        if len(splitpaths) >1:
            filename = splitpaths[-1]
            tmp_dirname = splitpaths[:-1]
            tmp_dirname= '/'.join(tmp_dirname)
            self._chdir(tmp_dirname, update_curdir=False, ignore_error=False)
        file_out_adf = adflib.adfOpenFile(vol, filename, "w");
        if not file_out_adf:
            # error, bad directory or adf file opened in readonly mode?
            self._chdir(self._curdir)
            raise AdfIOException('unable to create filename %s for read' % filename)
            return
        
        tmp_buffer_size = 1024*8
        mybuff_type = ctypes.c_ubyte * tmp_buffer_size
        mybuff = mybuff_type() ## probably a better way than this
        file_contents_len = len(file_contents)
        file_contents_left = file_contents_len
        eof_yet = file_contents_left <= 0
        counter = 0
        while not eof_yet:
            tmp_counter = min(tmp_buffer_size, file_contents_left)
            mybuff_counter = 0
            for x in range(counter, counter + tmp_counter):
                mybuff[mybuff_counter] = ord(file_contents[x])
                mybuff_counter += 1  # maybe use enumerate instead?
            counter += tmp_counter
            file_contents_left -= tmp_counter
            eof_yet = file_contents_left <= 0
            
            # long adfWriteFile(struct File* file, long n, unsigned char* buffer) 
            n = adflib.adfWriteFile(file_out_adf, tmp_counter, ctypes.byref(mybuff))
            #print 'write', n
        
        adflib.adfCloseFile(file_out_adf)


    
    def unlink(self, filename):
        """delete a file"""
        ## TODO not opened in write mode check?
        vol = self.vol
        result = adflib.adfRemoveEntry(vol, vol[0].curDirPtr, filename)
        if result == -1:
            # FAIL
            raise AdfIOException('unlink/delete failed on %s' % (filename))
        # else flush? incase of errors later on
    
    def rename(self, old, new):
        """rename a file or directory"""
        ## TODO not opened in write mode check?
        vol = self.vol
        result = adflib.adfRenameEntry(vol, vol[0].curDirPtr, old, vol[0].curDirPtr, new)
        if result == -1:
            # FAIL
            raise AdfIOException('rename %s to %s' % (old, new))
        # else flush? incase of errors later on

    def diskname(self):
        """return the volumn name
        Could be a property rather than a function"""
        raise NotImplementedError('Adf')
    
    def open(self):
        readonly_mode = self.readonly_mode
        ## not sure about name
        if self.env is None:
            self.env = True
            _single_internaladfenv.acquire()
        if not self.dev:
            self.dev = adflib.adfMountDev(self.adf_filename, readonly_mode)
        if not self.vol:
            self.vol = adflib.adfMount(self.dev, self.volnum, readonly_mode)

    def close(self):
        ## not sure about name
        if self.vol:
            adflib.adfUnMount(self.vol)
            self.vol = None
        if self.dev:
            adflib.adfUnMountDev(self.dev)
            self.dev = None
        if self.env is not None:
            _single_internaladfenv.release()
            self.env = None
    
    def __del__(self):
        self.close()

def create_empty_adf(adf_filename, diskname='empty', cyl=80, heads=2, sectors=11):
    """Consider implementing as a Adf classmethod?
        DD floppy; cyl=80, heads=2, sectors=11
        HD floppies have 22 sectors 
    """
    #raise NotImplementedError('not completed yet, adflib appeared to be missing adfCreateDumpDevice')
    if os.path.exists(adf_filename):
        raise AdfIOException('%r should not exist!' % adf_filename)
    adf_setup()
    flop = adflib.adfCreateDumpDevice(adf_filename, cyl, heads, sectors)
    if flop is None:
        print 'adfCreateFlop error', rc
        raise AdfIOException('%s adfCreateDumpDevice failed' % adf_filename)
        
    # create the filesystem : OFS with DIRCACHE
    # RETCODE adfCreateFlop(struct Device* dev, char* volName, int volType ) 
    rc = adflib.adfCreateFlop(flop, diskname, adflib.FSMASK_DIRCACHE)
    if rc != adflib.RC_OK:
        print 'adfCreateFlop error', rc
        raise AdfIOException('%s adfCreateFlop failed, %s' % (adf_filename, diskname))
    adflib.adfUnMountDev(flop)
    adf_cleanup()

