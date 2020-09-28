#include <exec/exec.h>
#include <dos/dos.h>
#include <proto/exec.h>
#include <proto/dos.h>


int main(int argc, char *argv[])
{
    BPTR fh;
    char *msg = "Hello, world!?";
    int msg_size = 14;
    char buffer[10];
    LONG num_read;
    LONG old_pos;
    LONG io_err;
    char *test_file;

    if(argc != 2) {
        PutStr("Usage: <test_file>\n");
        return 1;
    }
    test_file = argv[1];

    fh = Open(test_file, MODE_NEWFILE);
    if(fh == 0) {
        Printf("Error opening: '%s'\n", (ULONG)test_file);
        return 2;
    }

    if(Write(fh, msg, msg_size) != msg_size) {
        PutStr("Error writing...\n");
        return 3;
    }

    /* now seek */
    old_pos = Seek(fh, 0, OFFSET_BEGINNING);
    io_err = IoErr();
    num_read = Read(fh, buffer, 5);
    buffer[5] = 0;
    Printf("old_pos=%ld, io_err=%ld, num_read=%ld, buf='%s'\n",
        old_pos, io_err, num_read, (ULONG)buffer);

    old_pos = Seek(fh, -5, OFFSET_END);
    io_err = IoErr();
    num_read = Read(fh, buffer, 5);
    buffer[5] = 0;
    Printf("old_pos=%ld, io_err=%ld, num_read=%ld, buf='%s'\n",
        old_pos, io_err, num_read, (ULONG)buffer);

    /* error */
    old_pos = Seek(fh, 10, OFFSET_END);
    io_err = IoErr();
    Printf("old_pos=%ld, io_err=%ld\n",
        old_pos, io_err);


    Close(fh);

    return 0;
}
