#include <exec/exec.h>
#include <dos/dos.h>
#include <proto/exec.h>
#include <proto/dos.h>


int main(int argc, char *argv[])
{
    char msg[] = "Hello, world!?\n";

    /* PutStr */
    PutStr(msg);

    /* WriteChars */
    WriteChars(msg, sizeof(msg));

    return 0;
}
