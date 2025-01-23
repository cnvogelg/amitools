#include <dos/dos.h>
#include <proto/dos.h>

int main(int argc, char *argv[])
{
  BPTR fh = Input();
  long timeout = 100;
  long result;

  if(argc > 1) {
    PutStr("Usage: [timeout]\n");
    return 2;
  }

  if(argc > 1) {
    timeout = argv[1][0] - '0';
    timeout *= 100;
  }
  Printf("timeout=%ld\n", timeout);

  SetMode(fh, 1); /* RAW */

  result = WaitForChar(fh, timeout);

  SetMode(fh, 0); /* CON */

  Printf("result=%ld\n", result);

  return (result == DOSTRUE) ? 0 : 1;
}
