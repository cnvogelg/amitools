#include <dos/dosextens.h>
#include <proto/exec.h>
#include <stabs.h>

/* constants required for libnix lib support */
const char LibName[]="testnix.library";
const char LibIdString[]="testnix.library 1.0 (07.07.2007)";
const UWORD LibVersion=1;
const UWORD LibRevision=0;

struct Library *myLibPtr;
struct ExecBase *SysBase;
struct DosLibrary *DOSBase;

/* user init/cleanup */

int __UserLibInit(struct Library *myLib)
{
  myLibPtr = myLib;

  SysBase = *(struct ExecBase **)4L;
  DOSBase=(struct DosLibrary *)OpenLibrary("dos.library",33L);
  return DOSBase==NULL;
}

void __UserLibCleanup(void)
{
  CloseLibrary(&DOSBase->dl_lib);
}

/* user funcs */

ADDTABL_2(Add,d0,d1);

ULONG Add(ULONG a, ULONG b)
{
  return a + b;
}

/* end func table marker (required) */
ADDTABL_END();
