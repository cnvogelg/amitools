"""dos.library local/global variables (RKRM AmigaDOS 3, "Variables").

``GetVar``/``SetVar``/``DeleteVar``/``FindVar`` read and write shell variables.
Local variables live in the current process's ``pr_LocalVars`` list and are
also tracked in ``DosLibrary.local_vars``; global variables live only in
``DosLibrary.global_vars``. ``SetVar``/``DeleteVar`` with the ``GVF_GLOBAL_ONLY``
flag operate on the global table, otherwise a local variable is preferred.
"""

from amitools.vamos.libstructs import LocalVarStruct, NodeStruct
from amitools.vamos.log import log_dos

from .Error import DOSTRUE, DOSFALSE, ERROR_BAD_NUMBER, ERROR_OBJECT_NOT_FOUND

GVF_GLOBAL_ONLY = 0x100
GVF_LOCAL_ONLY = 0x200
GVF_BINARY_VAR = 0x400


# ----- local variable list helpers -----


def find_var_node(dos, ctx, name, flags):
    if (name.lower(), flags & 0xFF) in dos.local_vars:
        return dos.local_vars[(name.lower(), flags & 0xFF)]
    return None


def create_var_node(dos, ctx, name, flags):
    varlist = ctx.process.get_local_vars()
    varlist_struct = varlist
    node_addr = dos._alloc_mem(
        "ShellVar(%s)" % name, LocalVarStruct.get_size() + len(name) + 1
    )
    name_addr = node_addr + LocalVarStruct.get_size()
    node = LocalVarStruct(ctx.mem, node_addr)
    ctx.mem.w_cstr(name_addr, name)
    node.lv_Node.ln_Name.aptr = name_addr
    node.lv_Node.ln_Type.val = flags & 0xFF
    node.lv_Value.aptr = 0
    head_addr = varlist_struct.mlh_Head.aptr
    head = NodeStruct(ctx.mem, head_addr)
    head.ln_Pred.aptr = node_addr
    varlist_struct.mlh_Head.aptr = node_addr
    node.lv_Node.ln_Succ.aptr = head_addr
    node.lv_Node.ln_Pred.aptr = varlist_struct.mlh_Head.addr
    dos.local_vars[(name.lower(), flags & 0xFF)] = node
    return node


def set_var_node(dos, ctx, node, buff_ptr, size, value, flags):
    if node.lv_Value.aptr != 0:
        dos._free_mem(node.lv_Value.aptr)
        node.lv_Value.aptr = 0
    buf_addr = dos._alloc_mem("ShellVarBuffer", size)
    node.lv_Value.aptr = buf_addr
    node.lv_Len.val = size
    if flags & GVF_BINARY_VAR:
        ctx.mem.copy_block(buff_ptr, buf_addr, size)
    else:
        ctx.mem.w_cstr(buf_addr, value)


def delete_var_node(dos, ctx, node):
    buf_addr = node.lv_Value.aptr
    if buf_addr != 0:
        dos._free_mem(buf_addr)
    node.lv_Value.aptr = 0
    succ = node.lv_Node.ln_Succ.aptr
    pred = node.lv_Node.ln_Pred.aptr
    NodeStruct(ctx.mem, pred).ln_Succ.aptr = succ
    NodeStruct(ctx.mem, succ).ln_Pred.aptr = pred
    dos._free_mem(node.addr)
    for k in list(dos.local_vars.keys()):
        if dos.local_vars[k] == node:
            del dos.local_vars[k]


# ----- fd functions -----


def get_var(dos, ctx, name_ptr, buff_ptr, size, flags):
    if size == 0:
        dos.setioerr(ctx, ERROR_BAD_NUMBER)
        return -1
    name = ctx.mem.r_cstr(name_ptr)
    if not flags & GVF_GLOBAL_ONLY:
        node = find_var_node(dos, ctx, name, flags & 0xFF)
        if node is not None:
            nodelen = node.lv_Len.val
            if flags & GVF_BINARY_VAR:
                ctx.mem.copy_block(node.lv_Value.aptr, buff_ptr, min(nodelen, size))
                log_dos.info(
                    'GetVar("%s", 0x%x) -> %0x06x', name, flags, node.lv_Value.aptr
                )
                dos.setioerr(ctx, nodelen)
                return min(nodelen, size)
            else:
                value = ctx.mem.r_cstr(node.lv_Value.aptr)
                ctx.mem.w_cstr(buff_ptr, value[: size - 1])
                log_dos.info('GetVar("%s", 0x%x) -> %s', name, flags, value)
                dos.setioerr(ctx, len(value))
                return min(nodelen - 1, size - 1)
    # no local variable. unless we were asked for local only, fall back
    # to the global ones, which is the order AmigaOS looks them up in
    if not flags & GVF_LOCAL_ONLY:
        value = dos.global_vars.get((name.lower(), flags & 0xFF))
        if value is not None:
            if flags & GVF_BINARY_VAR:
                ctx.mem.write_data(buff_ptr, value[:size])
                log_dos.info('GetVar("%s", 0x%x) -> <global binary>', name, flags)
                dos.setioerr(ctx, len(value))
                return min(len(value), size)
            ctx.mem.w_cstr(buff_ptr, value[: size - 1])
            log_dos.info('GetVar("%s", 0x%x) -> %s (global)', name, flags, value)
            dos.setioerr(ctx, len(value))
            return min(len(value), size - 1)
    dos.setioerr(ctx, ERROR_OBJECT_NOT_FOUND)
    return -1


def find_var(dos, ctx, name_ptr, vtype):
    name = ctx.mem.r_cstr(name_ptr)
    node = find_var_node(dos, ctx, name, vtype)
    if node is None:
        dos.setioerr(ctx, ERROR_OBJECT_NOT_FOUND)
        log_dos.info('FindVar("%s", 0x%x) -> NULL', name, vtype)
        return 0
    log_dos.info('FindVar("%s", 0x%x) -> %06lx', name, vtype, node.addr)
    return node.addr


def set_var(dos, ctx, name_ptr, buff_ptr, size, flags):
    name = ctx.mem.r_cstr(name_ptr)
    vtype = flags & 0xFF
    if buff_ptr == 0:
        if flags & GVF_GLOBAL_ONLY:
            dos.global_vars.pop((name.lower(), vtype), None)
            return DOSTRUE
        node = find_var_node(dos, ctx, name, vtype)
        if node is not None:
            delete_var_node(dos, ctx, node)
        return DOSTRUE
    else:
        if flags & GVF_BINARY_VAR:
            value = None
            log_dos.info('SetVar("%s") to %0x6x', name, buff_ptr)
        else:
            value = ctx.mem.r_cstr(buff_ptr)
            log_dos.info('SetVar("%s") to %s', name, value)
            size = len(value) + 1
        if flags & GVF_GLOBAL_ONLY:
            if flags & GVF_BINARY_VAR:
                value = ctx.mem.read_data(buff_ptr, size)
            dos.global_vars[(name.lower(), vtype)] = value
            return DOSTRUE
        node = find_var_node(dos, ctx, name, flags)
        if node is None and buff_ptr != 0:
            node = create_var_node(dos, ctx, name, flags)
        if node is not None:
            set_var_node(dos, ctx, node, buff_ptr, size, value, flags)
        return DOSTRUE


def delete_var(dos, ctx, name_ptr, flags):
    name = ctx.mem.r_cstr(name_ptr)
    if flags & GVF_GLOBAL_ONLY:
        found = dos.global_vars.pop((name.lower(), flags & 0xFF), None)
        log_dos.info('DeleteVar("%s") global', name)
        return DOSTRUE if found is not None else DOSFALSE
    node = find_var_node(dos, ctx, name, flags)
    log_dos.info('DeleteVar("%s")', name)
    if node is not None:
        delete_var_node(dos, ctx, node)
    return DOSTRUE
