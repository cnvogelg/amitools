#define __USE_SYSBASE
#include <exec/exec.h>
#include <proto/exec.h>
#include <proto/dos.h>
#include "compiler.h"

static REG_FUNC APTR expunge(REG(APTR lib_base,a6))
{
  /* remove lib from lib list */
  Remove(lib_base);
  /* no seglist */
  return 0;
}

static ULONG vectors[] = {
  0x200,
  0x400,
  (ULONG)expunge,
  0xffffffff
};

int main(int argc, char *argv[])
{
  struct Library *lib;
  struct Library *match;
  ULONG pos_size = sizeof(struct Library);
  UBYTE *lib_begin;
  int result = 0;
  APTR old_func;

  /* make lib */
  lib = MakeLibrary(vectors, NULL, NULL, pos_size, (BPTR)NULL);
  if(lib == NULL) {
    PutStr("no lib!\n");
    return 1;
  }
  lib->lib_Node.ln_Name = "bla.library";

  /* add library */
  AddLibrary(lib);

  /* search lib */
  match = (struct Library *)FindName(&SysBase->LibList, "bla.library");
  if(match != lib) {
    PutStr("lib NOT found after add!\n");
    result++;
  } else {
    PutStr("lib found after add.\n");
  }

  /* Patch Lib */
  old_func = SetFunction(lib, -6, (APTR)0xcafebabe);
  if(old_func != (APTR)0x200) {
    PutStr("wrong old_func!\n");
    result++;
  } else {
    PutStr("set function ok.\n");
  }

  /* sum library */
  SumLibrary(lib);

  /* remove lib - call expunge to remove lib */
  RemLibrary(lib);

  /* search lib */
  match = (struct Library *)FindName(&SysBase->LibList, "bla.library");
  if(match != NULL) {
    PutStr("lib found after remove?\n");
    result++;
  } else {
    PutStr("lib not found after remove.\n");
  }

  /* free lib */
  lib_begin = (UBYTE *)lib - lib->lib_NegSize;
  FreeVec(lib_begin);
  PutStr("ok\n");
  return result;
}
