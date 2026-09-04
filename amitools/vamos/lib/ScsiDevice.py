"""File-backed ``scsi.device`` implementation for vamos.

The device translates trackdisk, TD64, NSD, and selected direct SCSI
commands to a block backend.  A backend supplies geometry plus
``read_blocks()``, ``write_blocks()``, and optionally ``sync()``.  The
constructor also accepts a provider with ``get_backend(unit)`` so one device
implementation can route separate IORequests to separate units.
"""

from amitools.vamos.libcore import LibImpl
from amitools.vamos.libstructs import IORequestStruct, SCSICmdStruct, UnitStruct


IOF_QUICK = 0x01

CMD_READ = 2
CMD_WRITE = 3
CMD_UPDATE = 4
CMD_CLEAR = 5
TD_SEEK = 10
TD_FORMAT = 11
TD_CHANGENUM = 13
TD_ADDCHANGEINT = 20
TD_REMCHANGEINT = 21
TD_GETGEOMETRY = 22
TD_READ64 = 24
TD_WRITE64 = 25
TD_SEEK64 = 26
TD_FORMAT64 = 27
HD_SCSICMD = 28

NSCMD_DEVICEQUERY = 0x4000
NSCMD_TD_READ64 = 0xC000
NSCMD_TD_WRITE64 = 0xC001
NSCMD_TD_SEEK64 = 0xC002
NSCMD_TD_FORMAT64 = 0xC003
NSDEVTYPE_TRACKDISK = 5

IOERR_OPENFAIL = -1
IOERR_ABORTED = -2
IOERR_NOCMD = -3
IOERR_BADLENGTH = -4
IOERR_BADADDRESS = -5
TDERR_NOT_SPECIFIED = 20
TDERR_WRITE_PROT = 28
TDERR_NO_MEM = 31
TDERR_BAD_UNIT_NUM = 32


_CMD_NAMES = {
    CMD_READ: "CMD_READ",
    CMD_WRITE: "CMD_WRITE",
    CMD_UPDATE: "CMD_UPDATE",
    CMD_CLEAR: "CMD_CLEAR",
    9: "TD_MOTOR",
    TD_SEEK: "TD_SEEK",
    TD_FORMAT: "TD_FORMAT",
    TD_CHANGENUM: "TD_CHANGENUM",
    14: "TD_CHANGESTATE",
    15: "TD_PROTSTATUS",
    18: "TD_GETDRIVETYPE",
    TD_ADDCHANGEINT: "TD_ADDCHANGEINT",
    TD_REMCHANGEINT: "TD_REMCHANGEINT",
    TD_GETGEOMETRY: "TD_GETGEOMETRY",
    TD_READ64: "TD_READ64",
    TD_WRITE64: "TD_WRITE64",
    TD_SEEK64: "TD_SEEK64",
    TD_FORMAT64: "TD_FORMAT64",
    HD_SCSICMD: "HD_SCSICMD",
    NSCMD_DEVICEQUERY: "NSCMD_DEVICEQUERY",
    NSCMD_TD_READ64: "NSCMD_TD_READ64",
    NSCMD_TD_WRITE64: "NSCMD_TD_WRITE64",
    NSCMD_TD_SEEK64: "NSCMD_TD_SEEK64",
    NSCMD_TD_FORMAT64: "NSCMD_TD_FORMAT64",
}


SUPPORTED_COMMANDS = (
    CMD_READ,
    CMD_WRITE,
    CMD_UPDATE,
    CMD_CLEAR,
    TD_SEEK,
    TD_FORMAT,
    TD_CHANGENUM,
    TD_ADDCHANGEINT,
    TD_REMCHANGEINT,
    TD_GETGEOMETRY,
    TD_READ64,
    TD_WRITE64,
    TD_SEEK64,
    TD_FORMAT64,
    HD_SCSICMD,
    NSCMD_DEVICEQUERY,
    NSCMD_TD_READ64,
    NSCMD_TD_WRITE64,
    NSCMD_TD_SEEK64,
    NSCMD_TD_FORMAT64,
    0,
)


class ScsiDevice(LibImpl):
    """Expose one backend, or a per-unit backend provider, as scsi.device."""

    def __init__(
        self,
        backend,
        debug=False,
        acknowledge_read_only_writes=False,
        acknowledge_unsupported_commands=False,
    ):
        super().__init__()
        # Inspect the type instead of using hasattr() on the instance.  Mock
        # objects (and other dynamic proxies) manufacture arbitrary attributes
        # and would otherwise be mistaken for providers.
        if callable(getattr(type(backend), "get_backend", None)):
            self.backend_provider = backend
            # Keep the historical unit-0 attribute available to callers that
            # wrap BeginIO(), while routing opened requests through the
            # provider below.
            self.backend = backend.get_backend(0)
        else:
            self.backend_provider = None
            self.backend = backend
        self.debug = debug
        self.acknowledge_read_only_writes = acknowledge_read_only_writes
        self.acknowledge_unsupported_commands = (
            acknowledge_unsupported_commands
        )
        self._unit_backends = {}
        self._nsd_cmd_mem = None
        self._nsd_cmd_alloc = None

    def get_version(self):
        return 40

    def open_lib(self, ctx, open_cnt):
        return 0

    def close_lib(self, ctx, open_cnt):
        return 0

    def finish_lib(self, ctx):
        if self._nsd_cmd_mem is not None:
            self._nsd_cmd_alloc.free_memory(self._nsd_cmd_mem)
            self._nsd_cmd_mem = None
            self._nsd_cmd_alloc = None
        for _, unit in self._unit_backends.values():
            unit.free()
        self._unit_backends.clear()

    def _provide_backend(self, unit):
        if self.backend_provider is not None:
            return self.backend_provider.get_backend(unit)
        if unit == 0:
            return self.backend
        return None

    def open_dev(self, ctx, io_request, unit, flags):
        """Bind an opened IORequest to the backend for its requested unit."""
        backend = self._provide_backend(unit)
        if backend is None:
            return TDERR_BAD_UNIT_NUM
        if unit == 0:
            self.backend = backend
        # io_Unit belongs to the device and survives copies of the request.
        # Each open owns a binding until CloseDevice, including any copies
        # the caller uses for additional transfers during that open.
        unit_mem = ctx.alloc.alloc_astruct(UnitStruct, label="scsi.device unit")
        self._unit_backends[unit_mem.addr] = (backend, unit_mem)
        IORequestStruct(ctx.mem, io_request).unit.aptr = unit_mem.addr
        return 0

    def close_dev(self, ctx, io_request):
        io = IORequestStruct(ctx.mem, io_request)
        binding = self._unit_backends.pop(io.unit.aptr, None)
        if binding is not None:
            binding[1].free()
        io.unit.aptr = 0

    def _get_backend(self, ior):
        binding = self._unit_backends.get(ior.unit.aptr)
        if binding is not None:
            return binding[0]
        # Preserve direct use by AmiFUSE and existing tests that invoke
        # BeginIO without routing through ExecLibrary.OpenDevice().
        if self.backend_provider is not None:
            return None
        return self.backend

    def _acknowledges_read_only_writes(self, backend):
        """Return whether protected writes use compatibility semantics.

        AmiFUSE historically acknowledged journal-replay writes on read-only
        mounts without changing the image.  The shared device reports normal
        write-protect errors unless that behavior is explicitly requested on
        the device or its backend provider.
        """
        if not getattr(backend, "read_only", False):
            return False
        if self.acknowledge_read_only_writes:
            return True
        return self.backend_provider is not None and bool(
            getattr(
                self.backend_provider,
                "acknowledge_read_only_writes",
                False,
            )
        )

    def _acknowledges_unsupported_commands(self):
        if self.acknowledge_unsupported_commands:
            return True
        return self.backend_provider is not None and bool(
            getattr(
                self.backend_provider,
                "acknowledge_unsupported_commands",
                False,
            )
        )

    def _check_block_bounds(self, block_num, num_blocks, backend=None):
        if backend is None:
            backend = self.backend
        if backend is None or block_num < 0 or num_blocks < 0:
            return False
        valid = block_num + num_blocks <= backend.total_blocks
        if not valid and self.debug:
            print(
                "[SCSI] Block bounds check FAILED: "
                f"block={block_num} count={num_blocks} "
                f"total={backend.total_blocks}",
                flush=True,
            )
        return valid

    def _get_transfer(self, backend, offset, length):
        block_size = getattr(backend, "block_size", 0)
        if (
            block_size <= 0
            or offset % block_size
            or length % block_size
        ):
            return None
        block_num = offset // block_size
        num_blocks = length // block_size
        if not self._check_block_bounds(block_num, num_blocks, backend):
            return None
        return block_num, num_blocks

    @staticmethod
    def _set_io_error(ior, error):
        ior.error.val = error
        ior.actual.val = 0

    def _read(self, mem, ior, backend, offset, length, buf_ptr):
        transfer = self._get_transfer(backend, offset, length)
        if transfer is None:
            self._set_io_error(ior, IOERR_BADLENGTH)
            return
        if length and not buf_ptr:
            self._set_io_error(ior, IOERR_BADADDRESS)
            return
        block_num, num_blocks = transfer
        if length:
            try:
                data = backend.read_blocks(block_num, num_blocks)
            except (IOError, OSError):
                self._set_io_error(ior, TDERR_NOT_SPECIFIED)
                return
        else:
            data = b""
        if len(data) != length:
            self._set_io_error(ior, IOERR_BADLENGTH)
            return
        if length:
            mem.w_block(buf_ptr, data)
        ior.actual.val = length

    def _write(self, mem, ior, backend, offset, length, buf_ptr):
        if getattr(backend, "read_only", False):
            if self._acknowledges_read_only_writes(backend):
                ior.actual.val = length
            else:
                self._set_io_error(ior, TDERR_WRITE_PROT)
            return
        transfer = self._get_transfer(backend, offset, length)
        if transfer is None:
            self._set_io_error(ior, IOERR_BADLENGTH)
            return
        if length and not buf_ptr:
            self._set_io_error(ior, IOERR_BADADDRESS)
            return
        block_num, num_blocks = transfer
        data = mem.r_block(buf_ptr, length) if length else b""
        if length:
            try:
                backend.write_blocks(block_num, data, num_blocks)
            except PermissionError:
                self._set_io_error(ior, TDERR_WRITE_PROT)
                return
            except (IOError, OSError):
                self._set_io_error(ior, TDERR_NOT_SPECIFIED)
                return
        ior.actual.val = length

    @staticmethod
    def _write_sense(mem, sense_ptr, sense_len, key, asc, ascq=0):
        if not sense_ptr or sense_len < 18:
            return 0
        sense = bytearray(18)
        sense[0] = 0x70
        sense[2] = key
        sense[7] = 0x0A
        sense[12] = asc
        sense[13] = ascq
        mem.w_block(sense_ptr, bytes(sense))
        return 18

    def _scsi_cmd(self, mem, ior, backend, buf_ptr):
        scsi = SCSICmdStruct(mem, buf_ptr)
        cdb_ptr = scsi.scsi_Command.val
        cdb_len = scsi.scsi_CmdLength.val
        data_ptr = scsi.scsi_Data.val
        data_len = scsi.scsi_Length.val
        sense_ptr = scsi.scsi_SenseData.val
        sense_len = scsi.scsi_SenseLength.val
        opcode = mem.r8(cdb_ptr) if cdb_ptr and cdb_len else None
        actual = 0
        status = 0
        sense_actual = 0

        if sense_ptr:
            mem.w_block(sense_ptr, b"\x00" * min(sense_len, 18))

        cdb_lengths = {
            0x00: 6,
            0x03: 6,
            0x08: 6,
            0x12: 6,
            0x1A: 6,
            0x25: 10,
            0x28: 10,
            0x2A: 10,
        }
        required_cdb_len = cdb_lengths.get(opcode, 1)

        if opcode is None or cdb_len < required_cdb_len:
            status = 2
            sense_actual = self._write_sense(
                mem, sense_ptr, sense_len, 0x05, 0x24
            )
        elif opcode == 0x00:  # TEST UNIT READY
            pass
        elif opcode == 0x03:  # REQUEST SENSE
            actual = min(data_len, 18)
            if actual and not data_ptr:
                status = 2
                actual = 0
                sense_actual = self._write_sense(
                    mem, sense_ptr, sense_len, 0x05, 0x24
                )
            elif actual:
                mem.w_block(data_ptr, b"\x00" * actual)
        elif opcode == 0x12:  # INQUIRY
            alloc_len = mem.r8(cdb_ptr + 4) if cdb_len > 4 else data_len
            alloc_len = min(alloc_len, data_len)
            response = bytearray(max(alloc_len, 36))
            is_cd = getattr(backend, "iso_info", None) is not None
            response[0] = 0x05 if is_cd else 0x00
            response[1] = 0x80 if is_cd else 0x00
            response[2] = 0x05
            response[3] = 0x02
            response[4] = len(response) - 5
            if alloc_len and not data_ptr:
                status = 2
                sense_actual = self._write_sense(
                    mem, sense_ptr, sense_len, 0x05, 0x24
                )
            elif alloc_len:
                mem.w_block(data_ptr, bytes(response[:alloc_len]))
                actual = alloc_len
        elif opcode == 0x1A:  # MODE SENSE(6)
            alloc_len = mem.r8(cdb_ptr + 4) if cdb_len > 4 else data_len
            response = bytearray([0, 0, 0x80 if backend.read_only else 0, 0])
            actual = min(alloc_len, data_len, len(response))
            if actual and not data_ptr:
                status = 2
                actual = 0
                sense_actual = self._write_sense(
                    mem, sense_ptr, sense_len, 0x05, 0x24
                )
            elif actual:
                mem.w_block(data_ptr, bytes(response[:actual]))
        elif opcode == 0x25:  # READ CAPACITY(10)
            last_lba = min(max(backend.total_blocks - 1, 0), 0xFFFFFFFF)
            response = last_lba.to_bytes(4, "big")
            response += backend.block_size.to_bytes(4, "big")
            actual = min(data_len, len(response))
            if actual and not data_ptr:
                status = 2
                actual = 0
                sense_actual = self._write_sense(
                    mem, sense_ptr, sense_len, 0x05, 0x24
                )
            elif actual:
                mem.w_block(data_ptr, response[:actual])
        elif opcode in (0x08, 0x28):  # READ(6), READ(10)
            if opcode == 0x08:
                lba = (
                    ((mem.r8(cdb_ptr + 1) & 0x1F) << 16)
                    | (mem.r8(cdb_ptr + 2) << 8)
                    | mem.r8(cdb_ptr + 3)
                )
                num_blocks = mem.r8(cdb_ptr + 4) or 256
            else:
                lba = mem.r32(cdb_ptr + 2)
                num_blocks = mem.r16(cdb_ptr + 7)
            expected = num_blocks * backend.block_size
            if (
                not self._check_block_bounds(lba, num_blocks, backend)
                or expected > data_len
                or (expected and not data_ptr)
            ):
                status = 2
                sense_actual = self._write_sense(
                    mem, sense_ptr, sense_len, 0x05, 0x24
                )
            else:
                if expected:
                    try:
                        data = backend.read_blocks(lba, num_blocks)
                    except (IOError, OSError):
                        data = None
                else:
                    data = b""
                if data is None or len(data) != expected:
                    status = 2
                    sense_actual = self._write_sense(
                        mem, sense_ptr, sense_len, 0x03, 0x11
                    )
                else:
                    if expected:
                        mem.w_block(data_ptr, data)
                    actual = expected
        elif opcode == 0x2A:  # WRITE(10)
            lba = mem.r32(cdb_ptr + 2)
            num_blocks = mem.r16(cdb_ptr + 7)
            expected = num_blocks * backend.block_size
            if getattr(backend, "read_only", False):
                if self._acknowledges_read_only_writes(backend):
                    actual = expected
                else:
                    status = 2
                    sense_actual = self._write_sense(
                        mem, sense_ptr, sense_len, 0x07, 0x27
                    )
            elif (
                not self._check_block_bounds(lba, num_blocks, backend)
                or expected > data_len
                or (expected and not data_ptr)
            ):
                status = 2
                sense_actual = self._write_sense(
                    mem, sense_ptr, sense_len, 0x05, 0x24
                )
            else:
                data = mem.r_block(data_ptr, expected) if expected else b""
                if expected:
                    try:
                        backend.write_blocks(lba, data, num_blocks)
                    except PermissionError:
                        status = 2
                        sense_actual = self._write_sense(
                            mem, sense_ptr, sense_len, 0x07, 0x27
                        )
                    except (IOError, OSError):
                        status = 2
                        sense_actual = self._write_sense(
                            mem, sense_ptr, sense_len, 0x03, 0x0C
                        )
                    else:
                        actual = expected
        else:
            status = 2
            sense_actual = self._write_sense(
                mem, sense_ptr, sense_len, 0x05, 0x20
            )

        scsi.scsi_CmdActual.val = cdb_len
        scsi.scsi_Status.val = status
        scsi.scsi_Actual.val = actual
        scsi.scsi_SenseActual.val = sense_actual
        ior.actual.val = actual

    def _get_nsd_command_table(self, ctx):
        if self._nsd_cmd_mem is not None:
            return self._nsd_cmd_mem.addr
        size = len(SUPPORTED_COMMANDS) * 2
        mem_obj = ctx.alloc.alloc_memory(
            size, label="scsi.device NSD commands", except_on_failure=False
        )
        if mem_obj is None:
            return 0
        self._nsd_cmd_mem = mem_obj
        self._nsd_cmd_alloc = ctx.alloc
        for pos, command in enumerate(SUPPORTED_COMMANDS):
            ctx.mem.w16(mem_obj.addr + pos * 2, command)
        return mem_obj.addr

    def _debug_request(self, backend, cmd, offset, length, buf_ptr, io_actual):
        if not self.debug:
            return
        name = _CMD_NAMES.get(cmd, f"CMD_{cmd}")
        extra = ""
        if cmd in (
            TD_READ64,
            TD_WRITE64,
            NSCMD_TD_READ64,
            NSCMD_TD_WRITE64,
        ):
            offset64 = (io_actual << 32) | offset
            extra = f" offset64={offset64}"
        elif cmd == TD_GETGEOMETRY:
            extra = (
                f" total={backend.total_blocks} cyls={backend.cyls} "
                f"heads={backend.heads} secs={backend.secs}"
            )
        print(
            f"[SCSI] {name} offset={offset} len={length} "
            f"buf=0x{buf_ptr:x}{extra}",
            flush=True,
        )

    def BeginIO(self, ctx, io_request):
        mem = ctx.mem
        ior = IORequestStruct(mem, io_request)
        cmd = ior.command.val
        length = ior.length.val
        offset = ior.offset.val
        buf_ptr = ior.data.val
        io_actual = ior.actual.val
        backend = self._get_backend(ior)

        ior.error.val = 0
        ior.flags.val |= IOF_QUICK
        if backend is None:
            self._set_io_error(ior, TDERR_BAD_UNIT_NUM)
            return 0

        self._debug_request(backend, cmd, offset, length, buf_ptr, io_actual)

        if cmd == HD_SCSICMD:
            if not buf_ptr:
                self._set_io_error(ior, IOERR_BADADDRESS)
            elif length < SCSICmdStruct.get_byte_size():
                self._set_io_error(ior, IOERR_BADLENGTH)
            else:
                self._scsi_cmd(mem, ior, backend, buf_ptr)
        elif cmd == CMD_READ:
            self._read(mem, ior, backend, offset, length, buf_ptr)
        elif cmd == CMD_WRITE:
            self._write(mem, ior, backend, offset, length, buf_ptr)
        elif cmd in (TD_READ64, NSCMD_TD_READ64):
            offset64 = (io_actual << 32) | offset
            self._read(mem, ior, backend, offset64, length, buf_ptr)
        elif cmd in (TD_WRITE64, NSCMD_TD_WRITE64):
            offset64 = (io_actual << 32) | offset
            self._write(mem, ior, backend, offset64, length, buf_ptr)
        elif cmd == TD_GETGEOMETRY:
            if not buf_ptr or length < 32:
                self._set_io_error(ior, IOERR_BADLENGTH)
            else:
                cyl_secs = backend.secs * backend.heads
                mem.w32(buf_ptr + 0, backend.block_size)
                mem.w32(buf_ptr + 4, backend.total_blocks)
                mem.w32(buf_ptr + 8, backend.cyls)
                mem.w32(buf_ptr + 12, cyl_secs)
                mem.w32(buf_ptr + 16, backend.heads)
                mem.w32(buf_ptr + 20, backend.secs)
                mem.w32(buf_ptr + 24, 1)
                mem.w8(buf_ptr + 28, 0)
                mem.w8(buf_ptr + 29, 0)
                mem.w16(buf_ptr + 30, 0)
                ior.actual.val = 0
        elif cmd == 9:  # TD_MOTOR
            ior.actual.val = 0
        elif cmd == TD_FORMAT:
            self._write(mem, ior, backend, offset, length, buf_ptr)
        elif cmd in (TD_FORMAT64, NSCMD_TD_FORMAT64):
            offset64 = (io_actual << 32) | offset
            self._write(mem, ior, backend, offset64, length, buf_ptr)
        elif cmd == TD_CHANGENUM:
            ior.actual.val = 0
        elif cmd == 14:  # TD_CHANGESTATE
            ior.actual.val = 0
        elif cmd == 15:  # TD_PROTSTATUS
            ior.actual.val = 1 if backend.read_only else 0
        elif cmd == 18:  # TD_GETDRIVETYPE
            ior.actual.val = 0
        elif cmd == CMD_UPDATE:
            try:
                if hasattr(backend, "sync"):
                    backend.sync()
            except (IOError, OSError):
                self._set_io_error(ior, TDERR_NOT_SPECIFIED)
            else:
                ior.actual.val = 0
        elif cmd == CMD_CLEAR:
            ior.actual.val = 0
        elif cmd in (TD_SEEK, TD_SEEK64, NSCMD_TD_SEEK64):
            ior.actual.val = 0
        elif cmd == TD_ADDCHANGEINT:
            ior.flags.val &= ~IOF_QUICK
            ior.actual.val = 0
        elif cmd == TD_REMCHANGEINT:
            ior.actual.val = 0
        elif cmd == NSCMD_DEVICEQUERY:
            if not buf_ptr or length < 16:
                self._set_io_error(ior, IOERR_NOCMD)
            else:
                table_addr = self._get_nsd_command_table(ctx)
                if not table_addr:
                    self._set_io_error(ior, TDERR_NO_MEM)
                else:
                    mem.w32(buf_ptr + 0, 0)
                    mem.w32(buf_ptr + 4, 16)
                    mem.w16(buf_ptr + 8, NSDEVTYPE_TRACKDISK)
                    mem.w16(buf_ptr + 10, 0)
                    mem.w32(buf_ptr + 12, table_addr)
                    ior.actual.val = 16
        else:
            if self._acknowledges_unsupported_commands():
                ior.actual.val = 0
            else:
                self._set_io_error(ior, IOERR_NOCMD)
        return 0

    def AbortIO(self, ctx, io_request):
        if io_request:
            ior = IORequestStruct(ctx.mem, io_request)
            ior.error.val = IOERR_ABORTED
            ior.actual.val = 0
            ior.flags.val |= IOF_QUICK
        return 0


__all__ = [
    "IOF_QUICK",
    "CMD_READ",
    "CMD_WRITE",
    "CMD_UPDATE",
    "CMD_CLEAR",
    "TD_SEEK",
    "TD_FORMAT",
    "TD_CHANGENUM",
    "TD_ADDCHANGEINT",
    "TD_REMCHANGEINT",
    "TD_GETGEOMETRY",
    "TD_READ64",
    "TD_WRITE64",
    "TD_SEEK64",
    "TD_FORMAT64",
    "HD_SCSICMD",
    "NSCMD_DEVICEQUERY",
    "NSCMD_TD_READ64",
    "NSCMD_TD_WRITE64",
    "NSCMD_TD_SEEK64",
    "NSCMD_TD_FORMAT64",
    "NSDEVTYPE_TRACKDISK",
    "IOERR_OPENFAIL",
    "IOERR_ABORTED",
    "IOERR_NOCMD",
    "IOERR_BADLENGTH",
    "IOERR_BADADDRESS",
    "TDERR_NOT_SPECIFIED",
    "TDERR_WRITE_PROT",
    "TDERR_NO_MEM",
    "TDERR_BAD_UNIT_NUM",
    "SCSICmdStruct",
    "ScsiDevice",
]
