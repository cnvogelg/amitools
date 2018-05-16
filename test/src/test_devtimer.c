#include <proto/exec.h>
#include <proto/dos.h>
#include <proto/timer.h>

int main(int argc, char *argv[])
{
  struct timerequest timerReq;

  if(!OpenDevice("timer.device", UNIT_MICROHZ, (struct IORequest*)&timerReq, 0)) {

    PutStr("ok\n");
    CloseDevice((struct IORequest *)&timerReq);
    return 0;
  } else {
    PutStr("opening timer.device failed!\n");
    return 1;
  }
}
