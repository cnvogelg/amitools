#include <dos/dos.h>
#include <exec/exec.h>
#include <proto/exec.h>
#include <proto/dos.h>
#define __NOLIBBASE__
#include <proto/utility.h>

#ifdef __VBCC__
struct DosLibrary *DOSBase;
#endif
struct Library *UtilityBase;

int main(int argc, char *argv[])
{
  ULONG res;

#ifdef __VBCC__
  DOSBase = (struct DosLibrary *)OpenLibrary("dos.library", 33L);
  if (DOSBase && (UtilityBase = OpenLibrary("utility.library", 37)))
#else
  if ((UtilityBase = OpenLibrary("utility.library", 37)))
#endif
  {
    struct ClockData cd;
    struct ClockData cf;

    Amiga2Date(0, &cd);
    res = Date2Amiga(&cd);
    Printf("t0: %lu\n", res);
    res = CheckDate(&cd);
    Printf("c0: %lu\n", res);

    Amiga2Date(1000, &cd);
    res = Date2Amiga(&cd);
    Printf("t1: %lu\n", res);
    res = CheckDate(&cd);
    Printf("c1: %lu\n", res);

    Amiga2Date(0xffffffff, &cd);
    res = Date2Amiga(&cd);
    Printf("t2: %lx\n", res);
    res = CheckDate(&cd);
    Printf("c2: %lx\n", res);

    /* invalid date */
    Amiga2Date(1000, &cf);
    cf.sec = 60;
    res = CheckDate(&cf);
    Printf("f0: %lu\n", res);

    Amiga2Date(1000, &cf);
    cf.min = 60;
    res = CheckDate(&cf);
    Printf("f1: %lu\n", res);

    Amiga2Date(1000, &cf);
    cf.hour = 24;
    res = CheckDate(&cf);
    Printf("f2: %lu\n", res);

    Amiga2Date(1000, &cf);
    cf.mday = 0;
    res = CheckDate(&cf);
    Printf("f3: %lu\n", res);

    Amiga2Date(1000, &cf);
    cf.mday = 32;
    res = CheckDate(&cf);
    Printf("f4: %lu\n", res);

    Amiga2Date(1000, &cf);
    cf.month = 0;
    res = CheckDate(&cf);
    Printf("f5: %lu\n", res);

    Amiga2Date(1000, &cf);
    cf.month = 13;
    res = CheckDate(&cf);
    Printf("f6: %lu\n", res);

    Amiga2Date(1000, &cf);
    cf.year = 1970;
    res = CheckDate(&cf);
    Printf("f7: %lu\n", res);

    Amiga2Date(1000, &cf);
    cf.wday = 7;
    res = Date2Amiga(&cf);
    Printf("f8: %lu\n", res);
    res = CheckDate(&cf);
    Printf("f9: %lu\n", res);

    CloseLibrary(UtilityBase);
  }
#ifdef __VBCC__
  if (DOSBase)
  {
    CloseLibrary(&DOSBase->dl_lib);
  }
#endif
  return 0;
}
