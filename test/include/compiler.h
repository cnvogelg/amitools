#ifndef COMMON_H
#define COMMON_H

/* compiler specific switches */
#ifdef __GNUC__
#ifdef __AROS__
#define REG(t,r) t
#define REG_FUNC
#else
#define REG(t,r)  t __asm(#r)
#define REG_FUNC
#endif
#else
#ifdef __VBCC__
#define REG(t,r) __reg( #r ) t
#define REG_FUNC
#else
#ifdef __SASC
#define REG(t,r) register __ ## r t
#define REG_FUNC __asm
#else
#error unsupported compiler
#endif
#endif
#endif

#endif
