from amitools.vamos.AmigaStruct import AmigaStruct

# Node
class NodeStruct(AmigaStruct):
  _name = "Node"
  _format = [
    ('Node*','ln_Succ'),
    ('Node*','ln_Pred'),
    ('UBYTE','ln_Type'),
    ('BYTE','ln_Pri'),
    ('char*','ln_Name')
  ]
NodeDef = NodeStruct()

# MinNode
class MinNodeStruct(AmigaStruct):
  _name = "MinNode"
  _format = [
    ('MinNode*','mln_Succ'),
    ('MinNode*','mln_Pred')
  ]
MinNodeDef = MinNodeStruct()

# Library
class LibraryStruct(AmigaStruct):
  _name = "Library"
  _format = [
    ('Node','lib_Node'),
    ('UBYTE','lib_Flags'),
    ('UBYTE','lib_pad'),
    ('UWORD','lib_NegSize'),
    ('UWORD','lib_PosSize'),
    ('UWORD','lib_Version'),
    ('UWORD','lib_Revision'),
    ('APTR','lib_ldString'),
    ('ULONG','lib_Sum'),
    ('UWORD','lib_OpenCnt')
  ]
LibraryDef = LibraryStruct()

# List
class ListStruct(AmigaStruct):
  _name = "List"
  _format = [
    ('Node*','lh_Head'),
    ('Node*','lh_Tail'),
    ('Node*','lh_TailPref'),
    ('UBYTE','lh_Type'),
    ('UBYTE','l_pad')
  ]
ListDef = ListStruct()

# MinList
class MinListStruct(AmigaStruct):
  _name = "MinList"
  _format = [
    ('MinNode*','mlh_Head'),
    ('MinNode*','mlh_Tail'),
    ('MinNode*','mlh_TailPred')
  ]
MinListDef = MinListStruct()

# MsgPort
class MsgPortStruct(AmigaStruct):
  _name = "MsgPort"
  _format = [
    ('Node','mp_Node'),
    ('UBYTE','mp_Flags'),
    ('UBYTE','mp_SigBit'),
    ('void*','mp_SigTask'),
    ('List','mp_MsgList')
  ]
MsgPortDef = MsgPortStruct()

# IntVector
class IntVectorStruct(AmigaStruct):
  _name = "IntVector"
  _format = [
    ('APTR','iv_Data'),
    ('VOIDFUNC','iv_Code'),
    ('Node*','iv_Node')
  ]
IntVectorDef = IntVectorStruct()

# SoftIntList
class SoftIntListStruct(AmigaStruct):
  _name = "SoftIntList"
  _format = [
    ('List','sh_List'),
    ('UWORD','sh_Pad')
  ]
SoftIntListDef = SoftIntListStruct()

# Task
class TaskStruct(AmigaStruct):
  _name = "Task"
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
TaskDef = TaskStruct()

class ExecLibraryStruct(AmigaStruct):
  _name = "ExecLibrary"
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
ExecLibraryDef = ExecLibraryStruct()
