#include <dos/dos.h>
#include <proto/dos.h>

static int test(STRPTR template, STRPTR key, LONG res)
{
  LONG r = FindArg(template, key);
  STRPTR msg;
  if(r == res) {
    msg = "ok";
  } else {
    msg = "FAIL";
  }
  Printf("FindArg(%s,%s)=%ld  == %ld  %s\n",
    (ULONG)template, (ULONG)key, r, res, (ULONG)msg);
  if(r != res) {
    return 1;
  } else {
    return 0;
  }
}

int main(int argc, char *argv[])
{
  LONG num_failed = 0;

  num_failed += test("a=b/k","a",0);
  num_failed += test("a=b/k","b",0);
  num_failed += test("a=b/k","c",-1);
  num_failed += test("hello/k,world/m","world",1);

  return num_failed;
}
