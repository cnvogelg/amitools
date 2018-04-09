#include <exec/exec.h>
#include <proto/exec.h>

static struct SignalSemaphore sem;

int main(int argc, char *argv[])
{
  LONG got;
  struct SignalSemaphore *sem2;

  InitSemaphore(&sem);

  ObtainSemaphore(&sem);
  ReleaseSemaphore(&sem);

  ObtainSemaphoreShared(&sem);
  ReleaseSemaphore(&sem);

  got = AttemptSemaphore(&sem);
  ReleaseSemaphore(&sem);

  sem.ss_Link.ln_Name = "mine";
  AddSemaphore(&sem);
  sem2 = FindSemaphore((STRPTR)"mine");
  if(sem2 != &sem) {
    return 2;
  }
  RemSemaphore(&sem);

  return got == TRUE ? 0 : 1;
}
