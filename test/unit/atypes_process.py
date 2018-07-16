import pytest
from amitools.vamos.machine import MockMemory
from amitools.vamos.mem import MemoryAlloc
from amitools.vamos.astructs import BAddr
from amitools.vamos.atypes import Process, NodeType, CLI


def atypes_process_base_test():
  mem = MockMemory()
  alloc = MemoryAlloc(mem)
  # alloc proc
  name = "my_proc"
  proc = Process.alloc(alloc, name)
  assert proc.get_name() == name
  # proc setup
  proc.setup()
  node = proc.task.node
  assert node.type == NodeType.NT_PROCESS
  # done
  proc.free()
  assert alloc.is_all_free()


def atypes_process_bptr_test():
  mem = MockMemory()
  alloc = MemoryAlloc(mem)
  # alloc proc
  proc = Process.alloc(alloc)
  # set list
  proc.seg_list = 0x100
  assert proc.seg_list == BAddr(0x40)
  # check in mem seg list baddr
  struct = proc.get_type_struct()
  off = struct.pr_SegList_field.offset
  addr = proc.addr + off
  assert mem.r32(addr) == 0x40
  # setup CLI
  cli = CLI.alloc(alloc)
  proc.cli = cli
  assert type(proc.cli) is CLI
  assert proc.cli == cli.addr
  # check in mem CLI baddr
  off = struct.pr_CLI_field.offset
  addr = proc.addr + off
  assert mem.r32(addr) == BAddr.from_addr(cli.addr).get_baddr()
  cli.free()
  # done
  proc.free()
  assert alloc.is_all_free()
