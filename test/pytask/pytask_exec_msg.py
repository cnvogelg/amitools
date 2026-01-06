import pytest
from amitools.vamos.libtypes import MsgPort, Message


def pytask_exec_msg_create_delete_port_test(vamos_task):
    def task(ctx, task):
        # get exec library
        exec_lib = ctx.proxies.get_exec_lib_proxy()

        # create a new port
        port = exec_lib.CreateMsgPort()
        assert type(port) is MsgPort

        # delete a message port
        exec_lib.DeleteMsgPort(port)

        return 0

    exit_codes = vamos_task.run([task])
    assert exit_codes == [0]


def pytask_exec_msg_put_get_test(vamos_task):
    def task(ctx, task):
        # get exec library
        exec_lib = ctx.proxies.get_exec_lib_proxy()

        # create a new port
        port = exec_lib.CreateMsgPort()
        assert type(port) is MsgPort

        # port is empty
        msg = exec_lib.GetMsg(port)
        assert msg is None

        # alloc message
        msg = Message.alloc(ctx.alloc)
        assert msg

        # put a message to port
        exec_lib.PutMsg(port, msg)

        # get message from port
        msg2 = exec_lib.GetMsg(port)
        assert msg2

        # got same message
        assert msg == msg2

        # port empty again
        msg3 = exec_lib.GetMsg(port)
        assert msg3 is None

        # delete a message port
        exec_lib.DeleteMsgPort(port)

        msg.free()

        return 0

    exit_codes = vamos_task.run([task])
    assert exit_codes == [0]


def pytask_exec_msg_reply_test(vamos_task):
    def task(ctx, task):
        # get exec library
        exec_lib = ctx.proxies.get_exec_lib_proxy()

        # create a new port
        port = exec_lib.CreateMsgPort()
        assert type(port) is MsgPort

        # port is empty
        msg = exec_lib.GetMsg(port)
        assert msg is None

        # alloc message
        msg = Message.alloc(ctx.alloc)
        assert msg

        # set reply port
        msg.reply_port.ref = port

        # put message to reply port
        exec_lib.ReplyMsg(msg)

        # get message from port
        msg2 = exec_lib.GetMsg(port)
        assert msg2

        # got same message
        assert msg == msg2

        # port empty again
        msg3 = exec_lib.GetMsg(port)
        assert msg3 is None

        # delete a message port
        exec_lib.DeleteMsgPort(port)

        msg.free()

        return 0

    exit_codes = vamos_task.run([task])
    assert exit_codes == [0]


def pytask_exec_msg_signal_test(vamos_task):
    def task(ctx, task):
        # get exec library
        exec_lib = ctx.proxies.get_exec_lib_proxy()

        # create a new port
        port = exec_lib.CreateMsgPort()
        assert type(port) is MsgPort

        # get sigmask
        sig_bit = port.sig_bit.val
        sig_mask = 1 << sig_bit

        # sigmal must be unset
        old_mask = exec_lib.SetSignal(0, 0)
        assert old_mask & sig_mask == 0

        # alloc message
        msg = Message.alloc(ctx.alloc)
        assert msg

        # put a message to port
        exec_lib.PutMsg(port, msg)

        # check for signal
        new_mask = exec_lib.SetSignal(0, 0)
        assert new_mask & sig_mask == sig_mask

        # get message from port
        msg2 = exec_lib.GetMsg(port)
        assert msg2

        # got same message
        assert msg == msg2

        # delete a message port
        exec_lib.DeleteMsgPort(port)

        msg.free()

        return 0

    exit_codes = vamos_task.run([task])
    assert exit_codes == [0]


def pytask_exec_msg_wait_port_test(vamos_task):
    def task(ctx, task):
        # get exec library
        exec_lib = ctx.proxies.get_exec_lib_proxy()

        # create a new port
        port = exec_lib.CreateMsgPort()
        assert type(port) is MsgPort

        # alloc message
        msg = Message.alloc(ctx.alloc)
        assert msg

        # put a message to port
        exec_lib.PutMsg(port, msg)

        # wait port shall return and get our msg
        msg2 = exec_lib.WaitPort(port)

        # got same message
        assert msg == msg2

        # delete a message port
        exec_lib.DeleteMsgPort(port)

        msg.free()

        return 0

    exit_codes = vamos_task.run([task])
    assert exit_codes == [0]


def pytask_exec_msg_add_rem_port_test(vamos_task):
    def task(ctx, task):
        # get exec library
        exec_lib = ctx.proxies.get_exec_lib_proxy()

        # create a new port
        port = exec_lib.CreateMsgPort()
        assert type(port) is MsgPort

        # set name
        port.node.name.alloc_str(ctx.alloc, "foo")

        # port is not known yet
        port2 = exec_lib.FindPort("foo")
        assert port2 is None

        # add port
        exec_lib.AddPort(port)

        # now we could find port
        port2 = exec_lib.FindPort("foo")
        assert port2 == port

        # remove port again
        exec_lib.RemPort(port)

        # now we cannot find it
        port2 = exec_lib.FindPort("foo")
        assert port2 is None

        # free name string
        port.node.name.free_str()

        # delete a message port
        exec_lib.DeleteMsgPort(port)

        return 0

    exit_codes = vamos_task.run([task])
    assert exit_codes == [0]
