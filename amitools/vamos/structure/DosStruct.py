from amitools.vamos.AmigaStruct import AmigaStruct

class ProcessStruct(AmigaStruct):
  _name = "Process"
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
ProcessDef = ProcessStruct()

class CLIStruct(AmigaStruct):
  _name = "CLI"
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
CLIDef = CLIStruct()

class DateStampStruct(AmigaStruct):
  _name = "DateStamp"
  _format = [
    ('LONG','ds_Days'),
    ('LONG','ds_Minute'),
    ('LONG','ds_Tick')
  ]
DateStampDef = DateStampStruct()

class DosInfoStruct(AmigaStruct):
  _name = "DosInfo"
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
DosInfoDef = DosInfoStruct()

class RootNodeStruct(AmigaStruct):
  _name = "RootNode"
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
RootNodeDef = RootNodeStruct()

class DosLibraryStruct(AmigaStruct):
  _name = "Dos"
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
DosLibraryDef = DosLibraryStruct()

class FileInfoBlockStruct(AmigaStruct):
  _name = "FileInfoBlock"
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
FileInfoBlockDef = FileInfoBlockStruct()

class FileHandleStruct(AmigaStruct):
  _name = "FileHandle"
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
FileHandleDef = FileHandleStruct()

class FileLockStruct(AmigaStruct):
  _name = "FileLock"
  _format = [
    ('BPTR','fl_Link'),
    ('LONG','fl_Key'),
    ('LONG','fl_Access'),
    ('void*','fl_Task'),
    ('BPTR','fl_Volume')
  ]
FileLockDef = FileLockStruct()

class DosPacketStruct(AmigaStruct):
  _name = "DosPacket"
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
DosPacketDef = DosPacketStruct()

class AChainStruct(AmigaStruct):
  _name = "AChain"
  _format = [
    ('AChain*','an_Child'),
    ('AChain*','an_Parent'),
    ('BPTR','an_Lock'),
    ('FileInfoBlock','an_Info'),
    ('BYTE','an_Flags'),
    ('UBYTE','an_String')
  ]
AChainDef = AChainStruct()

class AnchorPathStruct(AmigaStruct):
  _name = "AnchorPath"
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
AnchorPathDef = AnchorPathStruct()
