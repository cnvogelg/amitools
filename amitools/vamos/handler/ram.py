"""RAM: handler: an in-memory AmigaDOS file system.

The handler keeps a tree of :class:`RamNode` objects in memory, so ``RAM:``
is self-contained: there is no host temp directory to create or clean up.
It mirrors :class:`~amitools.vamos.handler.filesys.HostFileSysHandler` but
stores file contents in shared ``bytearray`` buffers instead of on disk.

All paths it receives are volume-relative and use AmigaDOS ``/`` separators.
Resolution is case-insensitive and collapses AmigaDOS parent steps.
"""

from amitools.vamos.path.amipath import collapse_parent_steps

from .base import (
    ERROR_BAD_NUMBER,
    ERROR_DIRECTORY_NOT_EMPTY,
    ERROR_NO_MORE_ENTRIES,
    ERROR_OBJECT_EXISTS,
    ERROR_OBJECT_IN_USE,
    ERROR_OBJECT_NOT_FOUND,
    ERROR_OBJECT_WRONG_TYPE,
    ERROR_SEEK_ERROR,
    MODE_NEWFILE,
    MODE_OLDFILE,
    MODE_READWRITE,
    Handler,
    HandlerError,
    HandlerFile,
    HandlerFileInfo,
    HandlerInfoData,
    HandlerLock,
)

# default nominal capacity of a RAM: volume in KiB
DEFAULT_SIZE_KB = 1024


class RamNode:
    """one file or directory in the in-memory file system"""

    def __init__(self, name, is_dir):
        self.name = name
        self.is_dir = is_dir
        # a shared bytearray for files so all open handles see each other
        self.data = None if is_dir else bytearray()
        # lower-case name -> RamNode; only used for directories
        self.children = {} if is_dir else None
        self.protection = 0
        self.comment = ""
        self.date = 0


class RamStream:
    """a file-like object over a node's shared ``bytearray``"""

    def __init__(self, node):
        self.node = node
        self.pos = 0

    def read(self, size=-1):
        data = self.node.data
        if size is None or size < 0:
            chunk = bytes(data[self.pos :])
        else:
            chunk = bytes(data[self.pos : self.pos + size])
        self.pos += len(chunk)
        return chunk

    def read1(self, size=-1):
        return self.read(size)

    def write(self, data):
        buf = self.node.data
        if self.pos > len(buf):
            buf.extend(b"\x00" * (self.pos - len(buf)))
        end = self.pos + len(data)
        buf[self.pos : end] = data
        self.pos = end
        return len(data)

    def seek(self, offset, whence=0):
        if whence == 0:
            new_pos = offset
        elif whence == 1:
            new_pos = self.pos + offset
        elif whence == 2:
            new_pos = len(self.node.data) + offset
        else:
            raise ValueError(f"invalid whence: {whence!r}")
        if new_pos < 0:
            raise OSError("negative seek position")
        self.pos = new_pos
        return new_pos

    def tell(self):
        return self.pos

    def truncate(self, size=None):
        if size is None:
            size = self.pos
        buf = self.node.data
        if size < len(buf):
            del buf[size:]
        else:
            buf.extend(b"\x00" * (size - len(buf)))
        return size

    def get_size(self):
        return len(self.node.data)

    def flush(self):
        pass

    def close(self):
        pass

    def isatty(self):
        return False

    def fileno(self):
        raise OSError("RAM: has no file descriptor")


class RamLock(HandlerLock):
    """lock on an object in the in-memory file system"""

    def __init__(self, rel_path, node):
        super().__init__(key=rel_path.lower())
        self.rel_path = rel_path
        self.node = node
        self._entries = None

    def get_entries(self):
        return self._entries

    def set_entries(self, entries):
        self._entries = entries

    def reset_entries(self):
        self._entries = None


class RamFile(HandlerFile):
    """open file in the in-memory file system"""

    def __init__(self, stream, rel_path):
        super().__init__(key=rel_path.lower())
        self.fobj = stream
        self.rel_path = rel_path
        self.node = stream.node


class RamHandler(Handler):
    """file system handler backed by an in-memory tree"""

    def __init__(self, name, cfg=None):
        super().__init__(name)
        if cfg is None:
            cfg = {}
        self.root = RamNode(name, is_dir=True)
        try:
            size_kb = int(cfg.get("size", DEFAULT_SIZE_KB))
        except (TypeError, ValueError):
            size_kb = DEFAULT_SIZE_KB
        # 512 byte blocks
        self.num_blocks = max(size_kb, 1) * 2

    # ----- helpers -----

    def _make_lock(self, rel_path, node):
        lock = RamLock(rel_path, node)
        lock.handler = self
        return lock

    def _make_file(self, stream, rel_path):
        fh = RamFile(stream, rel_path)
        fh.handler = self
        return fh

    def _find(self, rel_path):
        """resolve a path to ``(node, canonical_rel_path)`` or None"""
        rel = str(rel_path)
        if rel in ("", ":"):
            return self.root, ""
        dirs = collapse_parent_steps(rel.split("/"))
        if dirs is None:
            return None
        node = self.root
        canonical = []
        for name in dirs:
            if node.children is None:
                return None
            child = node.children.get(name.lower())
            if child is None:
                return None
            node = child
            canonical.append(node.name)
        return node, "/".join(canonical)

    def _find_parent(self, rel_path):
        """resolve the parent of a path to ``(parent, canonical, name)``

        Raises ``ERROR_OBJECT_NOT_FOUND`` if the path has no parent or a
        parent component does not exist.
        """
        rel = str(rel_path)
        dirs = collapse_parent_steps(rel.split("/")) if rel not in ("", ":") else None
        if not dirs:
            raise HandlerError(ERROR_OBJECT_NOT_FOUND)
        parent = self.root
        canonical = []
        for name in dirs[:-1]:
            if parent.children is None:
                raise HandlerError(ERROR_OBJECT_NOT_FOUND)
            child = parent.children.get(name.lower())
            if child is None:
                raise HandlerError(ERROR_OBJECT_NOT_FOUND)
            parent = child
            canonical.append(child.name)
        return parent, "/".join(canonical), dirs[-1]

    def _child_info(self, node, key):
        if node.is_dir:
            size = 0
            blocks = 1
            entry_type = HandlerFileInfo.DIR
        else:
            size = len(node.data)
            blocks = (size + 511) // 512
            entry_type = HandlerFileInfo.FILE
        return HandlerFileInfo(
            name=node.name,
            entry_type=entry_type,
            protection=node.protection,
            size=size,
            blocks=blocks,
            date=node.date,
            key=key,
            comment=node.comment,
        )

    def _count_blocks(self, node):
        if not node.is_dir:
            return (len(node.data) + 511) // 512
        total = 1
        for child in node.children.values():
            total += self._count_blocks(child)
        return total

    def _info_data(self):
        return HandlerInfoData(
            num_blocks=self.num_blocks,
            num_blocks_used=self._count_blocks(self.root),
            bytes_per_block=512,
            disk_state=HandlerInfoData.DISK_STATE_VALIDATED,
        )

    # ----- locks -----

    def locate_object(self, ami_path, exclusive=False):
        found = self._find(ami_path)
        if found is None:
            raise HandlerError(ERROR_OBJECT_NOT_FOUND)
        node, rel = found
        return self._make_lock(rel, node)

    def free_lock(self, lock):
        pass

    def copy_dir(self, lock):
        # ACTION_COPY_DIR replicates any lock (it is LOCATE_OBJECT with an
        # empty name), so it must not require a directory here
        return self._make_lock(lock.rel_path, lock.node)

    def parent(self, lock):
        rel = lock.rel_path
        if not rel:
            raise HandlerError(ERROR_OBJECT_NOT_FOUND)
        parent_rel = rel.rsplit("/", 1)[0] if "/" in rel else ""
        found = self._find(parent_rel)
        if found is None:
            raise HandlerError(ERROR_OBJECT_NOT_FOUND)
        node, canonical = found
        return self._make_lock(canonical, node)

    def same_lock(self, a, b):
        return a.handler is b.handler and a.key == b.key

    def examine_object(self, lock):
        return self._child_info(lock.node, 0)

    def examine_next(self, lock, key):
        if not lock.node.is_dir:
            raise HandlerError(ERROR_OBJECT_WRONG_TYPE)
        entries = lock.get_entries()
        if entries is None:
            entries = list(lock.node.children.values())
            lock.set_entries(entries)
        if key < len(entries):
            return self._child_info(entries[key], key + 1)
        lock.reset_entries()
        raise HandlerError(ERROR_NO_MORE_ENTRIES)

    def info(self, lock):
        return self._info_data()

    def disk_info(self, lock):
        return self._info_data()

    def fh_from_lock(self, lock, mode=MODE_OLDFILE):
        if lock.node.is_dir:
            raise HandlerError(ERROR_OBJECT_WRONG_TYPE)
        return self._make_file(RamStream(lock.node), lock.rel_path)

    def parent_fh(self, fh):
        return self.parent(fh)

    def copy_dir_fh(self, fh):
        # ACTION_COPY_DIR_FH locks the file opened by the handle
        return self._make_lock(fh.rel_path, fh.node)

    # ----- files -----

    def find_input(self, ami_path):
        found = self._find(ami_path)
        if found is None:
            raise HandlerError(ERROR_OBJECT_NOT_FOUND)
        node, rel = found
        if node.is_dir:
            raise HandlerError(ERROR_OBJECT_NOT_FOUND)
        return self._make_file(RamStream(node), rel)

    def _open_node(self, ami_path, create):
        found = self._find(ami_path)
        if found is not None:
            node, rel = found
            if node.is_dir:
                raise HandlerError(ERROR_OBJECT_NOT_FOUND)
            return node, rel
        if not create:
            raise HandlerError(ERROR_OBJECT_NOT_FOUND)
        parent, parent_rel, name = self._find_parent(ami_path)
        node = RamNode(name, is_dir=False)
        parent.children[name.lower()] = node
        rel = parent_rel + "/" + name if parent_rel else name
        return node, rel

    def find_output(self, ami_path, mode=MODE_NEWFILE):
        if mode == MODE_OLDFILE:
            node, rel = self._open_node(ami_path, create=False)
        else:
            node, rel = self._open_node(ami_path, create=True)
        if mode == MODE_NEWFILE:
            # truncate in place so existing handles share the new content
            del node.data[:]
        return self._make_file(RamStream(node), rel)

    def find_update(self, ami_path):
        return self.find_output(ami_path, MODE_READWRITE)

    def read(self, fh, size):
        return fh.fobj.read(size)

    def write(self, fh, data):
        return fh.fobj.write(data)

    def seek(self, fh, offset, whence):
        try:
            new_pos = fh.fobj.seek(offset, whence)
        except (OSError, ValueError):
            raise HandlerError(ERROR_SEEK_ERROR)
        file_size = fh.fobj.get_size()
        if new_pos > file_size:
            fh.fobj.seek(file_size, 0)
            return -2
        return new_pos

    def set_file_size(self, fh, size, mode):
        fobj = fh.fobj
        if mode == -1:  # OFFSET_BEGINNING
            new_size = size
        elif mode == 0:  # OFFSET_CURRENT
            new_size = fobj.tell() + size
        elif mode == 1:  # OFFSET_END
            new_size = fobj.get_size() + size
        else:
            raise HandlerError(ERROR_BAD_NUMBER)
        if new_size < 0:
            raise HandlerError(ERROR_OBJECT_WRONG_TYPE)
        fobj.truncate(new_size)
        return new_size

    def flush(self, fh):
        fh.fobj.flush()

    # ``end`` is inherited from the base handler (RamStream.close is a no-op)

    # ----- names -----

    def delete_object(self, ami_path):
        parent, _parent_rel, name = self._find_parent(ami_path)
        node = parent.children.get(name.lower())
        if node is None:
            raise HandlerError(ERROR_OBJECT_NOT_FOUND)
        if node.is_dir and node.children:
            raise HandlerError(ERROR_DIRECTORY_NOT_EMPTY)
        del parent.children[node.name.lower()]

    def rename_object(self, old_path, new_path):
        old_parent, _old_rel, old_name = self._find_parent(old_path)
        node = old_parent.children.get(old_name.lower())
        if node is None:
            raise HandlerError(ERROR_OBJECT_NOT_FOUND)
        new_parent, _new_rel, new_name = self._find_parent(new_path)
        existing = new_parent.children.get(new_name.lower())
        if existing is not None and existing is not node:
            raise HandlerError(ERROR_OBJECT_IN_USE)
        del old_parent.children[node.name.lower()]
        node.name = new_name
        new_parent.children[new_name.lower()] = node

    def set_protect(self, ami_path, mask):
        found = self._find(ami_path)
        if found is None:
            raise HandlerError(ERROR_OBJECT_NOT_FOUND)
        found[0].protection = mask

    def set_comment(self, ami_path, comment):
        found = self._find(ami_path)
        if found is None:
            raise HandlerError(ERROR_OBJECT_NOT_FOUND)
        found[0].comment = comment

    def set_date(self, ami_path, date):
        found = self._find(ami_path)
        if found is None:
            raise HandlerError(ERROR_OBJECT_NOT_FOUND)
        found[0].date = date

    def create_dir(self, ami_path):
        parent, _parent_rel, name = self._find_parent(ami_path)
        if name.lower() in parent.children:
            raise HandlerError(ERROR_OBJECT_EXISTS)
        parent.children[name.lower()] = RamNode(name, is_dir=True)
