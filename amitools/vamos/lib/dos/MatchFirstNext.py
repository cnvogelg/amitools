from DosStruct import *
from PathMatch import PathMatch
from amitools.vamos.LabelStruct import LabelStruct
from amitools.vamos.AccessStruct import AccessStruct

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
    self.flags = anchor.r_s('ap_Flags')
    self.total_size = AnchorPathDef.get_size() + self.str_len
    # setup matcher
    self.matcher = PathMatch(self.path_mgr)
    self.ok = self.matcher.parse(self.pattern)
    # get first entry
    if self.ok:
      self.path = self.matcher.begin()
    else:
      self.path = None
  
  def first(self, ctx):
    # replace label of struct
    self.old_label = ctx.label_mgr.get_label(self.anchor.struct_addr)
    if self.old_label != None:
      ctx.label_mgr.remove_label(self.old_label)
    self.new_label = LabelStruct("MatchAnchor", self.anchor.struct_addr, AnchorPathDef, size=self.total_size)
    ctx.label_mgr.add_label(self.new_label)
    
    # get parent dir of first match
    self.abs_path = self.path_mgr.ami_abs_path(self.path)
    self.voldir_path = self.path_mgr.ami_voldir_of_path(self.abs_path)
    self.dir_lock = self.lock_mgr.create_lock(self.voldir_path, False)
    
    # create last achain and set dir lock
    self.achain_last = ctx.alloc.alloc_struct("AChain_Last", AChainDef)
    self.anchor.w_s('ap_Last', self.achain_last.addr)
    self.achain_last.access.w_s('an_Lock', self.dir_lock.addr)
    
    self._fill_fib(ctx)
    
    # init stack
    self.dodir_stack = []
  
  def _fill_fib(self, ctx):
    # fill FileInfo of first match in anchor
    lock = self.lock_mgr.create_lock(self.abs_path, False)
    fib_ptr = self.anchor.s_get_addr('ap_Info')
    fib = AccessStruct(ctx.mem,FileInfoBlockDef,struct_addr=fib_ptr)
    self.lock_mgr.examine_lock(lock, fib)
    self.lock_mgr.release_lock(lock)
    # store path name of first name at end of structure
    if self.str_len > 0:
      path_ptr = self.anchor.s_get_addr('ap_Buf')
      self.anchor.w_cstr(path_ptr, self.abs_path)
  
  def _push_dodir(self):
    dir_entries = self.path_mgr.ami_list_dir(self.abs_path)
    # its really a dir
    if dir_entries != None:
      dodir = []
      for d in dir_entries:
        dodir.append(self.abs_path + "/" + d)
      self.dodir_stack.append((self.abs_path, dodir))

  def _get_dodir(self, flags):
    if len(self.dodir_stack) > 0:
      abs_path, dodir = self.dodir_stack[-1]
      # entry left in current dodir?
      if len(dodir) > 0:
        path = dodir.pop()
        return path, flags
      else:  
        # top stack is finished
        flags |= self.DIDDIR
        flags &= ~self.DODIR
        self.dodir_stack.pop()
        return abs_path, flags
    else:
      return None, flags

  def next(self, ctx):
    flags = self.anchor.r_s('ap_Flags')
    org_flags = flags
    
    # check DODIR flag and add first level of dir entries
    if flags & self.DODIR == self.DODIR:
      self._push_dodir()
    
    # are there dirs to do?
    path,flags = self._get_dodir(flags)
    if flags != org_flags:
      self.anchor.w_s('ap_Flags',flags)
    
    # no dodir -> use matcher
    if path == None:
      path = self.matcher.next()

    # store path
    self.path = path
    if path == None:
      return False
    else:
      # get parent dir of this match
      self.abs_path = self.path_mgr.ami_abs_path(path)
      voldir_path = self.path_mgr.ami_voldir_of_path(self.abs_path)
      # need new parent dir lock in achain_last?
      if voldir_path != self.voldir_path:
        self.lock_mgr.release_lock(self.dir_lock)
        self.dir_lock = self.lock_mgr.create_lock(voldir_path, False)
        self.voldir_path = voldir_path
        # update achain_last
        self.achain_last.access.w_s('an_Lock', self.dir_lock.addr)
      # fill fib
      self._fill_fib(ctx)
      return True

  def end(self, ctx):
    # restore label
    ctx.label_mgr.remove_label(self.new_label)
    if self.old_label != None:
      ctx.label_mgr.add_label(self.old_label)
    # free last dir lock & achain
    lock_addr = self.achain_last.access.r_s('an_Lock')
    lock = self.lock_mgr.get_by_b_addr(lock_addr >> 2)
    self.lock_mgr.release_lock(lock)
    ctx.alloc.free_struct(self.achain_last)

