#include <dos/dos.h>
#include <exec/exec.h>

#include <proto/exec.h>
#include <proto/dos.h>
#include <proto/mathieeedoubbas.h>

#include "math_double.h"

#define INT_MIN (-2147483647-1)
#define INT_MAX 2147483647

#if defined(__SASC) || defined(AROS)
typedef struct Library BaseType;
#else
typedef struct MathIEEEBase BaseType;
#endif

BaseType *MathIeeeDoubBasBase;

static void print_double(STRPTR prefix, double d)
{
  ULONG *u = (ULONG *)&d;
  Printf("%s: %08lx %08lx\n", (ULONG)prefix, u[0], u[1]);
}

static void print_long(STRPTR prefix, ULONG l)
{
  Printf("%s: %08lx\n", (ULONG)prefix, l);
}

static void test_const(void)
{
  print_double("const0", DBL_MAX);
  print_double("const1", DBL_MIN);
  print_double("const2", DBL_FLT_MAX);
  print_double("const3", DBL_FLT_MIN);
  print_double("const4", (double)INT_MAX);
  print_double("const5", (double)INT_MIN);
}

static void test_abs(void)
{
  print_double("abs0", IEEEDPAbs(0.0));
  print_double("abs1", IEEEDPAbs(-1.0));
  print_double("abs2", IEEEDPAbs(1.0));
  print_double("abs3", IEEEDPAbs(DBL_FLT_MIN));
  print_double("abs4", IEEEDPAbs(DBL_FLT_MAX));
  print_double("abs5", IEEEDPAbs(DBL_MIN));
  print_double("abs6", IEEEDPAbs(DBL_MAX));
  print_double("abs7", IEEEDPAbs(DBL_FLT_MAX_NEG));
  print_double("abs8", IEEEDPAbs(DBL_MAX_NEG));
}

static void test_add(void)
{
  print_double("add0", IEEEDPAdd(0.0, 0.0));
  print_double("add1", IEEEDPAdd(DBL_MAX, 1.0));
  print_double("add2", IEEEDPAdd(DBL_MIN, DBL_MAX));
  print_double("add3", IEEEDPAdd(DBL_MAX, DBL_MAX));
  print_double("add4", IEEEDPAdd(DBL_MAX, DBL_MAX_NEG));
}

static void test_ceil(void)
{
  print_double("ceil0", IEEEDPCeil(-1.0));
  print_double("ceil1", IEEEDPCeil(1.0));
  print_double("ceil2", IEEEDPCeil(0.0));
  print_double("ceil3", IEEEDPCeil(DBL_FLT_MIN));
  print_double("ceil4", IEEEDPCeil(DBL_FLT_MAX));
  print_double("ceil5", IEEEDPCeil(DBL_MIN));
  print_double("ceil6", IEEEDPCeil(DBL_MAX));
  print_double("ceil7", IEEEDPCeil(DBL_FLT_MIN_NEG));
  print_double("ceil8", IEEEDPCeil(DBL_FLT_MAX_NEG));
  print_double("ceil9", IEEEDPCeil(DBL_MIN_NEG));
  print_double("ceil10", IEEEDPCeil(DBL_MAX_NEG));
}

static void test_cmp(void)
{
  print_long("cmp0", IEEEDPCmp(0.0,0.0));
  print_long("cmp1", IEEEDPCmp(1000.0,10.0));
  print_long("cmp2", IEEEDPCmp(-1000.0,10.0));
  print_long("cmp3", IEEEDPCmp(DBL_MAX,10.0));
  print_long("cmp4", IEEEDPCmp(DBL_MIN,10.0));
  print_long("cmp5", IEEEDPCmp(DBL_MAX,DBL_MAX));
  print_long("cmp6", IEEEDPCmp(DBL_MIN,DBL_MIN));
  print_long("cmp7", IEEEDPCmp(DBL_MAX_NEG,DBL_MAX_NEG));
  print_long("cmp8", IEEEDPCmp(DBL_MIN_NEG,DBL_MIN_NEG));
}

static void test_div(void)
{
  print_double("div0", IEEEDPDiv(0.0, 0.0));
  print_double("div1", IEEEDPDiv(-0.0, 0.0));
  print_double("div2", IEEEDPDiv(1.0, 0.0));
  print_double("div3", IEEEDPDiv(-1.0, 0.0));
  print_double("div4", IEEEDPDiv(1000.0, 10.0));
  print_double("div5", IEEEDPDiv(-1000.0, 10.0));
  print_double("div6", IEEEDPDiv(DBL_MAX, 10.0));
  print_double("div7", IEEEDPDiv(DBL_MIN, 10.0));
  print_double("div8", IEEEDPDiv(DBL_MAX, DBL_MAX));
  print_double("div9", IEEEDPDiv(DBL_MIN, DBL_MIN));
  print_double("div10", IEEEDPDiv(DBL_MAX_NEG, DBL_MAX_NEG));
  print_double("div11", IEEEDPDiv(DBL_MIN_NEG, DBL_MIN_NEG));
}

static void test_fix(void)
{
  print_long("fix0", IEEEDPFix(0.0));
  print_long("fix1", IEEEDPFix(1000.0));
  print_long("fix2", IEEEDPFix(-1000.0));
  print_long("fix3", IEEEDPFix((double)INT_MAX));
  print_long("fix4", IEEEDPFix((double)INT_MIN));
  print_long("fix5", IEEEDPFix(2.0*(double)INT_MAX));
  print_long("fix6", IEEEDPFix(2.0*(double)INT_MIN));
  print_long("fix7", IEEEDPFix(DBL_MAX));
  print_long("fix8", IEEEDPFix(DBL_MIN));
}

static void test_floor(void)
{
  print_double("floor0", IEEEDPFloor(-1.0));
  print_double("floor1", IEEEDPFloor(1.0));
  print_double("floor2", IEEEDPFloor(0.0));
  print_double("floor3", IEEEDPFloor(DBL_FLT_MIN));
  print_double("floor4", IEEEDPFloor(DBL_FLT_MAX));
  print_double("floor5", IEEEDPFloor(DBL_MIN));
  print_double("floor6", IEEEDPFloor(DBL_MAX));
}

static void test_flt(void)
{
  print_double("flt0", IEEEDPFlt(0));
  print_double("flt1", IEEEDPFlt(1000));
  print_double("flt2", IEEEDPFlt(-1000));
  print_double("flt3", IEEEDPFlt(INT_MIN));
  print_double("flt4", IEEEDPFlt(INT_MAX));
}

static void test_mul(void)
{
  print_double("mul0", IEEEDPMul(0.0, 0.0));
  print_double("mul1", IEEEDPMul((double)INT_MAX, 1000.0));
  print_double("mul2", IEEEDPMul(1000.0, (double)INT_MIN));
  print_double("mul3", IEEEDPMul((double)INT_MAX,(double)INT_MAX));
  print_double("mul4", IEEEDPMul((double)INT_MIN,(double)INT_MIN));
}

static void test_neg(void)
{
  print_double("neg0", IEEEDPNeg(-1.0));
  print_double("neg1", IEEEDPNeg(1.0));
  print_double("neg2", IEEEDPNeg(0.0));
  print_double("neg3", IEEEDPNeg(DBL_FLT_MIN));
  print_double("neg4", IEEEDPNeg(DBL_FLT_MAX));
  print_double("neg5", IEEEDPNeg(DBL_MIN));
  print_double("neg6", IEEEDPNeg(DBL_MAX));
  print_double("neg7", IEEEDPNeg(DBL_FLT_MIN_NEG));
  print_double("neg8", IEEEDPNeg(DBL_FLT_MAX_NEG));
  print_double("neg9", IEEEDPNeg(DBL_MIN_NEG));
  print_double("neg10", IEEEDPNeg(DBL_MAX_NEG));
}

static void test_sub(void)
{
  print_double("sub0", IEEEDPSub(0.0, 0.0));
  print_double("sub1", IEEEDPSub(0.0, DBL_MAX));
  print_double("sub2", IEEEDPSub(DBL_MAX, 1.0));
  print_double("sub3", IEEEDPSub(DBL_MAX, -1.0));
  print_double("sub4", IEEEDPSub(DBL_MIN, DBL_MAX));
  print_double("sub5", IEEEDPSub(DBL_MAX, DBL_MAX));
  print_double("sub6", IEEEDPSub(DBL_MAX, DBL_MAX_NEG));
}

static void test_tst(void)
{
  print_long("tst0", IEEEDPTst(0.0));
  print_long("tst1", IEEEDPTst(1000.0));
  print_long("tst2", IEEEDPTst(-1000.0));
  print_long("tst3", IEEEDPTst(DBL_MAX));
  print_long("tst4", IEEEDPTst(DBL_MIN));
  print_long("tst5", IEEEDPTst(DBL_MAX_NEG));
  print_long("tst6", IEEEDPTst(DBL_MIN_NEG));
}

int main(int argc, char *argv[])
{
  ULONG res = 0;

  MathIeeeDoubBasBase = (BaseType *)OpenLibrary("mathieeedoubbas.library", 34);
  if(MathIeeeDoubBasBase) {
    PutStr("ok!\n");

    test_const();

    test_abs();
    test_add();
    test_ceil();
    test_cmp();
    test_div();
    test_fix();
    test_floor();
    test_flt();
    test_mul();
    test_neg();
    test_sub();
    test_tst();

    CloseLibrary((struct Library *)MathIeeeDoubBasBase);
  } else {
    PutStr("No mathieeedoubbas.library!\n");
    res = 1;
  }
  return res;
}
