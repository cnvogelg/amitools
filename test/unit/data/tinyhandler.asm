; tiny 68k AmigaDOS file system handler fixture for the vamos native-handler
; tests.  dos.library-free: it only uses exec.library (AbsExecBase at 4.w).
;
; build the checked-in hunk with:
;   vasmm68k_mot -Fhunkexe -o tinyhandler.hunk tinyhandler.asm
;
; The handler finds its own process with FindTask(NULL) (a Process's pr_Task is
; its first member, so the returned Task pointer *is* the Process pointer) and
; waits on pr_MsgPort (offset 92, right after TaskStruct).
;
; Actions:
;   ACTION_STARTUP       (0)  -> dp_Res1 = DOSTRUE
;   ACTION_LOCATE_OBJECT (8)  -> dp_Res1 = 1 (a fake lock), dp_Res2 = 0
;   ACTION_FREE_LOCK     (15) -> dp_Res1 = DOSTRUE
;   ACTION_DIE           (5)  -> dp_Res1 = DOSTRUE, then exit
;   anything else             -> dp_Res1 = 0, dp_Res2 = ERROR_ACTION_NOT_KNOWN

WAITPORT  equ -384
GETMSG    equ -372
REPLYMSG  equ -378
FINDTASK  equ -294

DP_TYPE   equ 8
DP_RES1   equ 12
DP_RES2   equ 16
LN_NAME   equ 10

ERR_ACTION_NOT_KNOWN equ 209

        section code,code
        xdef    _start

_start:
        move.l  4.w,a6                  ; a6 = SysBase
        suba.l  a1,a1
        jsr     FINDTASK(a6)            ; FindTask(NULL) -> d0 = process
        move.l  d0,a4                   ; a4 = process
        lea     92(a4),a3               ; a3 = pr_MsgPort

.loop:
        move.l  a3,a0
        jsr     WAITPORT(a6)            ; WaitPort(pr_MsgPort)
        move.l  a3,a0
        jsr     GETMSG(a6)              ; GetMsg(pr_MsgPort) -> d0 = message
        move.l  d0,a2                   ; a2 = message
        move.l  LN_NAME(a2),a0          ; a0 = packet (mn_Node.ln_Name)
        move.l  DP_TYPE(a0),d1

        cmp.l   #5,d1                   ; ACTION_DIE
        beq     .die
        cmp.l   #0,d1                   ; ACTION_STARTUP
        beq     .ok
        cmp.l   #8,d1                   ; ACTION_LOCATE_OBJECT
        beq     .ok
        cmp.l   #15,d1                  ; ACTION_FREE_LOCK
        beq     .ok

        ; unknown action
        move.l  #ERR_ACTION_NOT_KNOWN,DP_RES2(a0)
        clr.l   DP_RES1(a0)
        bra     .reply

.ok:
        move.l  #1,DP_RES1(a0)
        clr.l   DP_RES2(a0)
        bra     .reply

.die:
        move.l  #1,DP_RES1(a0)
        clr.l   DP_RES2(a0)
        move.l  a2,a1
        jsr     REPLYMSG(a6)            ; ReplyMsg(message)
        moveq   #0,d0                   ; exit code 0
        rts

.reply:
        move.l  a2,a1
        jsr     REPLYMSG(a6)            ; ReplyMsg(message)
        bra     .loop
