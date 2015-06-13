#include <dos/dos.h>
#include <proto/dos.h>

int main(int argc, char *argv[])
{
  int a = 65001;
  int b = 0xdead;
  int c = -1;
  char *s1 = "hello";

  /* integers (32 bit) */
  Printf("int1 %ld %lx %ld %lu %lx\n", a, b, c, c, c);
  Printf("int2 '%10ld' '%10lx'\n", a, b);
  Printf("int3 '%-10ld' '%-10lx'\n", a, b);

  /* strings */
  Printf("str1 '%s'\n", s1);
  Printf("str2 '%10s'\n", s1);
  Printf("str3 '%-10s'\n", s1);
  Printf("str4 '%2s'\n", s1);
  Printf("str5 '%-2s'\n", s1);

  /* play with limit/width */
  Printf("str6 '%10.s'\n", s1);
  Printf("str7 '%-10.s'\n", s1);
  Printf("str8 '%2.s'\n", s1);
  Printf("str9 '%-2.s'\n", s1);
  Printf("strA '%.10s'\n", s1);
  Printf("strB '%-.10s'\n", s1);
  Printf("strC '%.2s'\n", s1);
  Printf("strD '%-.2s'\n", s1);

  return 0;
}
