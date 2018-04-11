#include <exec/exec.h>
#include <proto/exec.h>
#include <proto/dos.h>

int main(int argc, char *argv[])
{
  WORD offsets[6] = { -2, 10, 42, 100, 4096, -1 };
  ULONG pointers[6] = { 0x100, 0x202, 0x404, 0x808, 0x10000, 0xffffffff };
  UBYTE table[30];
  ULONG disp_base = 0x1000;
  UBYTE *lib_base = table + 30;
  int i;
  ULONG *addr;
  ULONG faddr;
  UBYTE *ptr = lib_base - 6;

  /* offset */
  MakeFunctions((APTR)lib_base, (APTR)offsets, (APTR)disp_base);
  for(i=0; i<5; i++) {
    UWORD *op = (UWORD *)ptr;
    if(*op != 0x4ef9) {
      Printf("No jump: %04x\n", (ULONG)*op);
      return 1;
    }
    addr = (ULONG *)(ptr + 2);
    faddr = disp_base + offsets[i];
    if(*addr != faddr) {
      Printf("Wrong func addr: %08x != %08x\n", *addr, faddr);
      return 2;
    }
    ptr -= 6;
  }
  PutStr("offset jump table ok\n");

  /* pointers */
  ptr = lib_base - 6;
  MakeFunctions((APTR)lib_base, (APTR)pointers, (APTR)NULL);
  for(i=0; i<5; i++) {
    UWORD *op = (UWORD *)ptr;
    if(*op != 0x4ef9) {
      Printf("No jump: %04x\n", (ULONG)*op);
      return 1;
    }
    addr = (ULONG *)(ptr + 2);
    faddr = pointers[i];
    if(*addr != faddr) {
      Printf("Wrong func addr: %08x != %08x\n", *addr, faddr);
      return 2;
    }
    ptr -= 6;
  }
  PutStr("pointer jump table ok\n");

  return 0;
}
