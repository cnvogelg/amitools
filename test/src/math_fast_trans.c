#include <dos/dos.h>
#include <exec/exec.h>

#include <proto/exec.h>
#include <proto/dos.h>
#include <proto/mathtrans.h>

#include "math_fast.h"
#include "math_single.h"

#define PI      3.14159265358979323846

struct Library *MathTransBase;

static void print_float(STRPTR prefix, FLOAT f)
{
  const ULONG *u = (const ULONG *)(const void *)&f;
  Printf("%s: %08lx\n", prefix, *u);
}

void test_fieee(void)
{
  print_float("fieee0", SPFieee(0.0f));
  print_float("fieee1", SPFieee(1.0f));
  print_float("fieee2", SPFieee(-1.0f));
  print_float("fieee3", SPFieee((float)PI));
  print_float("fieee4", SPFieee((float)-PI));
  print_float("fieee5", SPFieee(FLT_MIN));
  print_float("fieee6", SPFieee(FLT_MAX));
  print_float("fieee7", SPFieee(FLT_MIN_NEG));
  print_float("fieee8", SPFieee(FLT_MAX_NEG));
  print_float("fieee9", SPFieee(FLT_FFP_MIN));
  print_float("fieee10", SPFieee(FLT_FFP_MAX));
  print_float("fieee11", SPFieee(FLT_FFP_MIN_NEG));
  print_float("fieee12", SPFieee(FLT_FFP_MAX_NEG));
}

void test_tieee(void)
{
  print_float("tieee0", SPTieee(FFP_ZERO));
  print_float("tieee1", SPTieee(FFP_ONE));
  print_float("tieee2", SPTieee(FFP_ONE_NEG));
  print_float("tieee3", SPTieee(FFP_PI));
  print_float("tieee4", SPTieee(FFP_PI_NEG));
  print_float("tieee5", SPTieee(FFP_MIN));
  print_float("tieee6", SPTieee(FFP_MIN_NEG));
  print_float("tieee7", SPTieee(FFP_MAX));
  print_float("tieee8", SPTieee(FFP_MAX_NEG));
}

int main(int argc, char *argv[])
{
  ULONG res = 0;

  MathTransBase = OpenLibrary("mathtrans.library", 34);
  if(MathTransBase) {
    PutStr("ok!\n");

    test_fieee();
    test_tieee();

    CloseLibrary(MathTransBase);
  } else {
    PutStr("No mathtrans.library!\n");
    res = 1;
  }
  return res;
}
