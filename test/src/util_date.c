#include <dos/dos.h>
#include <exec/exec.h>
#include <proto/exec.h>
#include <proto/dos.h>
#include <proto/utility.h>

#ifdef __SASC
typedef struct Library UtilType;
#else
typedef struct UtilityBase UtilType;
#endif

UtilType *UtilityBase;

int main(int argc, char *argv[])
{
  ULONG res;

  if ((UtilityBase = (UtilType *)OpenLibrary("utility.library", 37)))
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
    res = CheckDate(&cf);
    Printf("f8: %lu\n", res);

    CloseLibrary((struct Library *)UtilityBase);
  }
  return 0;
}
