#include <exec/exec.h>
#include <exec/initializers.h>
#include <proto/exec.h>
#include <proto/dos.h>
#include "compiler.h"

#define my_offsetof(st, m) \
     ((ULONG) ( (UBYTE *)&((st *)(0))->m - (UBYTE *)0 ))

static const char name[] = "my.library";
static ULONG vectors[] = {
  0x200,
  0x400,
  0x600,
  0xffffffff
};
static UBYTE init_tab[12];

static UBYTE *init_byte(UBYTE *data, UBYTE offset, UBYTE value)
{
  data[0] = 0xa0;
  data[1] = offset;
  data[2] = value;
  data[3] = 0;
  return data + 4;
}

static UBYTE *init_long(UBYTE *data, UBYTE offset, ULONG value)
{
  ULONG *ptr;

  data[0] = 0x80;
  data[1] = offset;
  ptr = (ULONG *)(data + 2);
  *ptr = value;
  return data + 6;
}

static REG_FUNC APTR init(REG(APTR lib_base,d0),
                          REG(BPTR seglist,a0),
                          REG(struct Library *SysBase,a6))
{
  return lib_base;
}

int main(int argc, char *argv[])
{
  struct Library *lib;
  ULONG pos_size = sizeof(struct Library);
  UBYTE *lib_begin;
  int result = 0;

  UBYTE *ptr = init_tab;
  ptr = init_byte(ptr, my_offsetof(struct Library, lib_Node.ln_Type), NT_LIBRARY);
  ptr = init_long(ptr, my_offsetof(struct Library, lib_Node.ln_Name), (ULONG)name);
  *ptr = 0;

  lib = MakeLibrary(vectors, init_tab, (APTR)init, pos_size, NULL);
  if(lib == NULL) {
    PutStr("no lib!\n");
    return 1;
  }

  /* check lib */
  if(lib->lib_Node.ln_Name != name) {
    PutStr("name failed!\n");
    result = 2;
  }
  if(lib->lib_Node.ln_Type != NT_LIBRARY) {
    PutStr("type failed!\n");
    result = 3;
  }

  /* free lib */
  lib_begin = (UBYTE *)lib - lib->lib_NegSize;
  FreeVec(lib_begin);
  PutStr("ok\n");
  return result;
}
