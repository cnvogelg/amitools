from .astructdef import AmigaStructDef
from .astruct import AmigaStruct

@AmigaStructDef
class ProcessStruct(AmigaStruct):
  _format = [
    ('Task','pr_Task'),
    ('MsgPort','pr_MsgPort'),
    # param
    ('WORD','pr_Pad'),
    ('BPTR','pr_SegList'),
    ('LONG','pr_StackSize'),
    ('APTR','pr_GlobVec'),
    ('LONG','pr_TaskNum'),
    ('BPTR','pr_StackBase'),
    ('LONG','pr_Result2'),
    ('BPTR','pr_CurrentDir'),
    ('BPTR','pr_CIS'),
    ('BPTR','pr_COS'),
    ('APTR','pr_ConsoleTask'),
    ('APTR','pr_FileSystemTask'),
    ('BPTR','pr_CLI'),
    ('APTR','pr_ReturnAddr'),
    ('APTR','pr_PktWait'),
    ('APTR','pr_WindowPtr'),
    # 2.0
    ('BPTR','pr_HomeDir'),
    ('LONG','pr_Flags'),
    ('VOIDFUNC','pr_ExitCode'),
    ('LONG','pr_ExitData'),
    ('UBYTE*','pr_Arguments'),
    ('MinList','pr_LocalVars'),
    ('ULONG','pr_ShellPrivate'),
    ('BPTR','pr_CES'),
  ]

@AmigaStructDef
class CLIStruct(AmigaStruct):
  _format = [
    ('LONG','cli_Result2'),
    ('BSTR','cli_SetName'),
    ('BPTR','cli_CommandDir'),
    ('LONG','cli_ReturnCode'),
    ('BSTR','cli_CommandName'),
    ('LONG','cli_FailLevel'),
    ('BSTR','cli_Prompt'),
    ('BPTR','cli_StandardInput'),
    ('BPTR','cli_CurrentInput'),
    ('BSTR','cli_CommandFile'),
    ('LONG','cli_Interactive'),
    ('LONG','cli_Background'),
    ('BPTR','cli_CurrentOutput'),
    ('LONG','cli_DefaultStack'),
    ('BPTR','cli_StandardOutput'),
    ('BPTR','cli_Module'),
  ]

@AmigaStructDef
class DateStampStruct(AmigaStruct):
  _format = [
    ('LONG','ds_Days'),
    ('LONG','ds_Minute'),
    ('LONG','ds_Tick')
  ]

# the union in DosList is splitted up into own types
@AmigaStructDef
class DosListDeviceStruct(AmigaStruct):
  _format = [
    ('BPTR','dol_Next'),
    ('LONG','dol_Type'),
    ('APTR','dol_Task'),
    ('BPTR','dol_Lock'),
    ('BSTR','dol_Handler'),
    ('LONG','dol_StackSize'),
    ('LONG','dol_Priority'),
    ('LONG','dol_Startup'),
    ('BPTR','dol_SegList'),
    ('BPTR','dol_GlobVec'),
    ('BSTR','dol_Name')
  ]

@AmigaStructDef
class DosListVolumeStruct(AmigaStruct):
  _format = [
    ('BPTR','dol_Next'),
    ('LONG','dol_Type'),
    ('APTR','dol_Task'),
    ('BPTR','dol_Lock'),
    ('DateStamp','dol_VolumeDate'),
    ('BPTR','dol_LockList'),
    ('LONG','dol_DiskType'),
    ('LONG','dol_Padding0'),
    ('BSTR','dol_Name')
  ]

@AmigaStructDef
class AssignListStruct(AmigaStruct):
  _format = [
    ('AssignList*','al_Next'),
    ('BPTR','al_Lock')
  ]

@AmigaStructDef
class DosListAssignStruct(AmigaStruct):
  _format = [
    ('BPTR','dol_Next'),
    ('LONG','dol_Type'),
    ('APTR','dol_Task'),
    ('BPTR','dol_Lock'),
    ('UBYTE*','dol_AssignName'),
    ('AssignList*','dol_List'),
    ('LONG|4','dol_Padding'),
    ('BSTR','dol_Name')
  ]

@AmigaStructDef
class DosInfoStruct(AmigaStruct):
  _format = [
    ('BPTR','di_McName'),
    ('BPTR','di_DevInfo'),
    ('BPTR','di_Devices'),
    ('BPTR','di_Handlers'),
    ('BPTR','di_NetHand'),
    ('SignalSemaphore','di_DevLock'),
    ('SignalSemaphore','di_EntryLock'),
    ('SignalSemaphore','di_DeleteLock')
  ]

@AmigaStructDef
class RootNodeStruct(AmigaStruct):
  _format = [
    ('BPTR','rn_TaskArray'),
    ('BPTR','rn_ConsoleSegment'),
    ('DateStamp','rn_Time'),
    ('LONG','rn_RestartSeg'),
    ('BPTR','rn_Info'),
    ('BPTR','rn_FileHandlerSegment'),
    ('MinList','rn_CliList'),
    ('MsgPort*','rn_BootProc'),
    ('BPTR','rn_ShellSegment'),
    ('LONG','rn_Flags')
  ]

@AmigaStructDef
class DosLibraryStruct(AmigaStruct):
  _format = [
    ('Library','lib'),
    ('RootNode*','dl_Root'),
    ('APTR','dl_GV'),
    ('LONG','dl_A2'),
    ('LONG','dl_A5'),
    ('LONG','dl_A6'),
    ('APTR','dl_Errors'),
    ('APTR','dl_TimeReq'),
    ('APTR','dl_UtilityBase'),
    ('APTR','dl_IntuitionBase')
  ]

@AmigaStructDef
class FileInfoBlockStruct(AmigaStruct):
  _format = [
    ('LONG','fib_DiskKey'),
    ('LONG','fib_DirEntryType'),
    ('char|108','fib_FileName'),
    ('LONG','fib_Protection'),
    ('LONG','fib_EntryType'),
    ('LONG','fib_Size'),
    ('LONG','fib_NumBlocks'),
    ('DateStamp','fib_Date'),
    ('char|80','fib_Comment'),
    ('UWORD','fib_OwnerUID'),
    ('UWORD','fib_OwnerGID'),
    ('char|32','fib_Reserved')
  ]

@AmigaStructDef
class FileHandleStruct(AmigaStruct):
  _format = [
    ('void*','fh_Link'),
    ('void*','fh_Port'),
    ('void*','fh_Type'),
    ('LONG','fh_Buf'),
    ('LONG','fh_Pos'),
    ('LONG','fh_End'),
    ('LONG','fh_Funcs'),
    ('LONG','fh_Func2'),
    ('LONG','fh_Func3'),
    ('LONG','fh_Args'),
    ('LONG','fh_Arg2')
  ]

@AmigaStructDef
class FileLockStruct(AmigaStruct):
  _format = [
    ('BPTR','fl_Link'),
    ('LONG','fl_Key'),
    ('LONG','fl_Access'),
    ('void*','fl_Task'),
    ('BPTR','fl_Volume')
  ]

@AmigaStructDef
class DosPacketStruct(AmigaStruct):
  _format = [
    ('Message*','dp_Link'),
    ('MsgPort*','dp_Port'),
    ('LONG','dp_Type'),
    ('LONG','dp_Res1'),
    ('LONG','dp_Res2'),
    ('LONG','dp_Arg1'),
    ('LONG','dp_Arg2'),
    ('LONG','dp_Arg3'),
    ('LONG','dp_Arg4'),
    ('LONG','dp_Arg5'),
    ('LONG','dp_Arg6'),
    ('LONG','dp_Arg7')
  ]

@AmigaStructDef
class AChainStruct(AmigaStruct):
  _format = [
    ('AChain*','an_Child'),
    ('AChain*','an_Parent'),
    ('BPTR','an_Lock'),
    ('FileInfoBlock','an_Info'),
    ('BYTE','an_Flags'),
    ('UBYTE','an_String')
  ]

@AmigaStructDef
class AnchorPathStruct(AmigaStruct):
  _format = [
    ('AChain*','ap_Base'),
    ('AChain*','ap_Last'),
    ('LONG','ap_BreakBits'),
    ('LONG','ap_FoundBreak'),
    ('BYTE','ap_Flags'),
    ('BYTE','ap_Reserved'),
    ('WORD','ap_Strlen'),
    ('FileInfoBlock','ap_Info'),
    ('UBYTE','ap_Buf')
  ]

@AmigaStructDef
class DevProcStruct(AmigaStruct):
  _format = [
    ('MsgPort*','dvp_Port'),
    ('BPTR','dvp_Lock'),
    ('ULONG','dvp_Flags'),
    ('void*','dvp_DevNode')
  ]

@AmigaStructDef
class CSourceStruct(AmigaStruct):
  _format = [
    ('UBYTE*','CS_Buffer'),
    ('LONG','CS_Length'),
    ('LONG','CS_CurChr')
  ]

@AmigaStructDef
class RDArgsStruct(AmigaStruct):
  _format = [
    ('CSource','RDA_Source'),
    ('LONG','RDA_DAList'),
    ('UBYTE*','RDA_Buffer'),
    ('LONG','RDA_BufSiz'),
    ('UBYTE*','RDA_ExtHelp'),
    ('LONG','RDA_Flags')
  ]

@AmigaStructDef
class DateTimeStruct(AmigaStruct):
  _format = [
    ('DateStamp','dat_Stamp'),
    ('UBYTE','dat_Format'),
    ('UBYTE','dat_Flags'),
    ('UBYTE*','dat_StrDay'),
    ('UBYTE*','dat_StrDate'),
    ('UBYTE*','dat_StrTime')
  ]

@AmigaStructDef
class InfoDataStruct(AmigaStruct):
  _format = [
    ('LONG','id_NumSoftErrors'),
    ('LONG','id_UnitNumber'),
    ('LONG','id_DiskState'),
    ('LONG','id_NumBlocks'),
    ('LONG','id_NumBlocksUsed'),
    ('LONG','id_BytesPerBlock'),
    ('LONG','id_DiskType'),
    ('BPTR','id_VolumeNode'),
    ('LONG','id_InUse')
    ]

@AmigaStructDef
class SegmentStruct(AmigaStruct):
  _format = [
    ('BPTR','seg_Next'),
    ('ULONG','seg_UC'),
    ('BPTR','seg_Seg'),
    ('UBYTE','seg_Name')
    ]

@AmigaStructDef
class LocalVarStruct(AmigaStruct):
  _format = [
    ('Node','lv_Node'),
    ('UWORD','lv_Flags'),
    ('UBYTE*','lv_Value'),
    ('ULONG','lv_Len')
  ]

@AmigaStructDef
class PathStruct(AmigaStruct):
  _format = [
    ('BPTR','path_Next'),
    ('BPTR','path_Lock')
  ]
