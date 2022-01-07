from amitools.vamos.astructs import AccessStruct
from amitools.vamos.libstructs import (
    AnchorPathStruct,
    AChainStruct,
    FileInfoBlockStruct,
)
from .PathMatch import PathMatch
from amitools.vamos.label import LabelStruct
from .Error import *


class MatchFirstNext:

    DODIR = 4
    DIDDIR = 8

    def __init__(self, path_mgr, lock_mgr, lock, pattern, anchor):
        self.path_mgr = path_mgr
        self.lock_mgr = lock_mgr
        self.pattern = pattern
        self.lock = lock
        self.anchor = anchor
        # get total size of struct
        self.str_len = anchor.r_s("ap_Strlen")
        self.total_size = AnchorPathStruct.get_size() + self.str_len
        self.flags = anchor.r_s("ap_Flags")
        # setup matcher
        self.matcher = PathMatch(self.path_mgr, self.lock)
        self.ok = self.matcher.parse(self.pattern)
        # init state
        self.old_label = None
        self.new_label = None
        self.achain_dummy = None
        self.name = None
        self.path = None
        self.dir_lock = None

    def first(self, ctx):
        # match first entry
        self.path = self.matcher.begin()
        if self.path == None:
            return ERROR_OBJECT_NOT_FOUND
        self.name = self.path_mgr.ami_name_of_path(self.lock, self.path)
        # get parent dir of first match
        dir_part = self.path_mgr.ami_dir_of_path(self.lock, self.path)
        abs_path = self.path_mgr.ami_abs_path(self.lock, dir_part)

        # create base/last achain and set dir lock
        # THOR: this is still screwed up. Some utililties
        # most notably "dir" depend on a correctly setup
        # anchor chain...
        self.achain_dummy = ctx.alloc.alloc_struct(AChainStruct, label="AChain_Dummy")
        self.anchor.w_s("ap_Last", self.achain_dummy.addr)
        self.anchor.w_s("ap_Base", self.achain_dummy.addr)
        if not self._fill_lock(abs_path):
            return ERROR_OBJECT_NOT_FOUND

        # fill first entry
        io_err = self._fill_fib(ctx, self.path)
        self._fill_parent_lock(self.path)

        # init stack
        self.dodir_stack = []
        return io_err

    def _fill_fib(self, ctx, path):
        # fill FileInfo of first match in anchor
        lock = self.lock_mgr.create_lock(self.lock, path, False)
        if lock == None:
            return ERROR_OBJECT_NOT_FOUND
        fib_ptr = self.anchor.s_get_addr("ap_Info")
        fib = AccessStruct(ctx.mem, FileInfoBlockStruct, struct_addr=fib_ptr)
        io_err = lock.examine_lock(fib)
        self.lock_mgr.release_lock(lock)
        # store path name of first name at end of structure
        if self.str_len > 0:
            path_ptr = self.anchor.s_get_addr("ap_Buf")
            self.anchor.mem.w_cstr(path_ptr, path)
        return io_err

    def _fill_lock(self, path):
        lock = self.lock_mgr.create_lock(self.lock, path, False)
        if lock == None:
            return False
        self.dir_lock = lock
        oldlock = self.lock_mgr.get_by_b_addr(
            self.achain_dummy.access.r_s("an_Lock") >> 2
        )
        self.lock_mgr.release_lock(oldlock)
        self.achain_dummy.access.w_s("an_Lock", lock.mem.addr)
        return True

    def _fill_parent_lock(self, path):
        parent = self.path_mgr.ami_abs_parent_path(path)
        return self._fill_lock(parent)

    def _push_dodir(self, name, path):
        abs_path = self.path_mgr.ami_abs_path(self.lock, path)
        dir_entries = sorted(self.path_mgr.ami_list_dir(self.lock, path))
        # its really a dir
        if dir_entries != None:
            self.dodir_stack.append((name, path, dir_entries))
            self._fill_lock(path)

    def _get_dodir(self, flags):
        if len(self.dodir_stack) > 0:
            name, path, dir_entries = self.dodir_stack[-1]
            # entry left in current dodir?
            if len(dir_entries) > 0:
                sub_name = dir_entries.pop(0)
                if path == "":
                    sub_path = sub_name
                elif path[-1] in (":", "/"):
                    sub_path = path + sub_name
                else:
                    sub_path = path + "/" + sub_name
                self._fill_lock(path)
                return sub_name, sub_path, flags
            else:
                # top stack is finished
                flags |= self.DIDDIR
                flags &= ~self.DODIR
                self.dodir_stack.pop()
                self._fill_parent_lock(path)
                return name, path, flags
        else:
            flags &= ~self.DODIR
            self._fill_lock("")
            return None, None, flags

    def next(self, ctx):
        flags = self.anchor.r_s("ap_Flags")
        org_flags = flags

        # check DODIR flag and add first level of dir entries
        if flags & self.DODIR == self.DODIR:
            # Note that FindNext *CLEARS* DODIR after testing!
            self.anchor.w_s("ap_Flags", flags & ~self.DODIR)
            self._push_dodir(self.name, self.path)

        # are there dirs to do?
        name, path, flags = self._get_dodir(flags)
        if flags != org_flags:
            self.anchor.w_s("ap_Flags", flags)

        # no dodir -> use matcher
        if path == None:
            path = next(self.matcher)
            # no more matches
            if path == None:
                return ERROR_NO_MORE_ENTRIES
            # extract name
            name = self.path_mgr.ami_name_of_path(self.lock, path)

        # update current
        self.path = path
        self.name = name
        self._fill_parent_lock(path)

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
        if self.achain_dummy != None:
            oldlock = self.lock_mgr.get_by_b_addr(
                self.achain_dummy.access.r_s("an_Lock") >> 2
            )
            self.lock_mgr.release_lock(oldlock)
            ctx.alloc.free_struct(self.achain_dummy)
