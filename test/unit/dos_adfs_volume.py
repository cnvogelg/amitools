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
from amitools.vamos.astructs import CSTR, LONG
from amitools.vamos.handler import MODE_NEWFILE, AdfsHandler
from amitools.vamos.lib.dos.Error import DOSTRUE
from amitools.vamos.libstructs import FileInfoBlockStruct
from amitools.vamos.machine.regs import REG_D1, REG_D2, REG_D3, REG_D4, REG_D5
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
        lock_b = dos_lib.Lock(
            ctx, CSTR(cpu=cpu, reg=REG_D1, mem=mem), cpu.r_reg(REG_D2)
        )
        alloc.free_cstr(name)
        assert lock_b != 0

        # Examine() fills a FileInfoBlock from the ADFS handler
        fib_mem = alloc.alloc_astruct(FileInfoBlockStruct, label="FIB")
        cpu.w_reg(REG_D1, lock_b)
        cpu.w_reg(REG_D2, fib_mem.addr)
        assert dos_lib.Examine(ctx, cpu.r_reg(REG_D1), cpu.r_reg(REG_D2)) == DOSTRUE
        fib = FileInfoBlockStruct(mem, fib_mem.addr)
        assert mem.r_cstr(fib.fib_FileName.addr) == "hello.txt"
        assert fib.fib_Size.val == len(DATA)
        alloc.free_struct(fib_mem)

        # OpenFromLock() + Read() read the data back through the handler; the
        # handle absorbs the lock, so no UnLock is needed
        cpu.w_reg(REG_D1, lock_b)
        fh_b = dos_lib.OpenFromLock(ctx, cpu.r_reg(REG_D1))
        assert fh_b != 0
        buf = alloc.alloc_memory(len(DATA), label="buf")
        assert dos_lib.Read(ctx, fh_b, buf.addr, len(DATA)) == len(DATA)
        assert bytes(mem.r_block(buf.addr, len(DATA))) == DATA
        alloc.free_memory(buf)
        assert dos_lib.Close(ctx, fh_b) == DOSTRUE

        # MakeLink() creates a soft link through the handler; ReadLink()
        # returns the stored target through a directory lock
        link_name = alloc.alloc_cstr("work:link.txt")
        target_name = alloc.alloc_cstr("hello.txt")
        cpu.w_reg(REG_D1, link_name.addr)
        cpu.w_reg(REG_D2, target_name.addr)
        cpu.w_reg(REG_D3, 1)  # LINK_SOFT
        assert (
            dos_lib.MakeLink(
                ctx,
                CSTR(cpu=cpu, reg=REG_D1, mem=mem),
                LONG(cpu=cpu, reg=REG_D2, mem=mem),
                LONG(cpu=cpu, reg=REG_D3, mem=mem),
            )
            == DOSTRUE
        )
        alloc.free_cstr(link_name)
        alloc.free_cstr(target_name)

        # a Lock() on the link resolves to the target file
        name = alloc.alloc_cstr("work:link.txt")
        cpu.w_reg(REG_D1, name.addr)
        cpu.w_reg(REG_D2, 0xFFFFFFFF)
        link_b = dos_lib.Lock(
            ctx, CSTR(cpu=cpu, reg=REG_D1, mem=mem), cpu.r_reg(REG_D2)
        )
        alloc.free_cstr(name)
        assert link_b != 0
        cpu.w_reg(REG_D1, link_b)
        fh_b = dos_lib.OpenFromLock(ctx, cpu.r_reg(REG_D1))
        assert fh_b != 0
        buf = alloc.alloc_memory(len(DATA), label="buf")
        assert dos_lib.Read(ctx, fh_b, buf.addr, len(DATA)) == len(DATA)
        assert bytes(mem.r_block(buf.addr, len(DATA))) == DATA
        alloc.free_memory(buf)
        assert dos_lib.Close(ctx, fh_b) == DOSTRUE

        # ReadLink() with a lock on the link's directory returns the target
        root_name = alloc.alloc_cstr("work:")
        cpu.w_reg(REG_D1, root_name.addr)
        cpu.w_reg(REG_D2, 0xFFFFFFFF)
        root_b = dos_lib.Lock(
            ctx, CSTR(cpu=cpu, reg=REG_D1, mem=mem), cpu.r_reg(REG_D2)
        )
        alloc.free_cstr(root_name)
        assert root_b != 0
        link_path = alloc.alloc_cstr("link.txt")
        buf = alloc.alloc_memory(64, label="linkbuf")
        cpu.w_reg(REG_D1, 0)  # port
        cpu.w_reg(REG_D2, root_b)
        cpu.w_reg(REG_D3, link_path.addr)
        cpu.w_reg(REG_D4, buf.addr)
        cpu.w_reg(REG_D5, 64)
        assert dos_lib.ReadLink(
            ctx,
            LONG(cpu=cpu, reg=REG_D1, mem=mem),
            LONG(cpu=cpu, reg=REG_D2, mem=mem),
            CSTR(cpu=cpu, reg=REG_D3, mem=mem),
            LONG(cpu=cpu, reg=REG_D4, mem=mem),
            LONG(cpu=cpu, reg=REG_D5, mem=mem),
        ) == len("hello.txt")
        assert mem.r_cstr(buf.addr) == "hello.txt"
        alloc.free_cstr(link_path)
        alloc.free_memory(buf)
        cpu.w_reg(REG_D1, root_b)
        dos_lib.UnLock(ctx, cpu.r_reg(REG_D1))

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
    # the soft link is persisted and still resolves to its target
    link = volume.get_link_path_name(FSString("link.txt"))
    assert link is not None
    assert link.get_target().get_unicode() == "hello.txt"
    assert volume.read_file(FSString("link.txt")) == DATA
    volume.close()
    blkdev.close()
