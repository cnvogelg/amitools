#include <libraries/vamostest.h>
#include <proto/vamostest.h>
#include <proto/exec.h>

struct VamosTestBase *VamosTestBase;

int main(int argc, char *argv[])
{
  if ((VamosTestBase = (struct VamosTestBase *)OpenLibrary("vamostest.library", 23)))
  {
    PrintHello();
    CloseLibrary((struct Library *)VamosTestBase);
    return 0;
  } else {
    return 1;
  }
}
