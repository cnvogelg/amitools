from amitools.vamos.error import VamosInternalError
from amitools.vamos.libstructs import (
    AChainStruct,
    AnchorPathStruct,
    FileInfoBlockStruct,
)
from amitools.vamos.log import log_dos

from .Error import (
    ERROR_BAD_TEMPLATE,
    ERROR_NO_MORE_ENTRIES,
    ERROR_OBJECT_NOT_FOUND,
    NO_ERROR,
)
from .PathMatch import PathMatch


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
        self.str_len = anchor.ap_Strlen.val
        self.total_size = AnchorPathStruct.get_size() + self.str_len
        self.flags = anchor.ap_Flags.val
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
        self.achain_dummy = ctx.alloc.alloc_astruct(AChainStruct, label="AChain_Dummy")
        self.achain_dummy_struct = self.achain_dummy
        self.anchor.ap_Last.aptr = self.achain_dummy.addr
        self.anchor.ap_Base.aptr = self.achain_dummy.addr
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
        fib_ptr = self.anchor.ap_Info.addr
        fib = FileInfoBlockStruct(ctx.mem, fib_ptr)
        io_err = lock.examine_lock(fib)
        self.lock_mgr.release_lock(lock)
        # store path name of first name at end of structure
        if self.str_len > 0:
            path_ptr = self.anchor.ap_Buf.addr
            self.anchor.mem.w_cstr(path_ptr, path)
        return io_err

    def _fill_lock(self, path):
        lock = self.lock_mgr.create_lock(self.lock, path, False)
        if lock == None:
            return False
        self.dir_lock = lock
        oldlock = self.lock_mgr.get_by_b_addr(self.achain_dummy_struct.lock.bptr)
        self.lock_mgr.release_lock(oldlock)
        self.achain_dummy_struct.lock.aptr = lock.mem.addr
        return True

    def _fill_parent_lock(self, path):
        parent = self.path_mgr.ami_dir_of_path(self.lock, path)
        if not parent:
            parent = ""
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
        flags = self.anchor.ap_Flags.val
        org_flags = flags

        # check DODIR flag and add first level of dir entries
        if flags & self.DODIR == self.DODIR:
            # Note that FindNext *CLEARS* DODIR after testing!
            self.anchor.ap_Flags.val = flags & ~self.DODIR
            self._push_dodir(self.name, self.path)

        # are there dirs to do?
        name, path, flags = self._get_dodir(flags)
        if flags != org_flags:
            self.anchor.ap_Flags.val = flags

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
            oldlock = self.lock_mgr.get_by_b_addr(self.achain_dummy_struct.lock.bptr)
            self.lock_mgr.release_lock(oldlock)
            self.achain_dummy.free()


# ----- fd functions -----


def match_first(dos, ctx, pat_ptr, anchor_ptr):
    pat = ctx.mem.r_cstr(pat_ptr)
    anchor = AnchorPathStruct(ctx.mem, anchor_ptr)

    # create MatchFirstNext instance
    mfn = MatchFirstNext(
        dos.path_mgr, dos.lock_mgr, dos.get_current_dir(ctx), pat, anchor
    )
    log_dos.info(
        "MatchFirst: pat='%s' anchor=%06x strlen=%d flags=%02x-> ok=%s",
        pat,
        anchor_ptr,
        mfn.str_len,
        mfn.flags,
        mfn.ok,
    )
    if not mfn.ok:
        dos.matches[anchor_ptr] = mfn
        dos.setioerr(ctx, ERROR_BAD_TEMPLATE)
        return dos.io_err
    log_dos.debug("MatchFirst: %s", mfn.matcher)

    # try first match
    err = mfn.first(ctx)
    dos.setioerr(ctx, err)
    if dos.io_err == NO_ERROR:
        log_dos.info(
            "MatchFirst: found name='%s' path='%s' -> parent lock %s, io_err=%d",
            mfn.name,
            mfn.path,
            mfn.dir_lock,
            dos.io_err,
        )
        dos.matches[anchor_ptr] = mfn
    # no entry found or error
    elif dos.io_err == ERROR_OBJECT_NOT_FOUND:
        log_dos.info("MatchFirst: none found")
        dos.matches[anchor_ptr] = mfn
    else:
        # Dos also creates a matcher on failure...
        dos.matches[anchor_ptr] = mfn
        log_dos.info("MatchFirst: error: %d", dos.io_err)
    return dos.io_err


def match_next(dos, ctx, anchor_ptr):
    log_dos.info("MatchNext: anchor=%06x", anchor_ptr)
    # retrieve match
    if anchor_ptr not in dos.matches:
        raise VamosInternalError("MatchNext: No matcher found for %06x" % anchor_ptr)
    mfn = dos.matches[anchor_ptr]
    # has matches?
    if mfn != None:
        dos.setioerr(ctx, mfn.next(ctx))
        if dos.io_err == NO_ERROR:
            log_dos.info(
                "MatchNext: found name='%s' path=%s -> parent lock %s, io_err=%d",
                mfn.name,
                mfn.path,
                mfn.dir_lock,
                dos.io_err,
            )
        elif dos.io_err == ERROR_NO_MORE_ENTRIES:
            log_dos.info("MatchNext: no more entries!")
        else:
            log_dos.info("MatchNext: error: %d", dos.io_err)
        return dos.io_err


def match_end(dos, ctx, anchor_ptr):
    log_dos.info("MatchEnd: anchor=%06x ", anchor_ptr)
    # retrieve match
    if anchor_ptr not in dos.matches:
        raise VamosInternalError("MatchEnd: No matcher found for %06x" % anchor_ptr)
    mfn = dos.matches[anchor_ptr]
    del dos.matches[anchor_ptr]
    if mfn != None:
        mfn.end(ctx)


class MatchFirstNextMixin:
    """dos.library fd methods (HANDLER.md step 22m)."""

    def MatchFirst(self, ctx, pat_ptr, anchor_ptr):
        return match_first(self, ctx, pat_ptr, anchor_ptr)

    def MatchNext(self, ctx, anchor_ptr):
        return match_next(self, ctx, anchor_ptr)

    def MatchEnd(self, ctx, anchor_ptr):
        return match_end(self, ctx, anchor_ptr)
