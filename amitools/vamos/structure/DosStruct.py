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

class DosLibraryStruct(AmigaStruct):
  _name = "Dos"
  _format = [
    ('Library','lib'),
  ]
DosLibraryDef = DosLibraryStruct()
