#include <dos/dos.h>
#include <proto/dos.h>

int mystrlen(char *txt)
{
  int len = 0;
  while(*txt != 0) {
    len++;
    txt++;
  }
  return len;
}

int main(int argc, char *argv[])
{
  BPTR fh = Input();
  long mode;
  int result = DOSTRUE;

  if(argc > 3) {
    PutStr("Usage: <mode> [out_str]\n");
    return 1;
  }

  if(argc > 1) {
    mode = argv[1][0] - '0';
    Printf("mode=%ld\n", (LONG)mode);
    result = SetMode(fh, mode);
  }

  if(result == DOSTRUE) {
    UBYTE buf[10];
    LONG len;

    if(argc > 2) {
      Write(Output(), argv[2], (LONG)mystrlen(argv[2]));
    }

    len = Read(fh, buf, 10);
    Printf("read=%ld\n", len);

    return 0;
  } else {
    Printf("Err=%ld\n", (LONG)IoErr());
    PrintFault(IoErr(), "set mode failed");
    return 2;
  }
}
