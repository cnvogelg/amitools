#include <dos/dos.h>
#include <proto/dos.h>

int main(int argc, char *argv[])
{
  int a = 65001;
  int b = 0xdead;
  int c = -1;
  char *s1 = "hello";

  /* integers (32 bit) */
  Printf("int %ld %lx %ld %lu %lx\n", a, b, c, c, c);
  Printf("int '%10ld' '%10lx'\n", a, b);
  Printf("int '%-10ld' '%-10lx'\n", a, b);

  /* strings */
  Printf("str '%s'\n", s1);
  Printf("str '%10s'\n", s1);
  Printf("str '%-10s'\n", s1);
  Printf("str '%2s'\n", s1);
  Printf("str '%-2s'\n", s1);

  return 0;
}
