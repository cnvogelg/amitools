#include <libraries/vamostest.h>
#include <proto/vamostest.h>
#include <proto/exec.h>

struct VamosTestBase *VamosTestBase;

int main(int argc, char *argv[])
{
  char *error = "RuntimeError";

  if(argc > 1) {
    error = argv[1];
  }

  if ((VamosTestBase = (struct VamosTestBase *)OpenLibrary("vamostest.library", 23)))
  {
    RaiseError((STRPTR)error);
    CloseLibrary((struct Library *)VamosTestBase);
    return 0;
  } else {
    return 1;
  }
}
