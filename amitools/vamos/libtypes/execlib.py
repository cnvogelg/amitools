from amitools.vamos.libstructs import ExecLibraryStruct, NodeType
from .library import Library, LibBase
from amitools.vamos.astructs import AmigaClassDef


@AmigaClassDef
class ExecLibrary(LibBase, ExecLibraryStruct):
    def new_lib(self, version=0, revision=0, attn_flags=0, max_loc_mem=0):
        self.lib_node.new_lib(version, revision)
        self.attn_flags.val = attn_flags
        self.max_loc_mem.val = max_loc_mem
        # init lists
        self.mem_list.new_list(NodeType.NT_MEMORY)
        self.resource_list.new_list(NodeType.NT_RESOURCE)
        self.device_list.new_list(NodeType.NT_DEVICE)
        self.intr_list.new_list(NodeType.NT_INTERRUPT)
        self.lib_list.new_list(NodeType.NT_LIBRARY)
        self.port_list.new_list(NodeType.NT_MSGPORT)
        self.task_ready.new_list(NodeType.NT_TASK)
        self.task_wait.new_list(NodeType.NT_TASK)
        self.semaphore_list.new_list(NodeType.NT_SEMAPHORE)
        self.mem_handlers.new_list()

    def fill_funcs(self, opcode=None, param=None):
        self.lib_node.fill_funcs(opcode, param)
