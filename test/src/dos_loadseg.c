#include <dos/dos.h>
#include <proto/dos.h>

int main(int argc, char *argv[])
{
  BPTR seglist;

  if(argc != 2) {
    Printf("Usage: %s <file>\n", (ULONG)argv[0]);
    return 1;
  }

  seglist = LoadSeg(argv[1]);
  if(seglist == 0) {
    Printf("No seglist found: %s\n", (ULONG)argv[1]);
    return 2;
  }

  UnLoadSeg(seglist);
  return 0;
}
