#include <exec/exec.h>
#include <dos/dos.h>
#include <proto/exec.h>
#include <proto/dos.h>


int main(int argc, char *argv[])
{
  LONG error;
  ULONG size = sizeof(struct AnchorPath) + 256;
  struct AnchorPath *ap;
  struct FileInfoBlock *fib;
  int ret = 0;

  if(argc != 2) {
    PutStr("Usage: <pattern>\n");
    return 2;
  }

  ap = (struct AnchorPath *)AllocVec(size, MEMF_CLEAR);
  if(ap == NULL) {
    PutStr("No Mem!\n");
    return 3;
  }

  ap->ap_Flags = APF_DOWILD | APF_DODIR;
  ap->ap_Strlen = 255;

  error = MatchFirst(argv[1], ap);
  if(error == ERROR_NO_MORE_ENTRIES) {
    PutStr("none found.\n");
  }
  else if(error != 0) {
    Printf("MatchFirst: %ld\n", error);
    ret = 1;
  } else {
    fib = &ap->ap_Info;
    while(1) {
      Printf("%s %s %ld %ld\n", (ULONG)fib->fib_FileName, (ULONG)&ap->ap_Buf,
        fib->fib_Size, ap->ap_Flags);

      error = MatchNext(ap);
      if(error == ERROR_NO_MORE_ENTRIES) {
        break;
      }
      if(error != 0) {
        Printf("MatchNext: %ld\n", error);
        ret = 4;
        break;
      }
    }
  }

  MatchEnd(ap);
  FreeVec(ap);

  return ret;
}
