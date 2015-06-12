#include <dos/dos.h>
#include <proto/dos.h>

int main(int argc, char *argv[])
{
  int a = 0xdead;

  /* integers */
  Printf("int %d %x\n", a, a);

  return 0;
}
