#include <dos/dos.h>
#include <proto/dos.h>

int main(int argc, char *argv[])
{
  BPTR lock;
  int i;

  for(i=1;i<argc;i++) {
    lock = Lock(argv[i], ACCESS_READ);
    if(lock != 0) {
      UnLock(lock);
    }
  }
  return 0;
}
