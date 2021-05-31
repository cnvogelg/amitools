from amitools.vamos.astructs import (
    AmigaStructDef,
    AmigaStruct,
    EnumType,
    Enum,
    BitFieldType,
    BitField,
    APTR_SELF,
    APTR_VOID,
    APTR,
    UBYTE,
    BYTE,
    UWORD,
    WORD,
    ULONG,
    LONG,
    CSTR,
    ARRAY,
)


@EnumType
class NodeType(Enum, UBYTE):
    """manage valid node type constants and conversions"""

    NT_UNKNOWN = 0
    NT_TASK = 1
    NT_INTERRUPT = 2
    NT_DEVICE = 3
    NT_MSGPORT = 4
    NT_MESSAGE = 5
    NT_FREEMSG = 6
    NT_REPLYMSG = 7
    NT_RESOURCE = 8
    NT_LIBRARY = 9
    NT_MEMORY = 10
    NT_SOFTINT = 11
    NT_FONT = 12
    NT_PROCESS = 13
    NT_SEMAPHORE = 14
    NT_SIGNALSEM = 15
    NT_BOOTNODE = 16
    NT_KICKMEM = 17
    NT_GRAPHICS = 18
    NT_DEATHMESSAGE = 19

    NT_USER = 254
    NT_EXTENDED = 255


# Node
@AmigaStructDef
class NodeStruct(AmigaStruct):
    _format = [
        (APTR_SELF, "ln_Succ"),
        (APTR_SELF, "ln_Pred"),
        (NodeType, "ln_Type"),
        (BYTE, "ln_Pri"),
        (CSTR, "ln_Name"),
    ]


# MinNode
@AmigaStructDef
class MinNodeStruct(AmigaStruct):
    _format = [(APTR_SELF, "mln_Succ"), (APTR_SELF, "mln_Pred")]


@BitFieldType
class LibFlags(BitField, UBYTE):
    LIBF_SUMMING = 1 << 0
    LIBF_CHANGED = 1 << 1
    LIBF_SUMUSED = 1 << 2
    LIBF_DELEXP = 1 << 3


# Library
@AmigaStructDef
class LibraryStruct(AmigaStruct):
    _format = [
        (NodeStruct, "lib_Node"),
        (LibFlags, "lib_Flags"),
        (UBYTE, "lib_pad"),
        (UWORD, "lib_NegSize"),
        (UWORD, "lib_PosSize"),
        (UWORD, "lib_Version"),
        (UWORD, "lib_Revision"),
        (CSTR, "lib_IdString"),
        (ULONG, "lib_Sum"),
        (UWORD, "lib_OpenCnt"),
    ]
    _subfield_aliases = {
        "name": "lib_Node.ln_Name",
        "type": "lib_Node.ln_Type",
        "pri": "lib_Node.ln_Pri",
    }


# List
@AmigaStructDef
class ListStruct(AmigaStruct):
    _format = [
        (APTR(NodeStruct), "lh_Head"),
        (APTR(NodeStruct), "lh_Tail"),
        (APTR(NodeStruct), "lh_TailPred"),
        (NodeType, "lh_Type"),
        (UBYTE, "l_pad"),
    ]


# MinList
@AmigaStructDef
class MinListStruct(AmigaStruct):
    _format = [
        (APTR(MinNodeStruct), "mlh_Head"),
        (APTR(MinNodeStruct), "mlh_Tail"),
        (APTR(MinNodeStruct), "mlh_TailPred"),
    ]


@EnumType
class MsgPortFlags(Enum, UBYTE):
    PA_SIGNAL = 0
    PA_SOFTINT = 1
    PA_IGNORE = 2


# MsgPort
@AmigaStructDef
class MsgPortStruct(AmigaStruct):
    _format = [
        (NodeStruct, "mp_Node"),
        (MsgPortFlags, "mp_Flags"),
        (UBYTE, "mp_SigBit"),
        (APTR_VOID, "mp_SigTask"),
        (ListStruct, "mp_MsgList"),
    ]
    _subfield_aliases = {
        "name": "mp_Node.ln_Name",
        "type": "mp_Node.ln_Type",
        "pri": "mp_Node.ln_Pri",
    }


# Message
@AmigaStructDef
class MessageStruct(AmigaStruct):
    _format = [
        (NodeStruct, "mn_Node"),
        (APTR(MsgPortStruct), "mn_ReplyPort"),
        (UWORD, "mn_Length"),
    ]
    _subfield_aliases = {
        "name": "mn_Node.ln_Name",
        "type": "mn_Node.ln_Type",
        "pri": "mn_Node.ln_Pri",
    }


# IntVector
@AmigaStructDef
class IntVectorStruct(AmigaStruct):
    _format = [
        (APTR_VOID, "iv_Data"),
        (APTR_VOID, "iv_Code"),
        (APTR(NodeStruct), "iv_Node"),
    ]


# SoftIntList
@AmigaStructDef
class SoftIntListStruct(AmigaStruct):
    _format = [(ListStruct, "sh_List"), (UWORD, "sh_Pad")]


@BitFieldType
class TaskFlags(BitField, UBYTE):
    TF_PROCTIME = 1 << 0
    TF_ETASK = 1 << 3
    TF_STACKCHK = 1 << 4
    TF_EXCEPT = 1 << 5
    TF_SWITCH = 1 << 6
    TF_LAUNCH = 1 << 7


@EnumType
class TaskState(Enum, UBYTE):
    TS_INVALID = 0
    TS_ADDED = 1
    TS_RUN = 2
    TS_READY = 3
    TS_WAIT = 4
    TS_EXCEPT = 5
    TS_REMOVED = 6


# Task
@AmigaStructDef
class TaskStruct(AmigaStruct):
    _format = [
        (NodeStruct, "tc_Node"),
        (TaskFlags, "tc_Flags"),
        (TaskState, "tc_State"),
        (BYTE, "tc_IDNestCnt"),
        (BYTE, "tc_TDNestCnt"),
        (ULONG, "tc_SigAlloc"),
        (ULONG, "tc_SigWait"),
        (ULONG, "tc_SigRecvd"),
        (ULONG, "tc_SigExcept"),
        (UWORD, "tc_TrapAlloc"),
        (UWORD, "tc_TrapAble"),
        (APTR_VOID, "tc_ExceptData"),
        (APTR_VOID, "tc_ExceptCode"),
        (APTR_VOID, "tc_TrapData"),
        (APTR_VOID, "tc_TrapCode"),
        (APTR_VOID, "tc_SPReg"),
        (APTR_VOID, "tc_SPLower"),
        (APTR_VOID, "tc_SPUpper"),
        (APTR_VOID, "tc_Switch"),
        (APTR_VOID, "tc_Launch"),
        (ListStruct, "tc_MemEntry"),
        (APTR_VOID, "tc_UserData"),
    ]
    _subfield_aliases = {
        "name": "tc_Node.ln_Name",
        "type": "tc_Node.ln_Type",
        "pri": "tc_Node.ln_Pri",
    }


@BitFieldType
class AttnFlags(BitField, UWORD):
    AFF_68010 = 1 << 0
    AFF_68020 = 1 << 1
    AFF_68030 = 1 << 2
    AFF_68040 = 1 << 3
    AFF_68881 = 1 << 4
    AFF_68882 = 1 << 5
    AFF_FPU40 = 1 << 6
    AFF_68060 = 1 << 7


@AmigaStructDef
class ExecLibraryStruct(AmigaStruct):
    _format = [
        (LibraryStruct, "LibNode"),
        # Static System Variables
        (UWORD, "SoftVer"),
        (WORD, "LowMemChkSum"),
        (ULONG, "ChkBase"),
        (APTR_VOID, "ColdCapture"),
        (APTR_VOID, "CoolCapture"),
        (APTR_VOID, "WarmCapture"),
        (APTR_VOID, "SysStkUpper"),
        (APTR_VOID, "SysStkLower"),
        (ULONG, "MaxLocMem"),
        (APTR_VOID, "DebugEntry"),
        (APTR_VOID, "DebugData"),
        (APTR_VOID, "AlertData"),
        (APTR_VOID, "MaxExtMem"),
        (UWORD, "ChkSum"),
        # Interrupt Related
        (ARRAY(IntVectorStruct, 16), "IntVects"),
        # Dynamic System Variables
        (APTR(TaskStruct), "ThisTask"),
        (ULONG, "IdleCount"),
        (ULONG, "DispCount"),
        (UWORD, "Quantum"),
        (UWORD, "Elapsed"),
        (UWORD, "SysFlags"),
        (BYTE, "IDNestCnt"),
        (BYTE, "TDNestCnt"),
        (AttnFlags, "AttnFlags"),
        (UWORD, "AttnResched"),
        (APTR_VOID, "ResModules"),
        (APTR_VOID, "TaskTrapCode"),
        (APTR_VOID, "TaskExceptCode"),
        (APTR_VOID, "TaskExitCode"),
        (ULONG, "TaskSigAlloc"),
        (UWORD, "TaskTrapAlloc"),
        # System Lists (private!)
        (ListStruct, "MemList"),
        (ListStruct, "ResourceList"),
        (ListStruct, "DeviceList"),
        (ListStruct, "IntrList"),
        (ListStruct, "LibList"),
        (ListStruct, "PortList"),
        (ListStruct, "TaskReady"),
        (ListStruct, "TaskWait"),
        (ARRAY(SoftIntListStruct, 5), "SoftIntList"),
        # Other Globals
        (ARRAY(ULONG, 4), "LastAlert"),
        (UBYTE, "VBlankFrequency"),
        (UBYTE, "PowerSupplyFrequency"),
        (ListStruct, "SemaphoreList"),
        (APTR_VOID, "KickMemPtr"),
        (APTR_VOID, "KickTagPtr"),
        (APTR_VOID, "KickCheckSum"),
        # V36 Additions
        (ULONG, "ex_Pad0"),
        (ULONG, "ex_LaunchPoint"),
        (APTR_VOID, "ex_RamLibPrivate"),
        (ULONG, "ex_EClockFrequency"),
        (ULONG, "ex_CacheControl"),
        (ULONG, "ex_TaskID"),
        (ARRAY(ULONG, 5), "ex_Reserved1"),
        (APTR_VOID, "ex_MMULock"),
        (ARRAY(ULONG, 3), "ex_Reserved2"),
        # V39 Additions
        (MinListStruct, "ex_MemHandlers"),
        (APTR_VOID, "ex_MemHandler"),
    ]
    _subfield_aliases = {
        "name": "LibNode.lib_Node.ln_Name",
        "type": "LibNode.lib_Node.ln_Type",
        "pri": "LibNode.lib_Node.ln_Pri",
        "id_string": "LibNode.lib_IdString",
        "pos_size": "LibNode.lib_PosSize",
        "neg_size": "LibNode.lib_NegSize",
    }


# StackSwap
@AmigaStructDef
class StackSwapStruct(AmigaStruct):
    _format = [
        (APTR_VOID, "stk_Lower"),
        (ULONG, "stk_Upper"),
        (APTR_VOID, "stk_Pointer"),
    ]


# Semaphores
@AmigaStructDef
class SemaphoreRequestStruct(AmigaStruct):
    _format = [(MinNodeStruct, "sr_Link"), (APTR(TaskStruct), "sr_Waiter")]


@AmigaStructDef
class SignalSemaphoreStruct(AmigaStruct):
    _format = [
        (NodeStruct, "ss_Link"),
        (WORD, "ss_NestCount"),
        (MinListStruct, "ss_WaitQueue"),
        (SemaphoreRequestStruct, "ss_MultipleLink"),
        (APTR(TaskStruct), "ss_Owner"),
        (WORD, "ss_QueueCount"),
    ]


# Device
@AmigaStructDef
class DeviceStruct(AmigaStruct):
    _format = [(LibraryStruct, "dd_Library")]


# Unit
@AmigaStructDef
class UnitStruct(AmigaStruct):
    _format = [
        (MsgPortStruct, "unit_MsgPort"),
        (UBYTE, "unit_flags"),
        (UBYTE, "unit_pad"),
        (UWORD, "unit_OpenCnt"),
    ]


# IORequests
@AmigaStructDef
class IORequestStruct(AmigaStruct):
    _format = [
        (MessageStruct, "io_Message"),
        (APTR(DeviceStruct), "io_Device"),
        (UnitStruct, "io_Unit"),
        (UWORD, "io_Command"),
        (UBYTE, "io_Flags"),
        (BYTE, "io_Error"),
        (ULONG, "io_Actual"),
        (ULONG, "io_Length"),
        (ULONG, "io_Data"),
        (ULONG, "io_Offset"),
    ]


# MemChunk
@AmigaStructDef
class MemChunkStruct(AmigaStruct):
    _format = [(APTR_SELF, "mc_Next"), (ULONG, "mc_Bytes")]


# MemHeader
@AmigaStructDef
class MemHeaderStruct(AmigaStruct):
    _format = [
        (NodeStruct, "mh_Node"),
        (UWORD, "mh_Attributes"),
        (APTR(MemChunkStruct), "mh_First"),
        (APTR_VOID, "mh_Lower"),
        (APTR_VOID, "mh_Upper"),
        (ULONG, "mh_Free"),
    ]


@BitFieldType
class ResidentFlags(BitField, UBYTE):
    RTF_AUTOINIT = 1 << 7
    RTF_AFTERDOS = 1 << 2
    RTF_SINGLETASK = 1 << 1
    RTF_COLDSTART = 1 << 0


# AutoInit used in Residents
@AmigaStructDef
class AutoInitStruct(AmigaStruct):
    _format = [
        (ULONG, "ai_PosSize"),
        (APTR_VOID, "ai_Functions"),
        (APTR_VOID, "ai_InitStruct"),
        (APTR_VOID, "ai_InitFunc"),
    ]


# Resident
@AmigaStructDef
class ResidentStruct(AmigaStruct):
    _format = [
        (UWORD, "rt_MatchWord"),
        (APTR_VOID, "rt_MatchTag"),
        (APTR_VOID, "rt_EndSkip"),
        (ResidentFlags, "rt_Flags"),
        (UBYTE, "rt_Version"),
        (UBYTE, "rt_Type"),
        (BYTE, "rt_Pri"),
        (CSTR, "rt_Name"),
        (CSTR, "rt_IdString"),
        (APTR(AutoInitStruct), "rt_Init"),
    ]
