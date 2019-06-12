#include <dos/dos.h>
#include <exec/exec.h>

#include <proto/exec.h>
#include <proto/dos.h>
#include <proto/mathieeesingtrans.h>

#include "math_single.h"

#define INT_MIN (-2147483647-1)
#define INT_MAX 2147483647
#define PI      3.14159265358979323846f

#if defined(__SASC) || defined(AROS)
typedef struct Library BaseType;
#else
typedef struct MathIEEEBase BaseType;
#endif

BaseType *MathIeeeSingTransBase;

static void print_float(STRPTR prefix, float f)
{
  ULONG *u = (ULONG *)&f;
  Printf("%s: %08lx\n", (ULONG)prefix, *u);
}

static void test_const(void)
{
  print_float("const0", FLT_MAX);
  print_float("const1", FLT_MIN);
  print_float("const2", (float)INT_MAX);
  print_float("const3", (float)INT_MIN);
  print_float("const4", PI);
}

static void test_acos(void)
{
  print_float("acos0", IEEESPAcos(-1.0f));
  print_float("acos1", IEEESPAcos(1.0f));
  print_float("acos2", IEEESPAcos(0.0f));
  print_float("acos3", IEEESPAcos(-0.5f));
  print_float("acos4", IEEESPAcos(0.5f));
  /* invalid */
  print_float("acos5", IEEESPAcos(-2.0f));
  print_float("acos6", IEEESPAcos(2.0f));
}

static void test_asin(void)
{
  print_float("asin0", IEEESPAsin(-1.0f));
  print_float("asin1", IEEESPAsin(1.0f));
  print_float("asin2", IEEESPAsin(0.0f));
  print_float("asin3", IEEESPAsin(-0.5f));
  print_float("asin4", IEEESPAsin(0.5f));
  /* invalid */
  print_float("asin5", IEEESPAsin(-2.0f));
  print_float("asin6", IEEESPAsin(2.0f));
}

static void test_atan(void)
{
  print_float("atan0", IEEESPAtan(0.0f));
  print_float("atan1", IEEESPAtan(PI));
  print_float("atan2", IEEESPAtan(-PI));
  print_float("atan3", IEEESPAtan(FLT_MIN));
  print_float("atan4", IEEESPAtan(FLT_MAX));
  print_float("atan5", IEEESPAtan(FLT_MIN_NEG));
  print_float("atan6", IEEESPAtan(FLT_MAX_NEG));
}

static void test_cos(void)
{
  print_float("cos0", IEEESPCos(0.0f));
  print_float("cos1", IEEESPCos(PI));
  print_float("cos2", IEEESPCos(-PI));
  print_float("cos3", IEEESPCos(FLT_MIN));
  print_float("cos4", IEEESPCos(FLT_MAX));
  print_float("cos5", IEEESPCos(FLT_MIN_NEG));
  print_float("cos6", IEEESPCos(FLT_MAX_NEG));
}

static void test_cosh(void)
{
  print_float("cosh0", IEEESPCosh(0.0f));
  print_float("cosh1", IEEESPCosh(PI));
  print_float("cosh2", IEEESPCosh(-PI));
  print_float("cosh3", IEEESPCosh(FLT_MIN));
  print_float("cosh4", IEEESPCosh(FLT_MAX));
  print_float("cosh5", IEEESPCosh(FLT_MIN_NEG));
  print_float("cosh6", IEEESPCosh(FLT_MAX_NEG));
}

static void test_exp(void)
{
  print_float("exp0", IEEESPExp(0.0f));
  print_float("exp1", IEEESPExp(PI));
  print_float("exp2", IEEESPExp(-PI));
  print_float("exp3", IEEESPExp(FLT_MIN));
  print_float("exp4", IEEESPExp(FLT_MAX));
  print_float("exp5", IEEESPExp(FLT_MIN_NEG));
  print_float("exp6", IEEESPExp(FLT_MAX_NEG));
}

static void test_fieee(void)
{
  print_float("fieee0", IEEESPFieee(0.0f));
  print_float("fieee1", IEEESPFieee((float)PI));
  print_float("fieee2", IEEESPFieee((float)-PI));
  print_float("fieee3", IEEESPFieee(FLT_MIN));
  print_float("fieee4", IEEESPFieee(FLT_MAX));
  print_float("fieee5", IEEESPFieee(FLT_MIN_NEG));
  print_float("fieee6", IEEESPFieee(FLT_MAX_NEG));
}

static void test_log(void)
{
  print_float("log0", IEEESPLog(0.0f));
  print_float("log1", IEEESPLog(PI));
  print_float("log2", IEEESPLog(-PI));
  print_float("log3", IEEESPLog(FLT_MIN));
  print_float("log4", IEEESPLog(FLT_MAX));
  print_float("log5", IEEESPLog(FLT_MIN_NEG));
  print_float("log6", IEEESPLog(FLT_MAX_NEG));
}

static void test_log10(void)
{
  print_float("logt0", IEEESPLog10(0.0f));
  print_float("logt1", IEEESPLog10(10.0f));
  print_float("logt2", IEEESPLog10(-10.0f));
  print_float("logt3", IEEESPLog10(FLT_MIN));
  print_float("logt4", IEEESPLog10(FLT_MAX));
  print_float("logt5", IEEESPLog10(FLT_MIN_NEG));
  print_float("logt6", IEEESPLog10(FLT_MAX_NEG));
}

static void test_pow(void)
{
  print_float("pow0", IEEESPPow(0.0f, 0.0f));
  print_float("pow1", IEEESPPow(1000.0f, 0.0f));
  print_float("pow2", IEEESPPow(FLT_MAX, FLT_MAX));
  print_float("pow3", IEEESPPow(-1000.0f, -1000.0f));
  print_float("pow4", IEEESPPow(3.0f, 4.0f));
}

static void test_sin(void)
{
  print_float("sin0", IEEESPSin(0.0f));
  print_float("sin1", IEEESPSin(PI));
  print_float("sin2", IEEESPSin(-PI));
  print_float("sin3", IEEESPSin(FLT_MIN));
  print_float("sin4", IEEESPSin(FLT_MAX));
  print_float("sin5", IEEESPSin(FLT_MIN_NEG));
  print_float("sin6", IEEESPSin(FLT_MAX_NEG));
}

static void test_sincos(void)
{
  float cos;

  print_float("sincos0", IEEESPSincos(&cos, 0.0f));
  print_float("cosret0", cos);
  print_float("sincos1", IEEESPSincos(&cos, PI));
  print_float("cosret1", cos);
  print_float("sincos2", IEEESPSincos(&cos, -PI));
  print_float("cosret2", cos);
  print_float("sincos3", IEEESPSincos(&cos, FLT_MIN));
  print_float("cosret3", cos);
  print_float("sincos4", IEEESPSincos(&cos, FLT_MAX));
  print_float("cosret4", cos);
  print_float("sincos5", IEEESPSincos(&cos, FLT_MIN_NEG));
  print_float("cosret5", cos);
  print_float("sincos6", IEEESPSincos(&cos, FLT_MAX_NEG));
  print_float("cosret6", cos);
}

static void test_sinh(void)
{
  print_float("sinh0", IEEESPSinh(0.0f));
  print_float("sinh1", IEEESPSinh(PI));
  print_float("sinh2", IEEESPSinh(-PI));
  print_float("sinh3", IEEESPSinh(FLT_MIN));
  print_float("sinh4", IEEESPSinh(FLT_MAX));
  print_float("sinh5", IEEESPSinh(FLT_MIN_NEG));
  print_float("sinh6", IEEESPSinh(FLT_MAX_NEG));
}

static void test_sqrt(void)
{
  print_float("sqrt0", IEEESPSqrt(0.0f));
  print_float("sqrt1", IEEESPSqrt(2.0f));
  print_float("sqrt2", IEEESPSqrt(-2.0f));
  print_float("sqrt3", IEEESPSqrt(FLT_MIN));
  print_float("sqrt4", IEEESPSqrt(FLT_MAX));
  print_float("sqrt5", IEEESPSqrt(FLT_MIN_NEG));
  print_float("sqrt6", IEEESPSqrt(FLT_MAX_NEG));
}

static void test_tan(void)
{
  print_float("tan0", IEEESPTan(0.0f));
  print_float("tan1", IEEESPTan(PI));
  print_float("tan2", IEEESPTan(-PI));
  print_float("tan3", IEEESPTan(FLT_MIN));
  print_float("tan4", IEEESPTan(FLT_MAX));
  print_float("tan5", IEEESPTan(FLT_MIN_NEG));
  print_float("tan6", IEEESPTan(FLT_MAX_NEG));
}

static void test_tanh(void)
{
  print_float("tanh0", IEEESPTanh(0.0f));
  print_float("tanh1", IEEESPTanh(PI));
  print_float("tanh2", IEEESPTanh(-PI));
  print_float("tanh3", IEEESPTanh(FLT_MIN));
  print_float("tanh4", IEEESPTanh(FLT_MAX));
  print_float("tanh5", IEEESPTanh(FLT_MIN_NEG));
  print_float("tanh6", IEEESPTanh(FLT_MAX_NEG));
}

static void test_tieee(void)
{
  print_float("tieee0", IEEESPTieee(0.0f));
  print_float("tieee1", IEEESPTieee(PI));
  print_float("tieee2", IEEESPTieee(-PI));
  print_float("tieee2", IEEESPTieee(FLT_MIN));
  print_float("tieee3", IEEESPTieee(FLT_MAX));
  print_float("tieee4", IEEESPTieee(FLT_MIN_NEG));
  print_float("tieee5", IEEESPTieee(FLT_MAX_NEG));
}

int main(int argc, char *argv[])
{
  ULONG res = 0;

  MathIeeeSingTransBase = (BaseType *)OpenLibrary("mathieeesingtrans.library", 34);
  if(MathIeeeSingTransBase) {
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

    CloseLibrary((struct Library *)MathIeeeSingTransBase);
  } else {
    PutStr("No mathieeesingtrans.library!\n");
    res = 1;
  }
  return res;
}
