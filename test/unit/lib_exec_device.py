from amitools.vamos.lib.lexec.devicefunc import DeviceMixin
from amitools.vamos.libstructs import DeviceStruct, NodeType
from lib_exec_helper import ExecHost, make_exec_lib


class Host(ExecHost, DeviceMixin):
    pass


def exec_add_rem_device_test():
    mem, alloc, el = make_exec_lib()
    host = Host(mem, alloc, el)
    dev = alloc.alloc_astruct(DeviceStruct, label="device")
    host.AddDevice(host.ctx, dev)
    node = host.exec_lib.device_list.get_head()
    assert node.addr == dev.addr
    assert node.type.val == NodeType.NT_DEVICE
    host.RemDevice(host.ctx, dev)
    assert host.exec_lib.device_list.is_empty()
