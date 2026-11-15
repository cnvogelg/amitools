#include <exec/exec.h>
#include <dos/dos.h>
#include <dos/exall.h>
#include <proto/exec.h>
#include <proto/dos.h>

/* room for one ED_SIZE entry plus a short name: forces a continued scan */
#define EXALL_BUF_SIZE 32

/* list the directory again with ExAll(), using a buffer too small for
   all entries so the scan continues across calls via eac_LastKey */
static int exall_scan(BPTR lock)
{
    struct ExAllControl *eac;
    struct ExAllData *ead;
    UBYTE buffer[EXALL_BUF_SIZE];
    BOOL more;
    LONG calls = 0;

    eac = AllocDosObject(DOS_EXALLCONTROL, NULL);
    if(eac == NULL) {
        PutStr("Error: no ExAllControl\n");
        return 6;
    }
    eac->eac_LastKey = 0;

    do {
        more = ExAll(lock, (struct ExAllData *)buffer, EXALL_BUF_SIZE, ED_SIZE, eac);
        calls++;
        if(!more && IoErr() != ERROR_NO_MORE_ENTRIES) {
            Printf("Error: ExAll(): IoErr %ld\n", IoErr());
            FreeDosObject(DOS_EXALLCONTROL, eac);
            return 7;
        }
        for(ead = (struct ExAllData *)buffer; eac->eac_Entries > 0; ead = ead->ed_Next) {
            if(ead->ed_Type > 0) {
                PutStr("<DIR> ");
            } else {
                Printf("%5ld ", ead->ed_Size);
            }
            Printf("%s\n", (ULONG)ead->ed_Name);
            eac->eac_Entries--;
        }
    } while(more);

    FreeDosObject(DOS_EXALLCONTROL, eac);
    if(calls < 2) {
        Printf("Error: expected a continued ExAll() scan, got %ld call(s)\n", calls);
        return 8;
    }
    return 0;
}

int main(int argc, char *argv[])
{
    struct FileInfoBlock fib;
    BPTR lock;
    char *test_dir;
    BOOL ok;
    int rc;

    if(argc != 2) {
        PutStr("Usage: <test_dir>\n");
        return 1;
    }
    test_dir = argv[1];

    /* Lock */
    lock = Lock(test_dir, ACCESS_READ);
    if(lock == 0) {
        Printf("Error: can't Lock(): '%s'\n", (ULONG)test_dir);
        return 2;
    }

    /* Examine */
    ok = Examine(lock, &fib);
    if(ok == DOSFALSE) {
        UnLock(lock);
        Printf("Error: can't Examine(): '%s'\n", (ULONG)test_dir);
        return 3;
    }
    Printf("Examine: %s\n", (ULONG)fib.fib_FileName);
    if(fib.fib_DirEntryType < 0) {
        UnLock(lock);
        Printf("Error: wrong type: '%s'\n", (ULONG)test_dir);
        return 4;
    }

    /* ExNext Loop */
    while(ExNext(lock, &fib)==DOSTRUE) {
        if(fib.fib_DirEntryType > 0) {
            PutStr("<DIR> ");
        } else {
            Printf("%5ld ", (ULONG)fib.fib_Size);
        }
        Printf("%s\n", (ULONG)fib.fib_FileName);
    }
    /* Check Error Result */
    if(IoErr() != ERROR_NO_MORE_ENTRIES) {
        UnLock(lock);
        Printf("Error: wrong IoErr(): %d\n", IoErr());
        return 5;
    }

    /* ExAll scan */
    PutStr("ExAll:\n");
    rc = exall_scan(lock);
    if(rc != 0) {
        UnLock(lock);
        return rc;
    }

    UnLock(lock);
    PutStr("ok\n");
    return 0;
}
