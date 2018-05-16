from .astructdef import AmigaStructDef
from .astruct import AmigaStruct

# Node
@AmigaStructDef
class NodeStruct(AmigaStruct):
  _format = [
    ('Node*','ln_Succ'),
    ('Node*','ln_Pred'),
    ('UBYTE','ln_Type'),
    ('BYTE','ln_Pri'),
    ('char*','ln_Name')
  ]

# MinNode
@AmigaStructDef
class MinNodeStruct(AmigaStruct):
  _format = [
    ('MinNode*','mln_Succ'),
    ('MinNode*','mln_Pred')
  ]

# Library
@AmigaStructDef
class LibraryStruct(AmigaStruct):
  _format = [
    ('Node','lib_Node'),
    ('UBYTE','lib_Flags'),
    ('UBYTE','lib_pad'),
    ('UWORD','lib_NegSize'),
    ('UWORD','lib_PosSize'),
    ('UWORD','lib_Version'),
    ('UWORD','lib_Revision'),
    ('char*','lib_IdString'),
    ('ULONG','lib_Sum'),
    ('UWORD','lib_OpenCnt')
  ]

# List
@AmigaStructDef
class ListStruct(AmigaStruct):
  _format = [
    ('Node*','lh_Head'),
    ('Node*','lh_Tail'),
    ('Node*','lh_TailPred'),
    ('UBYTE','lh_Type'),
    ('UBYTE','l_pad')
  ]

# MinList
@AmigaStructDef
class MinListStruct(AmigaStruct):
  _format = [
    ('MinNode*','mlh_Head'),
    ('MinNode*','mlh_Tail'),
    ('MinNode*','mlh_TailPred')
  ]

# MsgPort
@AmigaStructDef
class MsgPortStruct(AmigaStruct):
  _format = [
    ('Node','mp_Node'),
    ('UBYTE','mp_Flags'),
    ('UBYTE','mp_SigBit'),
    ('void*','mp_SigTask'),
    ('List','mp_MsgList')
  ]

# Message
@AmigaStructDef
class MessageStruct(AmigaStruct):
  _format = [
    ('Node','mn_Node'),
    ('MsgPort*','mn_ReplyPort'),
    ('UWORD','mn_Length')
  ]

# IntVector
@AmigaStructDef
class IntVectorStruct(AmigaStruct):
  _format = [
    ('APTR','iv_Data'),
    ('VOIDFUNC','iv_Code'),
    ('Node*','iv_Node')
  ]

# SoftIntList
@AmigaStructDef
class SoftIntListStruct(AmigaStruct):
  _format = [
    ('List','sh_List'),
    ('UWORD','sh_Pad')
  ]

# Task
@AmigaStructDef
class TaskStruct(AmigaStruct):
  _format = [
    ('Node','tc_Node'),
    ('UBYTE','tc_Flags'),
    ('UBYTE','tc_State'),
    ('BYTE','tc_IDNestCnt'),
    ('BYTE','tc_TDNestCnt'),
    ('ULONG','tc_SigAlloc'),
    ('ULONG','tc_SigWait'),
    ('ULONG','tc_SigRecvd'),
    ('ULONG','tc_SigExcept'),
    ('UWORD','tc_TrapAlloc'),
    ('UWORD','tc_TrapAble'),
    ('APTR','tc_ExceptData'),
    ('APTR','tc_ExceptCode'),
    ('APTR','tc_TrapData'),
    ('APTR','tc_TrapCode'),
    ('APTR','tc_SPReg'),
    ('APTR','tc_SPLower'),
    ('APTR','tc_SPUpper'),
    ('VOIDFUNC','tc_Switch'),
    ('VOIDFUNC','tc_Launch'),
    ('List','tc_MemEntry'),
    ('APTR','tc_UserData')
  ]

@AmigaStructDef
class ExecLibraryStruct(AmigaStruct):
  _format = [
    ('Library','LibNode'),
    # Static System Variables
    ('UWORD','SoftVer'),
    ('WORD','LowMemChkSum'),
    ('ULONG','ChkBase'),
    ('APTR','ColdCapture'),
    ('APTR','CoolCapture'),
    ('APTR','WarmCapture'),
    ('APTR','SysStkUpper'),
    ('APTR','SysStkLower'),
    ('ULONG','MaxLocMem'),
    ('APTR','DebugEntry'),
    ('APTR','DebugData'),
    ('APTR','AlertData'),
    ('APTR','MaxExtMem'),
    ('UWORD','ChkSum'),
    # Interrupt Related
    ('IntVector|16','IntVects'),
    # Dynamic System Variables
    ('Task*','ThisTask'),
    ('ULONG','IdleCount'),
    ('ULONG','DispCount'),
    ('UWORD','Quantum'),
    ('UWORD','Elapsed'),
    ('UWORD','SysFlags'),
    ('BYTE','IDNestCnt'),
    ('BYTE','TDNestCnt'),
    ('UWORD','AttnFlags'),
    ('UWORD','AttnResched'),
    ('APTR','ResModules'),
    ('APTR','TaskTrapCode'),
    ('APTR','TaskExceptCode'),
    ('APTR','TaskExitCode'),
    ('ULONG','TaskSigAlloc'),
    ('UWORD','TaskTrapAlloc'),
    # System Lists (private!)
    ('List','MemList'),
    ('List','ResourceList'),
    ('List','DeviceList'),
    ('List','IntrList'),
    ('List','LibList'),
    ('List','PortList'),
    ('List','TaskReady'),
    ('List','TaskWait'),
    ('SoftIntList|5','SoftIntList'),
    # Other Globals
    ('LONG|4','LastAlert'),
    ('UBYTE','VBlankFrequency'),
    ('UBYTE','PowerSupplyFrequency'),
    ('List','SemaphoreList'),
    ('APTR','KickMemPtr'),
    ('APTR','KickTagPtr'),
    ('APTR','KickCheckSum'),
    # V36 Additions
    ('ULONG','ex_Pad0'),
    ('ULONG','ex_LaunchPoint'),
    ('APTR','ex_RamLibPrivate'),
    ('ULONG','ex_EClockFrequency'),
    ('ULONG','ex_CacheControl'),
    ('ULONG','ex_TaskID'),
    ('ULONG|5','ex_Reserved1'),
    ('APTR','ex_MMULock'),
    ('ULONG|3','ex_Reserved2'),
    # V39 Additions
    ('MinList','ex_MemHandlers'),
    ('APTR','ex_MemHandler')
  ]

# StackSwap
@AmigaStructDef
class StackSwapStruct(AmigaStruct):
  _format = [
    ('APTR', 'stk_Lower'),
    ('ULONG', 'stk_Upper'),
    ('APTR', 'stk_Pointer')
  ]

# Semaphores
@AmigaStructDef
class SemaphoreRequestStruct(AmigaStruct):
  _format = [
    ('MinNode','sr_Link'),
    ('Task*','sr_Waiter')
  ]

@AmigaStructDef
class SignalSemaphoreStruct(AmigaStruct):
  _format = [
    ('Node','ss_Link'),
    ('WORD','ss_NestCount'),
    ('MinList','ss_WaitQueue'),
    ('SemaphoreRequest','ss_MultipleLink'),
    ('Task*','ss_Owner'),
    ('WORD','ss_QueueCount')
  ]

# Device
@AmigaStructDef
class DeviceStruct(AmigaStruct):
  _format = [
    ('Library','dd_Library')
  ]

# Unit
@AmigaStructDef
class UnitStruct(AmigaStruct):
  _format = [
    ('MsgPort','unit_MsgPort'),
    ('UBYTE','unit_flags'),
    ('UBYTE','unit_pad'),
    ('UWORD','unit_OpenCnt')
  ]

# IORequests
@AmigaStructDef
class IORequestStruct(AmigaStruct):
  _format = [
    ('Message','io_Message'),
    ('Device*','io_Device'),
    ('Unit','io_Unit'),
    ('UWORD','io_Command'),
    ('UBYTE','io_Flags'),
    ('BYTE','io_Error'),
    ('ULONG','io_Actual'),
    ('ULONG','io_Length'),
    ('ULONG','io_Data'),
    ('ULONG','io_Offset')
  ]

# MemChunk
@AmigaStructDef
class MemChunkStruct(AmigaStruct):
  _format = [
    ('MemChunk*', 'mc_Next'),
    ('ULONG', 'mc_Bytes')
  ]

# MemHeader
@AmigaStructDef
class MemHeaderStruct(AmigaStruct):
  _format = [
    ('Node', 'mh_Node'),
    ('UWORD', 'mh_Attributes'),
    ('MemChunk*', 'mh_First'),
    ('APTR', 'mh_Lower'),
    ('APTR', 'mh_Upper'),
    ('ULONG', 'mh_Free')
  ]

# Resident
@AmigaStructDef
class ResidentStruct(AmigaStruct):
  _format = [
    ('UWORD', 'rt_MatchWord'),
    ('APTR', 'rt_MatchTag'),
    ('APTR', 'rt_EndSkip'),
    ('UBYTE', 'rt_Flags'),
    ('UBYTE', 'rt_Version'),
    ('UBYTE', 'rt_Type'),
    ('BYTE', 'rt_Pri'),
    ('char*', 'rt_Name'),
    ('char*', 'rt_IdString'),
    ('APTR', 'rt_Init')
  ]

# AutoInit used in Residents
@AmigaStructDef
class AutoInitStruct(AmigaStruct):
  _format = [
    ('ULONG', 'ai_PosSize'),
    ('APTR', 'ai_Functions'),
    ('APTR', 'ai_InitStruct'),
    ('APTR', 'ai_InitFunc')
  ]

