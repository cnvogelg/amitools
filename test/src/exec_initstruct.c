#include <exec/exec.h>
#include <exec/initializers.h>
#include <proto/exec.h>
#include <proto/dos.h>

static UBYTE mem[128];
static UWORD init_tab[] = {
  INITBYTE(8, 21),
  INITWORD(12, 0xdead),
  INITLONG(20, 0xcafebabe),
#if 0
  INITSTRUCT(0, 32, 0, 1), /* 2 LONGs */
  0xdead,0xbeef,0xcafe,0xbabe,
  INITSTRUCT(1, 40, 0, 2), /* 3 WORDs */
  0x1234,0x4567,0x8900,
  INITSTRUCT(2, 64, 0, 3), /* 4 BYTES */
  0x0102,0x0304,
#endif
  0
};

int main(int argc, char *argv[])
{
  UBYTE *ptr = mem;

  InitStruct(init_tab, mem, 128);

  /* check */
  if(*(ptr + 8) != 21) {
    PutStr("BYTE failed\n");
    return 1;
  }
  if(*(UWORD *)(ptr + 12) != 0xdead) {
    PutStr("WORD failed\n");
    return 2;
  }
  if(*(ULONG *)(ptr + 20) != 0xcafebabe) {
    PutStr("LONG failed\n");
    return 3;
  }

  PutStr("ok\n");
  return 0;
}
