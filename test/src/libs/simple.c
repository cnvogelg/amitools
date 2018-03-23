#include <dos/dosextens.h>
#include <proto/exec.h>
#include <stabs.h>

/* constants required for libnix lib support */
const char LibName[]="simple.library";
const char LibIdString[]="simple.library 1.0 (07.07.2007)";
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
  return (DOSBase=(struct DosLibrary *)OpenLibrary("dos.library",33L))==NULL;
}

void __UserLibCleanup(void)
{
  CloseLibrary(&DOSBase->dl_lib);
}

/* user funcs */

ADDTABL_1(__UserFunc,d0); /* One Argument in d0 */

int __UserFunc(long a)
{
  return a*2;
}

/* end func table marker (required) */
ADDTABL_END();
