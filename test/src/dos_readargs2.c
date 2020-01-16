#include <dos/dos.h>
#include <proto/dos.h>

static STRPTR TEMPLATE = "NAME,NUM/K/N,SWITCH/S";
struct param {
    STRPTR  name;
    ULONG   num;
    ULONG   swit;
} params;

int main(int argc, char *argv[])
{
    struct RDArgs *rda = ReadArgs(TEMPLATE, (LONG *)&params, NULL);
    if(rda != NULL) {
        Printf("NAME=%s\n", (ULONG)params.name);
        Printf("NUM=%ld\n", params.num);
        Printf("SWITCH=%ld\n", params.swit);
        FreeArgs(rda);
        return 0;
    } else {
        PutStr("ReadArg failed!\n");
        return 1;
    }
}
