#include <dos/dos.h>
#include <proto/dos.h>

int main(int argc, char *argv[])
{
  int a = 65001;
  int b = 0xdead;
  int c = -1;
  char *s1 = "hello";
  UWORD d = 0x0ead;
  UWORD e = 0xdead;
  ULONG f = 0xdeadbeef;

  /* integers (32 bit) */
  Printf("int1 %ld %lx %ld %lu %lx\n", a, b, c, c, c);
  Printf("int2 '%10ld' '%10lx'\n", a, b);
  Printf("int3 '%-10ld' '%-10lx'\n", a, b);

  /* strings */
  Printf("str1 '%s'\n", (ULONG)s1);
  Printf("str2 '%10s'\n", (ULONG)s1);
  Printf("str3 '%-10s'\n", (ULONG)s1);
  Printf("str4 '%2s'\n", (ULONG)s1);
  Printf("str5 '%-2s'\n", (ULONG)s1);

  /* play with limit/width */
  Printf("str6 '%10.s'\n", (ULONG)s1);
  Printf("str7 '%-10.s'\n", (ULONG)s1);
  Printf("str8 '%2.s'\n", (ULONG)s1);
  Printf("str9 '%-2.s'\n", (ULONG)s1);
  Printf("strA '%.10s'\n", (ULONG)s1);
  Printf("strB '%-.10s'\n", (ULONG)s1);
  Printf("strC '%.2s'\n", (ULONG)s1);
  Printf("strD '%-.2s'\n", (ULONG)s1);

  Printf("strE %d %x %u # %d %x %u\n", d, d, d, d, d, d);
  Printf("strF %d %x %u # %d %x %u\n", e, e, e, e, e, e);
  Printf("strG %ld %lx %lu # %ld %lx %lu\n", f, f, f, f, f, f);

  return 0;
}
