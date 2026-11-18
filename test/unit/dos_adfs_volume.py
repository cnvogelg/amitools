"""End-to-end: an ADFS image mounted as a volume driven through dos.library.

A volume whose source is a file is backed by the ``adfs`` handler. This test
mounts a real ADFS image through :func:`main` and then runs dos.library path
operations (``Lock``, ``Examine``, ``OpenFromLock``, ``Read``, ``Open``,
``Write``, ``Close``) from a real DOS process, so the whole chain

    dos.library -> lock/file manager -> handler manager -> AdfsHandler -> amitools.fs

is exercised, not only the handler manager.
"""

from amitools.fs import DosType
from amitools.fs.ADFSVolume import ADFSVolume
from amitools.fs.FSString import FSString
from amitools.fs.blkdev.ADFBlockDevice import ADFBlockDevice
from amitools.vamos.handler import MODE_NEWFILE, AdfsHandler
from amitools.vamos.lib.dos.Error import DOSTRUE
from amitools.vamos.libstructs import FileInfoBlockStruct
from amitools.vamos.machine.regs import REG_D1, REG_D2
from amitools.vamos.main import main
from amitools.vamos.mode import BaseMode
from amitools.vamos.task import DosProcess

DATA = b"hello adfs"
NEW_DATA = b"written through dos"


def make_image(path, name="work"):
    """create a small ADFS image with one file and return its path"""
    blkdev = ADFBlockDevice(str(path))
    blkdev.create()
    volume = ADFSVolume(blkdev)
    volume.create(FSString(name), dos_type=DosType.DOS0)
    volume.write_file(DATA, FSString("hello.txt"))
    volume.close()
    blkdev.close()
    return str(path)


def dos_adfs_volume_e2e_test(tmp_path):
    image = make_image(tmp_path / "disk.adf")

    def proc(ctx, task):
        # the volume is served by the adfs handler over the image file
        assert isinstance(ctx.handler_mgr.get_handler("work"), AdfsHandler)

        dos_lib = ctx.dos_lib
        cpu = ctx.cpu
        mem = ctx.mem
        alloc = ctx.alloc

        # Lock() resolves the name through the handler chain
        name = alloc.alloc_cstr("work:hello.txt")
        cpu.w_reg(REG_D1, name.addr)
        cpu.w_reg(REG_D2, 0xFFFFFFFF)  # exclusive
        lock_b = dos_lib.Lock(ctx)
        alloc.free_cstr(name)
        assert lock_b != 0

        # Examine() fills a FileInfoBlock from the ADFS handler
        fib_mem = alloc.alloc_astruct(FileInfoBlockStruct, label="FIB")
        cpu.w_reg(REG_D1, lock_b)
        cpu.w_reg(REG_D2, fib_mem.addr)
        assert dos_lib.Examine(ctx) == DOSTRUE
        fib = FileInfoBlockStruct(mem, fib_mem.addr)
        assert mem.r_cstr(fib.fib_FileName.addr) == "hello.txt"
        assert fib.fib_Size.val == len(DATA)
        alloc.free_struct(fib_mem)

        # OpenFromLock() + Read() read the data back through the handler; the
        # handle absorbs the lock, so no UnLock is needed
        cpu.w_reg(REG_D1, lock_b)
        fh_b = dos_lib.OpenFromLock(ctx)
        assert fh_b != 0
        buf = alloc.alloc_memory(len(DATA), label="buf")
        assert dos_lib.Read(ctx, fh_b, buf.addr, len(DATA)) == len(DATA)
        assert bytes(mem.r_block(buf.addr, len(DATA))) == DATA
        alloc.free_memory(buf)
        assert dos_lib.Close(ctx, fh_b) == DOSTRUE

        # Open() + Write() + Close() create a new file through the handler;
        # the handler buffers it and writes it back to the image on shutdown
        name = alloc.alloc_cstr("work:new.txt")
        fh_b = dos_lib.Open(ctx, name.addr, MODE_NEWFILE)
        alloc.free_cstr(name)
        assert fh_b != 0
        buf = alloc.alloc_memory(len(NEW_DATA), label="buf")
        mem.w_block(buf.addr, NEW_DATA)
        assert dos_lib.Write(ctx, fh_b, buf.addr, len(NEW_DATA)) == len(NEW_DATA)
        alloc.free_memory(buf)
        assert dos_lib.Close(ctx, fh_b) == DOSTRUE
        return 0

    def gen_task_list(mode_ctx):
        dos_ctx = mode_ctx.dos_ctx
        return [
            DosProcess(
                dos_ctx.machine,
                dos_ctx.alloc,
                "adfs",
                func=lambda task: proc(dos_ctx, task),
            )
        ]

    mode = BaseMode("adfs", gen_task_list)
    args = [
        "--vols-base-dir",
        str(tmp_path / "volumes"),
        "-V",
        "work:" + image,
    ]
    assert main(cfg_files=[], args=args, mode=mode, single_return_code=False) == [0]

    # after unmounting, the new file is persisted in the image file system
    blkdev = ADFBlockDevice(image)
    blkdev.open()
    volume = ADFSVolume(blkdev)
    volume.open()
    node = volume.get_path_name(FSString("new.txt"))
    assert node is not None
    assert node.get_file_data() == NEW_DATA
    volume.close()
    blkdev.close()
