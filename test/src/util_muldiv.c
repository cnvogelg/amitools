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
  ULONG q;

#ifdef __VBCC__
  DOSBase = (struct DosLibrary *)OpenLibrary("dos.library", 33L);
  if (DOSBase && (UtilityBase = OpenLibrary("utility.library", 37)))
#else
  if ((UtilityBase = OpenLibrary("utility.library", 37)))
#endif
  {
    q = UDivMod32(10,2);
    Printf("%lu\n", q);

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
