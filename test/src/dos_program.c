#include <dos/dos.h>
#include <proto/dos.h>

int main(int argc, char *argv[])
{
  struct FileInfoBlock fib;
  UBYTE buf[256];
  BPTR lock;
  BOOL ok;

  ok = GetProgramName(buf, 255);
  Printf("%08lx %s\n", ok, (ULONG)buf);

  lock = GetProgramDir();
  ok = Examine(lock, &fib);
  Printf("%08lx %s\n", ok, (ULONG)fib.fib_FileName);

  return 0;
}
