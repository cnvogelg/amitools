#include <dos/dos.h>
#include <exec/exec.h>

#include <proto/exec.h>
#include <proto/dos.h>
#include <proto/mathieeesingtrans.h>

#if defined(__SASC) || defined(AROS)
typedef struct Library BaseType;
#else
typedef struct MathIEEEBase BaseType;
#endif

BaseType *MathIeeeSingTransBase;

int main(int argc, char *argv[])
{
  ULONG res = 0;

  MathIeeeSingTransBase = (BaseType *)OpenLibrary("mathieeesingtrans.library", 34);
  if(MathIeeeSingTransBase) {
    PutStr("ok!\n");

    CloseLibrary((struct Library *)MathIeeeSingTransBase);
  } else {
    PutStr("No mathieeesingtrans.library!\n");
    res = 1;
  }
  return res;
}
