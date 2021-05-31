from amitools.vamos.astructs import (
    AmigaStruct,
    AmigaStructDef,
    BPTR,
    BPTR_SELF,
    BPTR_VOID,
    APTR,
    APTR_VOID,
    APTR_SELF,
    UBYTE,
    BYTE,
    UWORD,
    WORD,
    ULONG,
    LONG,
    BSTR,
    CSTR,
    ARRAY,
)
from .exec_ import (
    TaskStruct,
    MsgPortStruct,
    MinListStruct,
    NodeStruct,
    SignalSemaphoreStruct,
    LibraryStruct,
    MessageStruct,
)


@AmigaStructDef
class FileLockStruct(AmigaStruct):
    _format = [
        (BPTR_SELF, "fl_Link"),
        (ULONG, "fl_Key"),
        (LONG, "fl_Access"),
        (APTR_VOID, "fl_Task"),
        (BPTR_VOID, "fl_Volume"),
    ]


@AmigaStructDef
class FileHandleStruct(AmigaStruct):
    _format = [
        (APTR_VOID, "fh_Link"),
        (APTR_VOID, "fh_Port"),
        (APTR_VOID, "fh_Type"),
        (LONG, "fh_Buf"),
        (LONG, "fh_Pos"),
        (LONG, "fh_End"),
        (LONG, "fh_Funcs"),
        (LONG, "fh_Func2"),
        (LONG, "fh_Func3"),
        (LONG, "fh_Args"),
        (LONG, "fh_Arg2"),
    ]


@AmigaStructDef
class PathListStruct(AmigaStruct):
    _format = [(BPTR_SELF, "pl_Next"), (BPTR(FileLockStruct), "pl_Lock")]


@AmigaStructDef
class CLIStruct(AmigaStruct):
    _format = [
        (LONG, "cli_Result2"),
        (BSTR, "cli_SetName"),
        (BPTR(PathListStruct), "cli_CommandDir"),
        (LONG, "cli_ReturnCode"),
        (BSTR, "cli_CommandName"),
        (LONG, "cli_FailLevel"),
        (BSTR, "cli_Prompt"),
        (BPTR(FileHandleStruct), "cli_StandardInput"),
        (BPTR(FileHandleStruct), "cli_CurrentInput"),
        (BSTR, "cli_CommandFile"),
        (LONG, "cli_Interactive"),
        (LONG, "cli_Background"),
        (BPTR(FileHandleStruct), "cli_CurrentOutput"),
        (LONG, "cli_DefaultStack"),
        (BPTR(FileHandleStruct), "cli_StandardOutput"),
        (BPTR_VOID, "cli_Module"),
    ]


@AmigaStructDef
class ProcessStruct(AmigaStruct):
    _format = [
        (TaskStruct, "pr_Task"),
        (MsgPortStruct, "pr_MsgPort"),
        # param
        (WORD, "pr_Pad"),
        (BPTR_VOID, "pr_SegList"),
        (LONG, "pr_StackSize"),
        (APTR_VOID, "pr_GlobVec"),
        (LONG, "pr_TaskNum"),
        (BPTR_VOID, "pr_StackBase"),
        (LONG, "pr_Result2"),
        (BPTR(FileLockStruct), "pr_CurrentDir"),
        (BPTR(FileHandleStruct), "pr_CIS"),
        (BPTR(FileHandleStruct), "pr_COS"),
        (APTR_VOID, "pr_ConsoleTask"),
        (APTR_VOID, "pr_FileSystemTask"),
        (BPTR(CLIStruct), "pr_CLI"),
        (APTR_VOID, "pr_ReturnAddr"),
        (APTR_VOID, "pr_PktWait"),
        (APTR_VOID, "pr_WindowPtr"),
        # 2.0
        (BPTR(FileLockStruct), "pr_HomeDir"),
        (LONG, "pr_Flags"),
        (APTR_VOID, "pr_ExitCode"),
        (LONG, "pr_ExitData"),
        (CSTR, "pr_Arguments"),
        (MinListStruct, "pr_LocalVars"),
        (ULONG, "pr_ShellPrivate"),
        (BPTR(FileHandleStruct), "pr_CES"),
    ]
    _subfield_aliases = {
        "name": "pr_Task.tc_Node.ln_Name",
        "type": "pr_Task.tc_Node.ln_Type",
        "pri": "pr_Task.tc_Node.ln_Pri",
    }


@AmigaStructDef
class DateStampStruct(AmigaStruct):
    _format = [(LONG, "ds_Days"), (LONG, "ds_Minute"), (LONG, "ds_Tick")]


# the union in DosList is splitted up into own types


@AmigaStructDef
class DosListDeviceStruct(AmigaStruct):
    _format = [
        (BPTR_VOID, "dol_Next"),
        (LONG, "dol_Type"),
        (APTR_VOID, "dol_Task"),
        (BPTR_VOID, "dol_Lock"),
        (BSTR, "dol_Handler"),
        (LONG, "dol_StackSize"),
        (LONG, "dol_Priority"),
        (LONG, "dol_Startup"),
        (BPTR_VOID, "dol_SegList"),
        (BPTR_VOID, "dol_GlobVec"),
        (BSTR, "dol_Name"),
    ]


@AmigaStructDef
class DosListVolumeStruct(AmigaStruct):
    _format = [
        (BPTR_VOID, "dol_Next"),
        (LONG, "dol_Type"),
        (APTR_VOID, "dol_Task"),
        (BPTR_VOID, "dol_Lock"),
        (DateStampStruct, "dol_VolumeDate"),
        (BPTR_VOID, "dol_LockList"),
        (LONG, "dol_DiskType"),
        (LONG, "dol_Padding0"),
        (BSTR, "dol_Name"),
    ]


@AmigaStructDef
class AssignListStruct(AmigaStruct):
    _format = [(APTR_SELF, "al_Next"), (BPTR_VOID, "al_Lock")]


@AmigaStructDef
class DosListAssignStruct(AmigaStruct):
    _format = [
        (BPTR_VOID, "dol_Next"),
        (LONG, "dol_Type"),
        (APTR_VOID, "dol_Task"),
        (BPTR_VOID, "dol_Lock"),
        (CSTR, "dol_AssignName"),
        (APTR(AssignListStruct), "dol_List"),
        (ARRAY(ULONG, 4), "dol_Padding"),
        (BSTR, "dol_Name"),
    ]


@AmigaStructDef
class DosInfoStruct(AmigaStruct):
    _format = [
        (BPTR_VOID, "di_McName"),
        (BPTR_VOID, "di_DevInfo"),
        (BPTR_VOID, "di_Devices"),
        (BPTR_VOID, "di_Handlers"),
        (BPTR_VOID, "di_NetHand"),
        (SignalSemaphoreStruct, "di_DevLock"),
        (SignalSemaphoreStruct, "di_EntryLock"),
        (SignalSemaphoreStruct, "di_DeleteLock"),
    ]


@AmigaStructDef
class RootNodeStruct(AmigaStruct):
    _format = [
        (BPTR_VOID, "rn_TaskArray"),
        (BPTR_VOID, "rn_ConsoleSegment"),
        (DateStampStruct, "rn_Time"),
        (LONG, "rn_RestartSeg"),
        (BPTR_VOID, "rn_Info"),
        (BPTR_VOID, "rn_FileHandlerSegment"),
        (MinListStruct, "rn_CliList"),
        (APTR(MsgPortStruct), "rn_BootProc"),
        (BPTR_VOID, "rn_ShellSegment"),
        (LONG, "rn_Flags"),
    ]


@AmigaStructDef
class DosLibraryStruct(AmigaStruct):
    _format = [
        (LibraryStruct, "lib"),
        (APTR(RootNodeStruct), "dl_Root"),
        (APTR_VOID, "dl_GV"),
        (LONG, "dl_A2"),
        (LONG, "dl_A5"),
        (LONG, "dl_A6"),
        (APTR_VOID, "dl_Errors"),
        (APTR_VOID, "dl_TimeReq"),
        (APTR_VOID, "dl_UtilityBase"),
        (APTR_VOID, "dl_IntuitionBase"),
    ]


@AmigaStructDef
class FileInfoBlockStruct(AmigaStruct):
    _format = [
        (ULONG, "fib_DiskKey"),
        (LONG, "fib_DirEntryType"),
        (ARRAY(UBYTE, 108), "fib_FileName"),
        (LONG, "fib_Protection"),
        (LONG, "fib_EntryType"),
        (ULONG, "fib_Size"),
        (LONG, "fib_NumBlocks"),
        (DateStampStruct, "fib_Date"),
        (ARRAY(UBYTE, 80), "fib_Comment"),
        (UWORD, "fib_OwnerUID"),
        (UWORD, "fib_OwnerGID"),
        (ARRAY(UBYTE, 32), "fib_Reserved"),
    ]


@AmigaStructDef
class DosPacketStruct(AmigaStruct):
    _format = [
        (APTR(MessageStruct), "dp_Link"),
        (APTR(MsgPortStruct), "dp_Port"),
        (LONG, "dp_Type"),
        (LONG, "dp_Res1"),
        (LONG, "dp_Res2"),
        (LONG, "dp_Arg1"),
        (LONG, "dp_Arg2"),
        (LONG, "dp_Arg3"),
        (LONG, "dp_Arg4"),
        (LONG, "dp_Arg5"),
        (LONG, "dp_Arg6"),
        (LONG, "dp_Arg7"),
    ]


@AmigaStructDef
class AChainStruct(AmigaStruct):
    _format = [
        (APTR_SELF, "an_Child"),
        (APTR_SELF, "an_Parent"),
        (BPTR_VOID, "an_Lock"),
        (FileInfoBlockStruct, "an_Info"),
        (BYTE, "an_Flags"),
        (UBYTE, "an_String"),
    ]


@AmigaStructDef
class AnchorPathStruct(AmigaStruct):
    _format = [
        (APTR(AChainStruct), "ap_Base"),
        (APTR(AChainStruct), "ap_Last"),
        (LONG, "ap_BreakBits"),
        (LONG, "ap_FoundBreak"),
        (BYTE, "ap_Flags"),
        (BYTE, "ap_Reserved"),
        (WORD, "ap_Strlen"),
        (FileInfoBlockStruct, "ap_Info"),
        (UBYTE, "ap_Buf"),
    ]


@AmigaStructDef
class DevProcStruct(AmigaStruct):
    _format = [
        (APTR(MsgPortStruct), "dvp_Port"),
        (BPTR_VOID, "dvp_Lock"),
        (ULONG, "dvp_Flags"),
        (APTR_VOID, "dvp_DevNode"),
    ]


@AmigaStructDef
class CSourceStruct(AmigaStruct):
    _format = [(APTR(UBYTE), "CS_Buffer"), (LONG, "CS_Length"), (LONG, "CS_CurChr")]


@AmigaStructDef
class RDArgsStruct(AmigaStruct):
    _format = [
        (CSourceStruct, "RDA_Source"),
        (LONG, "RDA_DAList"),
        (APTR(UBYTE), "RDA_Buffer"),
        (LONG, "RDA_BufSiz"),
        (APTR(UBYTE), "RDA_ExtHelp"),
        (LONG, "RDA_Flags"),
    ]


@AmigaStructDef
class DateTimeStruct(AmigaStruct):
    _format = [
        (DateStampStruct, "dat_Stamp"),
        (UBYTE, "dat_Format"),
        (UBYTE, "dat_Flags"),
        (APTR(UBYTE), "dat_StrDay"),
        (APTR(UBYTE), "dat_StrDate"),
        (APTR(UBYTE), "dat_StrTime"),
    ]


@AmigaStructDef
class InfoDataStruct(AmigaStruct):
    _format = [
        (LONG, "id_NumSoftErrors"),
        (LONG, "id_UnitNumber"),
        (LONG, "id_DiskState"),
        (LONG, "id_NumBlocks"),
        (LONG, "id_NumBlocksUsed"),
        (LONG, "id_BytesPerBlock"),
        (LONG, "id_DiskType"),
        (BPTR_VOID, "id_VolumeNode"),
        (LONG, "id_InUse"),
    ]


@AmigaStructDef
class SegmentStruct(AmigaStruct):
    _format = [
        (BPTR_VOID, "seg_Next"),
        (ULONG, "seg_UC"),
        (BPTR_VOID, "seg_Seg"),
        (UBYTE, "seg_Name"),
    ]


@AmigaStructDef
class LocalVarStruct(AmigaStruct):
    _format = [
        (NodeStruct, "lv_Node"),
        (UWORD, "lv_Flags"),
        (APTR(UBYTE), "lv_Value"),
        (ULONG, "lv_Len"),
    ]


@AmigaStructDef
class PathStruct(AmigaStruct):
    _format = [(BPTR_VOID, "path_Next"), (BPTR_VOID, "path_Lock")]
