#include <exec/exec.h>
#include <dos/dos.h>
#include <proto/exec.h>
#include <proto/dos.h>

static struct Resident *find_res(BPTR seg)
{
  STRPTR addr = (STRPTR)(BADDR(seg)) - sizeof(ULONG);
  ULONG size = *(ULONG *)addr;
  STRPTR data = (STRPTR)(BADDR(seg)) + sizeof(BPTR);
  ULONG i;

  Printf("SEG:%08lx, ADDR:%08lx, SIZE:%08lx\n", seg, (ULONG)data, size);
  for(i=0;i<size;i+=2) {
    struct Resident *res = (struct Resident *)data;
    if(res->rt_MatchWord == RTC_MATCHWORD && res->rt_MatchTag == res) {
      return res;
    }
    data += 2;
  }
  return NULL;
}

int main(int argc, char *argv[])
{
  BPTR seglist;
  struct Resident *res;
  int result = 0;
  struct Library *lib;

  if(argc != 2) {
    Printf("Usage: %s <file>\n", (ULONG)argv[0]);
    return 1;
  }

  seglist = LoadSeg(argv[1]);
  if(seglist == 0) {
    Printf("No seglist found: %s\n", (ULONG)argv[1]);
    return 2;
  }

  /* find resident */
  res = find_res(seglist);
  if(res == 0) {
    PutStr("no resident?\n");
    result = 3;
  }
  else {
    /* init resident */
    lib = InitResident(res, seglist);
    if(lib == NULL) {
      PutStr("no lib?\n");
      result = 4;
      UnLoadSeg(seglist);
    }
    else {
      /* remove lib again */
      RemLibrary(lib);
    }
  }

  return result;
}
