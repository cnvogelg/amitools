#include <dos/dos.h>
#include <exec/exec.h>

#include <proto/exec.h>
#include <proto/dos.h>
#include <proto/mathieeesingbas.h>
#include <proto/mathieeesingtrans.h>

#if defined(__SASC) || defined(AROS)
typedef struct Library BaseType;
#else
typedef struct MathIEEEBase BaseType;
#endif

BaseType *MathIeeeSingBasBase;
BaseType *MathIeeeSingTransBase;

int main(int argc, char *argv[])
{
  ULONG res = 0;

  MathIeeeSingBasBase = (BaseType *)OpenLibrary("mathieeesingbas.library", 34);
  if(MathIeeeSingBasBase) {
    MathIeeeSingTransBase = (BaseType *)OpenLibrary("mathieeesingtrans.library", 34);
    if(MathIeeeSingTransBase) {
      PutStr("ok!\n");

      CloseLibrary((struct Library *)MathIeeeSingTransBase);
    } else {
      PutStr("No mathieeesingtrans.library!\n");
      res = 2;
    }
    CloseLibrary((struct Library *)MathIeeeSingBasBase);
  } else {
    PutStr("No mathieeesingbas.library!\n");
    res = 1;
  }
  return res;
}
