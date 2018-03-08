#include <dos/dos.h>
#include <exec/exec.h>

#include <proto/exec.h>
#include <proto/dos.h>
#include <proto/mathffp.h>

struct Library *MathBase;

int main(int argc, char *argv[])
{
  ULONG res = 0;

  MathBase = OpenLibrary("mathffp.library", 34);
  if(MathBase) {
    PutStr("ok!\n");

    CloseLibrary(MathBase);
  } else {
    PutStr("No mathffp.library!\n");
    res = 1;
  }
  return res;
}
