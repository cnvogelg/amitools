#include <proto/exec.h>
#include <proto/dos.h>

typedef void (*put_proc)();

/* dummy to align bstr at LONG */
ULONG dummy;
char *bstr = "\x04Hoi!";

static void test(STRPTR what, put_proc pp) {
  char buf[256];
  APTR args1[] = { "Huhu" };
  BPTR bptr;
  LONG args3[] = { 23, 42 };
  WORD args4[] = { 23, 42 };
  WORD args5[] = { 'H', 'i', '!' };

  PutStr(what);
  PutStr("\n");

  RawDoFmt("Hello, world!\n", NULL, pp, buf);
  PutStr(buf);

  RawDoFmt("CStr: '%s'\n", args1, pp, buf);
  PutStr(buf);

  bptr = MKBADDR(bstr);
  RawDoFmt("BStr: '%b'\n", &bptr, pp, buf);
  PutStr(buf);

  RawDoFmt("LONG: a=%ld b=%ld\n", args3, pp, buf);
  PutStr(buf);

  RawDoFmt("WORD: a=%d b=%d\n", args4, pp, buf);
  PutStr(buf);

  RawDoFmt("CHAR: '%c%c%c'\n", args5, pp, buf);
  PutStr(buf);
}

int main(int argc, char *argv[])
{
  /* known put codes */
  ULONG putcode1 = 0x16c04e75;
  ULONG putcode2[] = { 0x4e55fffc, 0x2b40fffc, 0x16c04e5d, 0x4e750000 };
  /* fake unknown put code */
  ULONG putcode3[] = { 0x4e714e71, 0x16c04e75 };

  test("putcode1", (put_proc)&putcode1);
  test("putcode2", (put_proc)putcode2);
  test("putcode3", (put_proc)putcode3);

  return 0;
}
