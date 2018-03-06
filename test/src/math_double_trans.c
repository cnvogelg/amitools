#include <dos/dos.h>
#include <exec/exec.h>

#include <proto/exec.h>
#include <proto/dos.h>
#include <proto/mathieeedoubtrans.h>

#if defined(__SASC) || defined(AROS)
typedef struct Library BaseType;
#else
typedef struct MathIEEEBase BaseType;
#endif

BaseType *MathIeeeDoubTransBase;

int main(int argc, char *argv[])
{
  ULONG res = 0;

  MathIeeeDoubTransBase = (BaseType *)OpenLibrary("mathieeedoubtrans.library", 34);
  if(MathIeeeDoubTransBase) {
    PutStr("ok!\n");

    CloseLibrary((struct Library *)MathIeeeDoubTransBase);
  } else {
    PutStr("No mathieeedoubtrans.library!\n");
    res = 1;
  }
  return res;
}
