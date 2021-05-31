#include <libraries/vamostest.h>
#include <proto/vamostest.h>
#include <proto/exec.h>
#include <proto/dos.h>

struct VamosTestBase *VamosTestBase;

int main(int argc, char *argv[])
{
  if ((VamosTestBase = (struct VamosTestBase *)OpenLibrary("vamostest.library", 23)))
  {
    int result = ExecutePy(argc - 1, (STRPTR *)(argv + 1));
    CloseLibrary((struct Library *)VamosTestBase);
    return result;
  } else {
    PutStr("Error opening 'vamostest.library'\n");
    return 1;
  }
}
