#include <dos/dos.h>
#include <exec/exec.h>

#include <proto/exec.h>
#include <proto/dos.h>
#include <proto/mathieeesingbas.h>

#include "math_single.h"

#define INT_MIN (-2147483647-1)
#define INT_MAX 2147483647

#if defined(__SASC) || defined(AROS)
typedef struct Library BaseType;
#else
typedef struct MathIEEEBase BaseType;
#endif

BaseType *MathIeeeSingBasBase;

static void print_float(STRPTR prefix, float f)
{
  ULONG *u = (ULONG *)&f;
  Printf("%s: %08lx\n", (ULONG)prefix, *u);
}

static void print_long(STRPTR prefix, ULONG l)
{
  Printf("%s: %08lx\n", (ULONG)prefix, l);
}

static void test_const(void)
{
  print_float("const0", FLT_MAX);
  print_float("const1", FLT_MIN);
  print_float("const2", (float)INT_MAX);
  print_float("const3", (float)INT_MIN);
}

static void test_abs(void)
{
  print_float("abs0", IEEESPAbs(0.0f));
  print_float("abs1", IEEESPAbs(-1.0f));
  print_float("abs2", IEEESPAbs(1.0f));
  print_float("abs3", IEEESPAbs(FLT_MIN));
  print_float("abs4", IEEESPAbs(FLT_MAX));
  print_float("abs5", IEEESPAbs(FLT_MIN_NEG));
  print_float("abs6", IEEESPAbs(FLT_MAX_NEG));
}

static void test_add(void)
{
  print_float("add0", IEEESPAdd(0.0f, 0.0f));
  print_float("add1", IEEESPAdd(FLT_MAX, 1.0f));
  print_float("add2", IEEESPAdd(FLT_MIN, FLT_MAX));
  print_float("add3", IEEESPAdd(FLT_MAX, FLT_MAX));
  print_float("add4", IEEESPAdd(FLT_MAX, FLT_MAX_NEG));
}

static void test_ceil(void)
{
  print_float("ceil0", IEEESPCeil(-1.0f));
  print_float("ceil1", IEEESPCeil(1.0f));
  print_float("ceil2", IEEESPCeil(0.0f));
  print_float("ceil3", IEEESPCeil(FLT_MIN));
  print_float("ceil4", IEEESPCeil(FLT_MAX));
  print_float("ceil5", IEEESPCeil(FLT_MIN_NEG));
  print_float("ceil6", IEEESPCeil(FLT_MAX_NEG));
}

static void test_cmp(void)
{
  print_long("cmp0", IEEESPCmp(0.0f,0.0f));
  print_long("cmp1", IEEESPCmp(1000.0f,10.0f));
  print_long("cmp2", IEEESPCmp(-1000.0f,10.0f));
  print_long("cmp3", IEEESPCmp(FLT_MAX,10.0f));
  print_long("cmp4", IEEESPCmp(FLT_MIN,10.0f));
  print_long("cmp5", IEEESPCmp(FLT_MAX,FLT_MAX));
  print_long("cmp6", IEEESPCmp(FLT_MIN,FLT_MIN));
  print_long("cmp7", IEEESPCmp(FLT_MAX_NEG,FLT_MAX_NEG));
  print_long("cmp8", IEEESPCmp(FLT_MIN_NEG,FLT_MIN_NEG));
}

static void test_div(void)
{
  print_float("div0", IEEESPDiv(0.0f, 0.0f));
  print_float("div1", IEEESPDiv(-0.0f, 0.0f));
  print_float("div2", IEEESPDiv(1.0f, 0.0f));
  print_float("div3", IEEESPDiv(-1.0f, 0.0f));
  print_float("div4", IEEESPDiv(1000.0f, 10.0f));
  print_float("div5", IEEESPDiv(-1000.0f, 10.0f));
  print_float("div6", IEEESPDiv(FLT_MAX, 10.0f));
  print_float("div7", IEEESPDiv(FLT_MIN, 10.0f));
  print_float("div8", IEEESPDiv(FLT_MAX, FLT_MAX));
  print_float("div9", IEEESPDiv(FLT_MIN, FLT_MIN));
  print_float("div10", IEEESPDiv(FLT_MAX_NEG, FLT_MAX_NEG));
  print_float("div11", IEEESPDiv(FLT_MIN_NEG, FLT_MIN_NEG));
}

static void test_fix(void)
{
  print_long("fix0", IEEESPFix(0.0f));
  print_long("fix1", IEEESPFix(1000.0f));
  print_long("fix2", IEEESPFix(-1000.0f));
  print_long("fix3", IEEESPFix((float)INT_MAX));
  print_long("fix4", IEEESPFix((float)INT_MIN));
  print_long("fix5", IEEESPFix(2.0f*(float)INT_MAX));
  print_long("fix6", IEEESPFix(2.0f*(float)INT_MIN));
  print_long("fix7", IEEESPFix(FLT_MAX));
  print_long("fix8", IEEESPFix(FLT_MIN));
}

static void test_floor(void)
{
  print_float("floor0", IEEESPFloor(-1.0f));
  print_float("floor1", IEEESPFloor(1.0f));
  print_float("floor2", IEEESPFloor(0.0f));
  print_float("floor3", IEEESPFloor(FLT_MIN));
  print_float("floor4", IEEESPFloor(FLT_MAX));
}

static void test_flt(void)
{
  print_float("flt0", IEEESPFlt(0));
  print_float("flt1", IEEESPFlt(1000));
  print_float("flt2", IEEESPFlt(-1000));
  print_float("flt3", IEEESPFlt(INT_MIN));
  print_float("flt4", IEEESPFlt(INT_MAX));
}

static void test_mul(void)
{
  print_float("mul0", IEEESPMul(0.0f, 0.0f));
  print_float("mul1", IEEESPMul((float)INT_MAX, 1000.0f));
  print_float("mul2", IEEESPMul(1000.0f, (float)INT_MIN));
  print_float("mul3", IEEESPMul((float)INT_MAX,(float)INT_MAX));
  print_float("mul4", IEEESPMul((float)INT_MIN,(float)INT_MIN));
}

static void test_neg(void)
{
  print_float("neg0", IEEESPNeg(-1.0f));
  print_float("neg1", IEEESPNeg(1.0f));
  print_float("neg2", IEEESPNeg(0.0f));
  print_float("neg3", IEEESPNeg(FLT_MIN));
  print_float("neg4", IEEESPNeg(FLT_MAX));
  print_float("neg5", IEEESPNeg(FLT_MIN_NEG));
  print_float("neg6", IEEESPNeg(FLT_MAX_NEG));
}

static void test_sub(void)
{
  print_float("sub0", IEEESPSub(0.0f, 0.0f));
  print_float("sub1", IEEESPSub(0.0f, FLT_MAX));
  print_float("sub2", IEEESPSub(FLT_MAX, 1.0f));
  print_float("sub3", IEEESPSub(FLT_MAX, -1.0f));
  print_float("sub4", IEEESPSub(FLT_MIN, FLT_MAX));
  print_float("sub5", IEEESPSub(FLT_MAX, FLT_MAX));
  print_float("sub6", IEEESPSub(FLT_MAX, FLT_MAX_NEG));
}

static void test_tst(void)
{
  print_long("tst0", IEEESPTst(0.0f));
  print_long("tst1", IEEESPTst(1000.0f));
  print_long("tst2", IEEESPTst(-1000.0f));
  print_long("tst3", IEEESPTst(FLT_MAX));
  print_long("tst4", IEEESPTst(FLT_MIN));
  print_long("tst5", IEEESPTst(FLT_MAX_NEG));
  print_long("tst6", IEEESPTst(FLT_MIN_NEG));
}

int main(int argc, char *argv[])
{
  ULONG res = 0;

  MathIeeeSingBasBase = (BaseType *)OpenLibrary("mathieeesingbas.library", 34);
  if(MathIeeeSingBasBase) {
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

    CloseLibrary((struct Library *)MathIeeeSingBasBase);
  } else {
    PutStr("No mathieeesingbas.library!\n");
    res = 1;
  }
  return res;
}
