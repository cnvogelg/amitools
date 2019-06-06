#include <dos/dos.h>
#include <exec/exec.h>

#include <proto/exec.h>
#include <proto/dos.h>
#include <proto/mathtrans.h>

#include "math_fast.h"
#include "math_single.h"

#define INT_MIN (-2147483647-1)
#define INT_MAX 2147483647
#define PI      3.14159265358979323846

struct Library *MathTransBase;

static void print_float(STRPTR prefix, FLOAT f)
{
  const ULONG *u = (const ULONG *)(const void *)&f;
  Printf("%s: %08lx\n", (ULONG)prefix, *u);
}

static void test_const(void)
{
  print_float("const0", FFP_MAX);
  print_float("const1", FFP_MIN);
  print_float("const2", FFP_INT_MAX);
  print_float("const3", FFP_INT_MIN);
  print_float("const4", FFP_PI);
}

static void test_acos(void)
{
  print_float("acos0", SPAcos(FFP_ONE_NEG));
  print_float("acos1", SPAcos(FFP_ONE));
  print_float("acos2", SPAcos(FFP_ZERO));
  print_float("acos3", SPAcos(FFP_0_5_NEG));
  print_float("acos4", SPAcos(FFP_0_5));
  /* invalid */
  print_float("acos5", SPAcos(FFP_2_NEG));
  print_float("acos6", SPAcos(FFP_2));
}

static void test_asin(void)
{
  print_float("asin0", SPAsin(FFP_ONE_NEG));
  print_float("asin1", SPAsin(FFP_ONE));
  print_float("asin2", SPAsin(FFP_ZERO));
  print_float("asin3", SPAsin(FFP_0_5_NEG));
  print_float("asin4", SPAsin(FFP_0_5));
  /* invalid */
  print_float("asin5", SPAsin(FFP_2_NEG));
  print_float("asin6", SPAsin(FFP_2));
}

static void test_atan(void)
{
  print_float("atan0", SPAtan(FFP_ZERO));
  print_float("atan1", SPAtan(FFP_PI));
  print_float("atan2", SPAtan(FFP_PI_NEG));
  print_float("atan3", SPAtan(FFP_MIN));
  print_float("atan4", SPAtan(FFP_MAX));
  print_float("atan5", SPAtan(FFP_MIN_NEG));
  print_float("atan6", SPAtan(FFP_MAX_NEG));
}

static void test_cos(void)
{
  print_float("cos0", SPCos(FFP_ZERO));
  print_float("cos1", SPCos(FFP_PI));
  print_float("cos2", SPCos(FFP_PI_NEG));
  print_float("cos3", SPCos(FFP_MIN));
  print_float("cos4", SPCos(FFP_MAX));
  print_float("cos5", SPCos(FFP_MIN_NEG));
  print_float("cos6", SPCos(FFP_MAX_NEG));
}

static void test_cosh(void)
{
  print_float("cosh0", SPCosh(FFP_ZERO));
  print_float("cosh1", SPCosh(FFP_PI));
  print_float("cosh2", SPCosh(FFP_PI_NEG));
  print_float("cosh3", SPCosh(FFP_MIN));
  print_float("cosh4", SPCosh(FFP_MAX));
  print_float("cosh5", SPCosh(FFP_MIN_NEG));
  print_float("cosh6", SPCosh(FFP_MAX_NEG));
}

static void test_exp(void)
{
  print_float("exp0", SPExp(FFP_ZERO));
  print_float("exp1", SPExp(FFP_PI));
  print_float("exp2", SPExp(FFP_PI_NEG));
  print_float("exp3", SPExp(FFP_MIN));
  print_float("exp4", SPExp(FFP_MAX));
  print_float("exp5", SPExp(FFP_MIN_NEG));
  print_float("exp6", SPExp(FFP_MAX_NEG));
}

static void test_fieee(void)
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
  print_float("fieee13", SPFieee((float)INT_MIN));
  print_float("fieee14", SPFieee((float)INT_MAX));
  print_float("fieee15", SPFieee(10.0f));
  print_float("fieee16", SPFieee(-10.0f));
  print_float("fieee15", SPFieee(1000.0f));
  print_float("fieee16", SPFieee(-1000.0f));
}

static void test_log(void)
{
  print_float("log0", SPLog(FFP_ZERO));
  print_float("log1", SPLog(FFP_PI));
  print_float("log2", SPLog(FFP_PI_NEG));
  print_float("log3", SPLog(FFP_MIN));
  print_float("log4", SPLog(FFP_MAX));
  print_float("log5", SPLog(FFP_MIN_NEG));
  print_float("log6", SPLog(FFP_MAX_NEG));
}

static void test_log10(void)
{
  print_float("logt0", SPLog10(FFP_ZERO));
  print_float("logt1", SPLog10(FFP_10));
  print_float("logt2", SPLog10(FFP_10_NEG));
  print_float("logt3", SPLog10(FFP_MIN));
  print_float("logt4", SPLog10(FFP_MAX));
  print_float("logt5", SPLog10(FFP_MIN_NEG));
  print_float("logt6", SPLog10(FFP_MAX_NEG));
}

static void test_pow(void)
{
  print_float("pow0", SPPow(FFP_ZERO, FFP_ZERO));
  print_float("pow1", SPPow(FFP_1000, FFP_ZERO));
  print_float("pow2", SPPow(FFP_MAX, FFP_MAX));
  print_float("pow3", SPPow(FFP_1000_NEG, FFP_1000_NEG));
  print_float("pow4", SPPow(FFP_2, FFP_10));
}

static void test_sin(void)
{
  print_float("sin0", SPSin(FFP_ZERO));
  print_float("sin1", SPSin(FFP_PI));
  print_float("sin2", SPSin(FFP_PI_NEG));
  print_float("sin3", SPSin(FFP_MIN));
  print_float("sin4", SPSin(FFP_MAX));
  print_float("sin5", SPSin(FFP_MIN_NEG));
  print_float("sin6", SPSin(FFP_MAX_NEG));
}

static void test_sincos(void)
{
  float cos;

  print_float("sincos0", SPSincos(&cos, FFP_ZERO));
  print_float("cosret0", cos);
  print_float("sincos1", SPSincos(&cos, FFP_PI));
  print_float("cosret1", cos);
  print_float("sincos2", SPSincos(&cos, FFP_PI_NEG));
  print_float("cosret2", cos);
  print_float("sincos3", SPSincos(&cos, FFP_MIN));
  print_float("cosret3", cos);
  print_float("sincos4", SPSincos(&cos, FFP_MAX));
  print_float("cosret4", cos);
  print_float("sincos5", SPSincos(&cos, FFP_MIN_NEG));
  print_float("cosret5", cos);
  print_float("sincos6", SPSincos(&cos, FFP_MAX_NEG));
  print_float("cosret6", cos);
}

static void test_sinh(void)
{
  print_float("sinh0", SPSinh(FFP_ZERO));
  print_float("sinh1", SPSinh(FFP_PI));
  print_float("sinh2", SPSinh(FFP_PI_NEG));
  print_float("sinh3", SPSinh(FFP_MIN));
  print_float("sinh4", SPSinh(FFP_MAX));
  print_float("sinh5", SPSinh(FFP_MIN_NEG));
#if 0
  print_float("sinh6", SPSinh(FFP_MAX_NEG));
#endif
}

static void test_sqrt(void)
{
  print_float("sqrt0", SPSqrt(FFP_ZERO));
  print_float("sqrt1", SPSqrt(FFP_2));
  print_float("sqrt2", SPSqrt(FFP_2_NEG));
  print_float("sqrt3", SPSqrt(FFP_MIN));
  print_float("sqrt4", SPSqrt(FFP_MAX));
  print_float("sqrt5", SPSqrt(FFP_MIN_NEG));
  print_float("sqrt6", SPSqrt(FFP_MAX_NEG));
}

static void test_tan(void)
{
  print_float("tan0", SPTan(FFP_ZERO));
  print_float("tan1", SPTan(FFP_PI));
  print_float("tan2", SPTan(FFP_PI_NEG));
  print_float("tan3", SPTan(FFP_MIN));
  print_float("tan4", SPTan(FFP_MAX));
  print_float("tan5", SPTan(FFP_MIN_NEG));
  print_float("tan6", SPTan(FFP_MAX_NEG));
}

static void test_tanh(void)
{
  print_float("tanh0", SPTanh(FFP_ZERO));
  print_float("tanh1", SPTanh(FFP_PI));
  print_float("tanh2", SPTanh(FFP_PI_NEG));
  print_float("tanh3", SPTanh(FFP_MIN));
  print_float("tanh4", SPTanh(FFP_MAX));
  print_float("tanh5", SPTanh(FFP_MIN_NEG));
  print_float("tanh6", SPTanh(FFP_MAX_NEG));
}

static void test_tieee(void)
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
  print_float("tieee9", SPTieee(FFP_INT_MIN));
  print_float("tieee10", SPTieee(FFP_INT_MAX));
  print_float("tieee11", SPTieee(FFP_10));
  print_float("tieee12", SPTieee(FFP_10_NEG));
  print_float("tieee13", SPTieee(FFP_1000));
  print_float("tieee14", SPTieee(FFP_1000_NEG));
}

int main(int argc, char *argv[])
{
  ULONG res = 0;

  MathTransBase = OpenLibrary("mathtrans.library", 34);
  if(MathTransBase) {
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

    CloseLibrary(MathTransBase);
  } else {
    PutStr("No mathtrans.library!\n");
    res = 1;
  }
  return res;
}
