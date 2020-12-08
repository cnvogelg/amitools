#include <exec/exec.h>
#include <dos/dos.h>
#include <proto/exec.h>
#include <proto/dos.h>

int main(int argc, char *argv[])
{
    struct FileInfoBlock fib;
    BPTR lock;
    char *test_dir;
    BOOL ok;

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

    UnLock(lock);
    PutStr("ok\n");
    return 0;
}
