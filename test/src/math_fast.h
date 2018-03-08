const ULONG ffp_zero[1]    = { 0x00000000UL };
const ULONG ffp_one[1]     = { 0x80000041UL };
const ULONG ffp_one_neg[1] = { 0x800000C1UL };
const ULONG ffp_0_5[1]     = { 0x80000040UL };
const ULONG ffp_0_5_neg[1] = { 0x800000C0UL };
const ULONG ffp_2[1]       = { 0x80000042UL };
const ULONG ffp_2_neg[1]   = { 0x800000C2UL };
const ULONG ffp_10[1]      = { 0xA0000044UL };
const ULONG ffp_10_neg[1]  = { 0xA00000C4UL };
const ULONG ffp_1000[1]    = { 0xFA00004AUL };
const ULONG ffp_1000_neg[1]= { 0xFA0000CAUL };
const ULONG ffp_pi[1]      = { 0xC90FDB42UL };
const ULONG ffp_pi_neg[1]  = { 0xC90FDBC2UL };

const ULONG ffp_int_min[1] = { 0x800000E0UL };
const ULONG ffp_int_max[1] = { 0x80000060UL };

const ULONG ffp_min[1]     = { 0x80000001UL };
const ULONG ffp_min_neg[1] = { 0x80000081UL };
const ULONG ffp_max[1]     = { 0xFFFFFF7FUL };
const ULONG ffp_max_neg[1] = { 0xFFFFFFFFUL };

#define FFP_ZERO (*(const FLOAT *)(const void *)ffp_zero)
#define FFP_ONE (*(const FLOAT *)(const void *)ffp_one)
#define FFP_ONE_NEG (*(const FLOAT *)(const void *)ffp_one_neg)
#define FFP_0_5 (*(const FLOAT *)(const void *)ffp_0_5)
#define FFP_0_5_NEG (*(const FLOAT *)(const void *)ffp_0_5_neg)
#define FFP_2 (*(const FLOAT *)(const void *)ffp_2)
#define FFP_2_NEG (*(const FLOAT *)(const void *)ffp_2_neg)
#define FFP_10 (*(const FLOAT *)(const void *)ffp_10)
#define FFP_10_NEG (*(const FLOAT *)(const void *)ffp_10_neg)
#define FFP_1000 (*(const FLOAT *)(const void *)ffp_1000)
#define FFP_1000_NEG (*(const FLOAT *)(const void *)ffp_1000_neg)
#define FFP_PI (*(const FLOAT *)(const void *)ffp_pi)
#define FFP_PI_NEG (*(const FLOAT *)(const void *)ffp_pi_neg)

#define FFP_INT_MIN (*(const FLOAT *)(const void *)ffp_int_min)
#define FFP_INT_MAX (*(const FLOAT *)(const void *)ffp_int_max)

#define FFP_MIN (*(const FLOAT *)(const void *)ffp_min)
#define FFP_MIN_NEG (*(const FLOAT *)(const void *)ffp_min_neg)
#define FFP_MAX (*(const FLOAT *)(const void *)ffp_max)
#define FFP_MAX_NEG (*(const FLOAT *)(const void *)ffp_max_neg)
