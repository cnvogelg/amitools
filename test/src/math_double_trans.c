#include <dos/dos.h>
#include <exec/exec.h>

#include <proto/exec.h>
#include <proto/dos.h>
#include <proto/mathieeedoubtrans.h>

#include "math_double.h"
#include "math_single.h"

#define INT_MIN (-2147483647-1)
#define INT_MAX 2147483647
#define PI      3.14159265358979323846

#if defined(__SASC) || defined(AROS)
typedef struct Library BaseType;
#else
typedef struct MathIEEEBase BaseType;
#endif

BaseType *MathIeeeDoubTransBase;

static void print_double(STRPTR prefix, double d)
{
  ULONG *u = (ULONG *)&d;
  Printf("%s: %08lx %08lx\n", (ULONG)prefix, u[0], u[1]);
}

static void print_float(STRPTR prefix, float f)
{
  ULONG *u = (ULONG *)&f;
  Printf("%s: %08lx\n", (ULONG)prefix, *u);
}

static void test_const(void)
{
  print_double("const0", DBL_MAX);
  print_double("const1", DBL_MIN);
  print_double("const2", DBL_FLT_MAX);
  print_double("const3", DBL_FLT_MIN);
  print_double("const4", (double)INT_MAX);
  print_double("const5", (double)INT_MIN);
  print_double("const6", PI);
}

static void test_acos(void)
{
  print_double("acos0", IEEEDPAcos(-1.0));
  print_double("acos1", IEEEDPAcos(1.0));
  print_double("acos2", IEEEDPAcos(0.0));
  print_double("acos3", IEEEDPAcos(-0.5));
  print_double("acos4", IEEEDPAcos(0.5));
  /* invalid */
  print_double("acos5", IEEEDPAcos(-2.0));
  print_double("acos6", IEEEDPAcos(2.0));
}

static void test_asin(void)
{
  print_double("asin0", IEEEDPAsin(-1.0));
  print_double("asin1", IEEEDPAsin(1.0));
  print_double("asin2", IEEEDPAsin(0.0));
  print_double("asin3", IEEEDPAsin(-0.5));
  print_double("asin4", IEEEDPAsin(0.5));
  /* invalid */
  print_double("asin5", IEEEDPAsin(-2.0));
  print_double("asin6", IEEEDPAsin(2.0));
}

static void test_atan(void)
{
  print_double("atan0", IEEEDPAtan(0.0));
  print_double("atan1", IEEEDPAtan(PI));
  print_double("atan2", IEEEDPAtan(-PI));
  print_double("atan3", IEEEDPAtan(DBL_MIN));
  print_double("atan4", IEEEDPAtan(DBL_MAX));
  print_double("atan5", IEEEDPAtan(DBL_MIN_NEG));
  print_double("atan6", IEEEDPAtan(DBL_MAX_NEG));
}

static void test_cos(void)
{
  print_double("cos0", IEEEDPCos(0.0));
  print_double("cos1", IEEEDPCos(PI));
  print_double("cos2", IEEEDPCos(-PI));
  print_double("cos3", IEEEDPCos(DBL_MIN));
  print_double("cos4", IEEEDPCos(DBL_MAX));
  print_double("cos5", IEEEDPCos(DBL_MIN_NEG));
  print_double("cos6", IEEEDPCos(DBL_MAX_NEG));
}

static void test_cosh(void)
{
  print_double("cosh0", IEEEDPCosh(0.0));
  print_double("cosh1", IEEEDPCosh(PI));
  print_double("cosh2", IEEEDPCosh(-PI));
  print_double("cosh3", IEEEDPCosh(DBL_MIN));
  print_double("cosh4", IEEEDPCosh(DBL_MAX));
  print_double("cosh5", IEEEDPCosh(DBL_MIN_NEG));
  print_double("cosh6", IEEEDPCosh(DBL_MAX_NEG));
}

static void test_exp(void)
{
  print_double("exp0", IEEEDPExp(0.0));
  print_double("exp1", IEEEDPExp(PI));
  print_double("exp2", IEEEDPExp(-PI));
  print_double("exp3", IEEEDPExp(DBL_MIN));
  print_double("exp4", IEEEDPExp(DBL_MAX));
  print_double("exp5", IEEEDPExp(DBL_MIN_NEG));
  print_double("exp6", IEEEDPExp(DBL_MAX_NEG));
}

static void test_fieee(void)
{
  print_double("fieee0", IEEEDPFieee(0.0f));
  print_double("fieee1", IEEEDPFieee((float)PI));
  print_double("fieee2", IEEEDPFieee((float)-PI));
  print_double("fieee3", IEEEDPFieee(FLT_MIN));
  print_double("fieee4", IEEEDPFieee(FLT_MAX));
  print_double("fieee5", IEEEDPFieee(FLT_MIN_NEG));
  print_double("fieee6", IEEEDPFieee(FLT_MAX_NEG));
}

static void test_log(void)
{
  print_double("log0", IEEEDPLog(0.0));
  print_double("log1", IEEEDPLog(PI));
  print_double("log2", IEEEDPLog(-PI));
  print_double("log3", IEEEDPLog(DBL_MIN));
  print_double("log4", IEEEDPLog(DBL_MAX));
  print_double("log5", IEEEDPLog(DBL_MIN_NEG));
  print_double("log6", IEEEDPLog(DBL_MAX_NEG));
}

static void test_log10(void)
{
  print_double("logt0", IEEEDPLog10(0.0));
  print_double("logt1", IEEEDPLog10(10.0));
  print_double("logt2", IEEEDPLog10(-10.0));
  print_double("logt3", IEEEDPLog10(DBL_MIN));
  print_double("logt4", IEEEDPLog10(DBL_MAX));
  print_double("logt5", IEEEDPLog10(DBL_MIN_NEG));
  print_double("logt6", IEEEDPLog10(DBL_MAX_NEG));
}

static void test_pow(void)
{
  print_double("pow0", IEEEDPPow(0.0, 0.0));
  print_double("pow1", IEEEDPPow(1000.0, 0.0));
  print_double("pow2", IEEEDPPow(DBL_FLT_MAX, DBL_FLT_MAX));
  print_double("pow3", IEEEDPPow(DBL_MAX, DBL_MAX));
  print_double("pow4", IEEEDPPow(-1000.0, -1000.0));
  print_double("pow5", IEEEDPPow(3.0, 4.0));
}

static void test_sin(void)
{
  print_double("sin0", IEEEDPSin(0.0));
  print_double("sin1", IEEEDPSin(PI));
  print_double("sin2", IEEEDPSin(-PI));
  print_double("sin3", IEEEDPSin(DBL_MIN));
  print_double("sin4", IEEEDPSin(DBL_MAX));
  print_double("sin5", IEEEDPSin(DBL_MIN_NEG));
  print_double("sin6", IEEEDPSin(DBL_MAX_NEG));
}

static void test_sincos(void)
{
  double cos;

  print_double("sincos0", IEEEDPSincos(&cos, 0.0));
  print_double("cosret0", cos);
  print_double("sincos1", IEEEDPSincos(&cos, PI));
  print_double("cosret1", cos);
  print_double("sincos2", IEEEDPSincos(&cos, -PI));
  print_double("cosret2", cos);
  print_double("sincos3", IEEEDPSincos(&cos, DBL_MIN));
  print_double("cosret3", cos);
  print_double("sincos4", IEEEDPSincos(&cos, DBL_MAX));
  print_double("cosret4", cos);
  print_double("sincos5", IEEEDPSincos(&cos, DBL_MIN_NEG));
  print_double("cosret5", cos);
  print_double("sincos6", IEEEDPSincos(&cos, DBL_MAX_NEG));
  print_double("cosret6", cos);
}

static void test_sinh(void)
{
  print_double("sinh0", IEEEDPSinh(0.0));
  print_double("sinh1", IEEEDPSinh(PI));
  print_double("sinh2", IEEEDPSinh(-PI));
  print_double("sinh3", IEEEDPSinh(DBL_MIN));
  print_double("sinh4", IEEEDPSinh(DBL_MAX));
  print_double("sinh5", IEEEDPSinh(DBL_MIN_NEG));
  print_double("sinh6", IEEEDPSinh(DBL_MAX_NEG));
}

static void test_sqrt(void)
{
  print_double("sqrt0", IEEEDPSqrt(0.0));
  print_double("sqrt1", IEEEDPSqrt(2.0));
  print_double("sqrt2", IEEEDPSqrt(-2.0));
  print_double("sqrt3", IEEEDPSqrt(DBL_MIN));
  print_double("sqrt4", IEEEDPSqrt(DBL_MAX));
  print_double("sqrt5", IEEEDPSqrt(DBL_MIN_NEG));
  print_double("sqrt6", IEEEDPSqrt(DBL_MAX_NEG));
}

static void test_tan(void)
{
  print_double("tan0", IEEEDPTan(0.0));
  print_double("tan1", IEEEDPTan(PI));
  print_double("tan2", IEEEDPTan(-PI));
  print_double("tan3", IEEEDPTan(DBL_MIN));
  print_double("tan4", IEEEDPTan(DBL_MAX));
  print_double("tan5", IEEEDPTan(DBL_MIN_NEG));
  print_double("tan6", IEEEDPTan(DBL_MAX_NEG));
}

static void test_tanh(void)
{
  print_double("tanh0", IEEEDPTanh(0.0));
  print_double("tanh1", IEEEDPTanh(PI));
  print_double("tanh2", IEEEDPTanh(-PI));
  print_double("tanh3", IEEEDPTanh(DBL_MIN));
  print_double("tanh4", IEEEDPTanh(DBL_MAX));
  print_double("tanh5", IEEEDPTanh(DBL_MIN_NEG));
  print_double("tanh6", IEEEDPTanh(DBL_MAX_NEG));
}

static void test_tieee(void)
{
  print_float("tieee0", IEEEDPTieee(0.0));
  print_float("tieee1", IEEEDPTieee(PI));
  print_float("tieee2", IEEEDPTieee(-PI));
  print_float("tieee3", IEEEDPTieee(DBL_FLT_MIN));
  print_float("tieee4", IEEEDPTieee(DBL_FLT_MAX));
  print_float("tieee5", IEEEDPTieee(DBL_FLT_MIN_NEG));
  print_float("tieee6", IEEEDPTieee(DBL_FLT_MAX_NEG));
  print_float("tieee7", IEEEDPTieee(DBL_MIN));
  print_float("tieee8", IEEEDPTieee(DBL_MAX));
  print_float("tieee9", IEEEDPTieee(DBL_MIN_NEG));
  print_float("tieee10", IEEEDPTieee(DBL_MAX_NEG));
}

int main(int argc, char *argv[])
{
  ULONG res = 0;

  MathIeeeDoubTransBase = (BaseType *)OpenLibrary("mathieeedoubtrans.library", 34);
  if(MathIeeeDoubTransBase) {
    PutStr("ok!\n");

    test_const();

    test_acos();
    test_asin();
    test_atan();
    test_cos();
    test_cosh();
    test_exp();
    test_fieee();
    test_log();
    test_log10();
    test_pow();
    test_sin();
    test_sincos();
    test_sinh();
    test_sqrt();
    test_tan();
    test_tanh();
    test_tieee();

    CloseLibrary((struct Library *)MathIeeeDoubTransBase);
  } else {
    PutStr("No mathieeedoubtrans.library!\n");
    res = 1;
  }
  return res;
}
