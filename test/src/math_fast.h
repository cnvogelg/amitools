const ULONG ffp_zero[1]    = { 0x00000000UL };
const ULONG ffp_one[1]     = { 0x80000041UL };
const ULONG ffp_one_neg[1] = { 0x800000C1UL };
const ULONG ffp_pi[1]      = { 0xC90FDB42UL };
const ULONG ffp_pi_neg[1]  = { 0xC90FDBC2UL };

const ULONG ffp_min[1]     = { 0x80000001UL };
const ULONG ffp_min_neg[1] = { 0x80000081UL };
const ULONG ffp_max[1]     = { 0xFFFFFF7FUL };
const ULONG ffp_max_neg[1] = { 0xFFFFFFFFUL };

#define FFP_ZERO (*(const FLOAT *)(const void *)ffp_zero)
#define FFP_ONE (*(const FLOAT *)(const void *)ffp_one)
#define FFP_ONE_NEG (*(const FLOAT *)(const void *)ffp_one_neg)
#define FFP_PI (*(const FLOAT *)(const void *)ffp_pi)
#define FFP_PI_NEG (*(const FLOAT *)(const void *)ffp_pi_neg)

#define FFP_MIN (*(const FLOAT *)(const void *)ffp_min)
#define FFP_MIN_NEG (*(const FLOAT *)(const void *)ffp_min_neg)
#define FFP_MAX (*(const FLOAT *)(const void *)ffp_max)
#define FFP_MAX_NEG (*(const FLOAT *)(const void *)ffp_max_neg)
