#include <dos/dos.h>
#include <exec/exec.h>

#include <proto/exec.h>
#include <proto/dos.h>
#include <proto/mathieeedoubtrans.h>

#define FLT_MIN 1.17549435E-38
#define FLT_MAX 3.40282347E+38
#define DBL_MIN 2.2250738585072014E-308
#define DBL_MAX 1.7976931348623157E+308
#define INT_MIN (-2147483647-1)
#define INT_MAX 2147483647

#if defined(__SASC) || defined(AROS)
typedef struct Library BaseType;
#else
typedef struct MathIEEEBase BaseType;
#endif

BaseType *MathIeeeDoubTransBase;

static void print_double(STRPTR prefix, double d)
{
  ULONG *u = (ULONG *)&d;
  Printf("%s: %08lx %08x\n", prefix, u[0], u[1]);
}

static void print_long(STRPTR prefix, ULONG l)
{
  Printf("%s: %08lx\n", prefix, l);
}

static void test_const(void)
{
  print_double("const0", DBL_MAX);
  print_double("const1", DBL_MIN);
  print_double("const2", FLT_MAX);
  print_double("const3", FLT_MIN);
  print_double("const4", (double)INT_MAX);
  print_double("const5", (double)INT_MIN);
}

static void test_acos(void)
{
  print_double("acos0", IEEEDPAcos(-1.0));
  print_double("acos1", IEEEDPAcos(1.0));
  print_double("acos2", IEEEDPAcos(0.0));
  print_double("acos3", IEEEDPAcos(-0.5));
  print_double("acos4", IEEEDPAcos(0.5));
  print_double("acos5", IEEEDPAcos(-2.0));
  print_double("acos6", IEEEDPAcos(2.0));
}

int main(int argc, char *argv[])
{
  ULONG res = 0;

  MathIeeeDoubTransBase = (BaseType *)OpenLibrary("mathieeedoubtrans.library", 34);
  if(MathIeeeDoubTransBase) {
    PutStr("ok!\n");

    test_const();

    test_acos();

    CloseLibrary((struct Library *)MathIeeeDoubTransBase);
  } else {
    PutStr("No mathieeedoubtrans.library!\n");
    res = 1;
  }
  return res;
}
