from enum import IntEnum

from .tag import CommonTag

SYS_Dummy = CommonTag.TAG_USER + 32
NP_Dummy = CommonTag.TAG_USER + 1000
ADO_Dummy = CommonTag.TAG_USER + 2000


class DosTag(IntEnum):
    # System
    SYS_Input = SYS_Dummy + 1
    SYS_Output = SYS_Dummy + 2
    SYS_Asynch = SYS_Dummy + 3
    SYS_UserShell = 36
    SYS_CustomShell = 37
    SYS_Error = SYS_Dummy + 6
    # CreateNewProc
    NP_SegList = NP_Dummy + 1
    NP_FreeSegList = NP_Dummy + 2
    NP_Entry = NP_Dummy + 3
    NP_Input = NP_Dummy + 4
    NP_Output = NP_Dummy + 5
    NP_CloseInput = NP_Dummy + 6
    NP_CloseOutput = NP_Dummy + 7
    NP_Error = NP_Dummy + 8
    NP_CloseError = NP_Dummy + 9
    NP_CurrentDir = NP_Dummy + 10
    NP_StackSize = NP_Dummy + 11
    NP_Name = NP_Dummy + 12
    NP_Priority = NP_Dummy + 13
    NP_ConsoleTask = NP_Dummy + 14
    NP_WindowPtr = NP_Dummy + 15
    NP_HomeDir = NP_Dummy + 16
    NP_CopyVars = NP_Dummy + 17
    NP_Cli = NP_Dummy + 18
    NP_Path = NP_Dummy + 19
    NP_CommandName = NP_Dummy + 20
    NP_Arguments = NP_Dummy + 21
    NP_NotifyOnDeath = NP_Dummy + 22
    NP_Synchronous = NP_Dummy + 23
    NP_ExitCode = NP_Dummy + 24
    NP_ExitData = NP_Dummy + 25
    # AllocDosObject
    ADO_FH_Mode = ADO_Dummy + 1
    ADO_DirLen = ADO_Dummy + 2
    ADR_CommNameLen = ADO_Dummy + 3
    ADR_CommFileLen = ADO_Dummy + 4
    ADR_PromptLen = ADO_Dummy + 5
