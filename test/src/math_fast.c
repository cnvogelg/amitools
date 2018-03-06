#include <dos/dos.h>
#include <exec/exec.h>

#include <proto/exec.h>
#include <proto/dos.h>
#include <proto/mathffp.h>
#include <proto/mathtrans.h>

struct Library *MathBase;
struct Library *MathTransBase;

int main(int argc, char *argv[])
{
  ULONG res = 0;

  MathBase = OpenLibrary("mathffp.library", 34);
  if(MathBase) {
    MathTransBase = OpenLibrary("mathtrans.library", 34);
    if(MathTransBase) {
      PutStr("ok!\n");

      CloseLibrary(MathTransBase);
    } else {
      PutStr("No mathtrans.library!\n");
      res = 2;
    }
    CloseLibrary(MathBase);
  } else {
    PutStr("No mathffp.library!\n");
    res = 1;
  }
  return res;
}
