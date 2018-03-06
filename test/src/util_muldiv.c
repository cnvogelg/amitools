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
  ULONG q;

  if ((UtilityBase = (UtilType *)OpenLibrary("utility.library", 37)))
  {
    q = UDivMod32(10,2);
    Printf("%lu\n", q);

    CloseLibrary((struct Library *)UtilityBase);
  }
  return 0;
}
