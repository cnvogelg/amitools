#include <proto/testnix.h>
#include <proto/exec.h>
#include <proto/dos.h>

struct Library *TestNixBase;

int main(int argc, char *argv[])
{
  ULONG a = 21;
  ULONG b = 23;

  TestNixBase = OpenLibrary("testnix.library", 1);
  if(TestNixBase != NULL)
  {
    ULONG c = Add(a, b);
    CloseLibrary(TestNixBase);
    if(c == (a+b)) {
      PutStr("Ok.\n");
      return 0;
    } else {
      PutStr("Add failed?\n");
      return 1;
    }
  } else {
    PutStr("Lib 'testnix.library' not found!\n");
    return 2;
  }
}
