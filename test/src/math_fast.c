#include <dos/dos.h>
#include <exec/exec.h>

#include <proto/exec.h>
#include <proto/dos.h>
#include <proto/mathffp.h>

#include "math_fast.h"

#define INT_MIN (-2147483647-1)
#define INT_MAX 2147483647

struct Library *MathBase;

static void print_float(STRPTR prefix, FLOAT f)
{
  const ULONG *u = (const ULONG *)(const void *)&f;
  Printf("%s: %08lx\n", (ULONG)prefix, *u);
}

static void print_long(STRPTR prefix, ULONG l)
{
  Printf("%s: %08lx\n", (ULONG)prefix, l);
}

static void test_const(void)
{
  print_float("const0", FFP_MAX);
  print_float("const1", FFP_MIN);
  print_float("const2", FFP_INT_MAX);
  print_float("const3", FFP_INT_MIN);
}

static void test_abs(void)
{
  print_float("abs0", SPAbs(FFP_ZERO));
  print_float("abs1", SPAbs(FFP_ONE_NEG));
  print_float("abs2", SPAbs(FFP_ONE));
  print_float("abs3", SPAbs(FFP_MIN));
  print_float("abs4", SPAbs(FFP_MAX));
  print_float("abs5", SPAbs(FFP_MIN_NEG));
  print_float("abs6", SPAbs(FFP_MAX_NEG));
}

static void test_add(void)
{
  print_float("add0", SPAdd(FFP_ZERO, FFP_ZERO));
  print_float("add1", SPAdd(FFP_MAX, FFP_ONE));
  print_float("add2", SPAdd(FFP_MIN, FFP_MAX));
  print_float("add3", SPAdd(FFP_MAX, FFP_MAX));
  print_float("add4", SPAdd(FFP_MAX, FFP_MAX_NEG));
}

static void test_ceil(void)
{
  print_float("ceil0", SPCeil(FFP_ONE_NEG));
  print_float("ceil1", SPCeil(FFP_ONE));
  print_float("ceil2", SPCeil(FFP_ZERO));
  print_float("ceil3", SPCeil(FFP_MIN));
  print_float("ceil4", SPCeil(FFP_MAX));
  print_float("ceil5", SPCeil(FFP_MIN_NEG));
  print_float("ceil6", SPCeil(FFP_MAX_NEG));
}

static void test_cmp(void)
{
  print_long("cmp0", SPCmp(FFP_ZERO,FFP_ZERO));
  print_long("cmp1", SPCmp(FFP_1000,FFP_10));
  print_long("cmp2", SPCmp(FFP_1000_NEG,FFP_10));
  print_long("cmp3", SPCmp(FFP_MAX,FFP_10));
  print_long("cmp4", SPCmp(FFP_MIN,FFP_10));
  print_long("cmp5", SPCmp(FFP_MAX,FFP_MAX));
  print_long("cmp6", SPCmp(FFP_MIN,FFP_MIN));
  print_long("cmp7", SPCmp(FFP_MAX_NEG,FFP_MAX_NEG));
  print_long("cmp8", SPCmp(FFP_MIN_NEG,FFP_MIN_NEG));
}

static void test_div(void)
{
  /* crash on real Amiga? */
#if 0
  print_float("div0", SPDiv(FFP_ZERO, FFP_ZERO));
  print_float("div1", SPDiv(FFP_ONE, FFP_ZERO));
  print_float("div2", SPDiv(FFP_ONE_NEG, FFP_ZERO));
#endif
  print_float("div3", SPDiv(FFP_1000, FFP_10));
  print_float("div4", SPDiv(FFP_1000_NEG, FFP_10));
  print_float("div5", SPDiv(FFP_MAX, FFP_10));
  print_float("div6", SPDiv(FFP_MIN, FFP_10));
  print_float("div7", SPDiv(FFP_MAX, FFP_MAX));
  print_float("div8", SPDiv(FFP_MIN, FFP_MIN));
  print_float("div9", SPDiv(FFP_MAX_NEG, FFP_MAX_NEG));
  print_float("div10", SPDiv(FFP_MIN_NEG, FFP_MIN_NEG));
}

static void test_fix(void)
{
  print_long("fix0", SPFix(FFP_ZERO));
  print_long("fix1", SPFix(FFP_1000));
  print_long("fix2", SPFix(FFP_1000_NEG));
  print_long("fix3", SPFix(FFP_INT_MAX));
  print_long("fix4", SPFix(FFP_INT_MIN));
  print_long("fix5", SPFix(FFP_MAX));
  print_long("fix6", SPFix(FFP_MIN));
}

static void test_floor(void)
{
  print_float("floor0", SPFloor(FFP_ONE_NEG));
  print_float("floor1", SPFloor(FFP_ONE));
  print_float("floor2", SPFloor(FFP_ZERO));
  print_float("floor3", SPFloor(FFP_MIN));
  print_float("floor4", SPFloor(FFP_MAX));
}

static void test_flt(void)
{
  print_float("flt0", SPFlt(0));
  print_float("flt1", SPFlt(1000));
  print_float("flt2", SPFlt(-1000));
  print_float("flt3", SPFlt(INT_MIN));
  print_float("flt4", SPFlt(INT_MAX));
}

static void test_mul(void)
{
  print_float("mul0", SPMul(FFP_ZERO, FFP_ZERO));
  print_float("mul1", SPMul(FFP_INT_MAX, FFP_1000));
  print_float("mul2", SPMul(FFP_1000, FFP_INT_MIN));
  print_float("mul3", SPMul(FFP_INT_MAX,FFP_INT_MAX));
  print_float("mul4", SPMul(FFP_INT_MIN,FFP_INT_MIN));
}

static void test_neg(void)
{
  print_float("neg0", SPNeg(FFP_ONE_NEG));
  print_float("neg1", SPNeg(FFP_ONE));
  print_float("neg2", SPNeg(FFP_ZERO));
  print_float("neg3", SPNeg(FFP_MIN));
  print_float("neg4", SPNeg(FFP_MAX));
  print_float("neg5", SPNeg(FFP_MIN_NEG));
  print_float("neg6", SPNeg(FFP_MAX_NEG));
}

static void test_sub(void)
{
  print_float("sub0", SPSub(FFP_ZERO, FFP_ZERO));
  print_float("sub1", SPSub(FFP_ZERO, FFP_MAX));
  print_float("sub2", SPSub(FFP_MAX, FFP_ONE));
  print_float("sub3", SPSub(FFP_MAX, FFP_ONE_NEG));
  print_float("sub4", SPSub(FFP_MIN, FFP_MAX));
  print_float("sub5", SPSub(FFP_MAX, FFP_MAX));
  print_float("sub6", SPSub(FFP_MAX, FFP_MAX_NEG));
}

static void test_tst(void)
{
  print_long("tst0", SPTst(FFP_ZERO));
  print_long("tst1", SPTst(FFP_1000));
  print_long("tst2", SPTst(FFP_1000_NEG));
  print_long("tst3", SPTst(FFP_MAX));
  print_long("tst4", SPTst(FFP_MIN));
  print_long("tst5", SPTst(FFP_MAX_NEG));
  print_long("tst6", SPTst(FFP_MIN_NEG));
}

int main(int argc, char *argv[])
{
  ULONG res = 0;

  MathBase = OpenLibrary("mathffp.library", 34);
  if(MathBase) {
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

    CloseLibrary(MathBase);
  } else {
    PutStr("No mathffp.library!\n");
    res = 1;
  }
  return res;
}
