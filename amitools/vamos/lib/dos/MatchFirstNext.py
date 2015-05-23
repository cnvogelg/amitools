from DosStruct import *
from PathMatch import PathMatch
from amitools.vamos.LabelStruct import LabelStruct
from amitools.vamos.AccessStruct import AccessStruct
from Error import *

class MatchFirstNext:
  
  DODIR = 4
  DIDDIR = 8
  
  def __init__(self, path_mgr, lock_mgr, pattern, anchor):
    self.path_mgr = path_mgr
    self.lock_mgr = lock_mgr
    self.pattern = pattern
    self.anchor = anchor
    # get total size of struct
    self.str_len = anchor.r_s('ap_Strlen')
    self.total_size = AnchorPathDef.get_size() + self.str_len
    self.flags = anchor.r_s('ap_Flags')
    # setup matcher
    self.matcher = PathMatch(self.path_mgr)
    self.ok = self.matcher.parse(self.pattern)
    # init state
    self.old_label = None
    self.new_label = None
    self.achain_dummy = None
    self.dir_lock = None
    self.name = None
    self.path = None
  
  def first(self, ctx):
    # match first entry
    self.path = self.matcher.begin()
    if self.path == None:
      return ERROR_OBJECT_NOT_FOUND
    self.name = self.path_mgr.ami_name_of_path(self.path)

    # get parent dir of first match
    dir_part = self.path_mgr.ami_dir_of_path(self.path)
    abs_path = self.path_mgr.ami_abs_path(dir_part)
    self.dir_lock = self.lock_mgr.create_lock(abs_path, False)
    if self.dir_lock == None:
      return ERROR_OBJECT_NOT_FOUND
    
    # create base/last achain and set dir lock
    self.achain_dummy = ctx.alloc.alloc_struct("AChain_Dummy", AChainDef)
    self.anchor.w_s('ap_Last', self.achain_dummy.addr)
    self.anchor.w_s('ap_Base', self.achain_dummy.addr)
    self.achain_dummy.access.w_s('an_Lock', self.dir_lock.addr)
    
    # fill first entry
    io_err = self._fill_fib(ctx, self.path)
    
    # init stack
    self.dodir_stack = []
    return io_err
  
  def _fill_fib(self, ctx, path):
    # fill FileInfo of first match in anchor
    lock = self.lock_mgr.create_lock(path, False)
    fib_ptr = self.anchor.s_get_addr('ap_Info')
    fib = AccessStruct(ctx.mem,FileInfoBlockDef,struct_addr=fib_ptr)
    io_err = self.lock_mgr.examine_lock(lock, fib)
    self.lock_mgr.release_lock(lock)
    # store path name of first name at end of structure
    if self.str_len > 0:
      path_ptr = self.anchor.s_get_addr('ap_Buf')
      self.anchor.w_cstr(path_ptr, path)
    return io_err
  
  def _push_dodir(self, name, path):
    abs_path = self.path_mgr.ami_abs_path(path)
    dir_entries = self.path_mgr.ami_list_dir(path)
    # its really a dir
    if dir_entries != None:
      self.dodir_stack.append((name, path, dir_entries))

  def _get_dodir(self, flags):
    if len(self.dodir_stack) > 0:
      name, path, dir_entries = self.dodir_stack[-1]
      # entry left in current dodir?
      if len(dir_entries) > 0:
        sub_name = dir_entries.pop()
        if path == "":
          sub_path = sub_name
        elif path[-1] in (':','/'):
          sub_path = path + sub_name
        else:
          sub_path = path + "/" + sub_name        
        return sub_name, sub_path, flags
      else:  
        # top stack is finished
        flags |= self.DIDDIR
        flags &= ~self.DODIR
        self.dodir_stack.pop()
        return name, path, flags
    else:
      flags &= ~self.DODIR
      return None, None, flags

  def next(self, ctx):
    flags = self.anchor.r_s('ap_Flags')
    org_flags = flags
    
    # check DODIR flag and add first level of dir entries
    if flags & self.DODIR == self.DODIR:
      self._push_dodir(self.name, self.path)
    
    # are there dirs to do?
    name, path, flags = self._get_dodir(flags)
    if flags != org_flags:
      self.anchor.w_s('ap_Flags',flags)
    
    # no dodir -> use matcher
    if path == None:
      path = self.matcher.next()
      # no more matches
      if path == None:
        return ERROR_NO_MORE_ENTRIES
      # extract name
      name = self.path_mgr.ami_name_of_path(path)
    
    # update current
    self.path = path
    self.name = name
    
    # fill fib
    io_err = self._fill_fib(ctx, path)
    return io_err

  def end(self, ctx):
    # restore label
    if self.new_label != None:
      ctx.label_mgr.remove_label(self.new_label)
    if self.old_label != None:
      ctx.label_mgr.add_label(self.old_label)
    # free last dir lock & achain
    if self.dir_lock != None:
      self.lock_mgr.release_lock(self.dir_lock)
    if self.achain_dummy != None:
      ctx.alloc.free_struct(self.achain_dummy)

