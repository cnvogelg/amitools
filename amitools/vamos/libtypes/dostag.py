from enum import IntEnum


class DosTag(IntEnum):
    # System
    SYS_Input = 33
    SYS_Output = 34
    SYS_Asynch = 35
    SYS_UserShell = 36
    SYS_CustomShell = 37
    # CreateNewProc
    NP_SegList = 1001
    NP_FreeSegList = 1002
    NP_Entry = 1003
    NP_Input = 1004
    NP_Output = 1005
    NP_CloseInput = 1006
    NP_CloseOutput = 1007
    NP_Error = 1008
    NP_CloseError = 1009
    NP_CurrentDir = 1010
    NP_StackSize = 1011
    NP_Name = 1012
    NP_Priority = 1013
    NP_ConsoleTask = 1014
    NP_WindowPtr = 1015
    NP_HomeDir = 1016
    NP_CopyVars = 1017
    NP_Cli = 1018
    NP_Path = 1019
    NP_CommandName = 1020
    NP_Arguments = 1021
    NP_NotifyOnDeath = 1022
    NP_Synchronous = 1023
    NP_ExitCode = 1024
    NP_ExitData = 1025
    # AllocDosObject
    ADO_FH_Mode = 2001
    ADO_DirLen = 2002
    ADR_CommNameLen = 2003
    ADR_CommFileLen = 2004
    ADR_PromptLen = 2005
