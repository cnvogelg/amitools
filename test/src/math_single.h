const ULONG flt_max[1] = { 0x7F7FFFFFUL };
const ULONG flt_min[1] = { 0x00100000UL };
const ULONG flt_max_neg[1] = { 0xFF7FFFFFUL };
const ULONG flt_min_neg[1] = { 0x80100000UL };

const ULONG flt_ffp_max[1] = { 0x5EFFFFFFUL };
const ULONG flt_ffp_min[1] = { 0x1F800000UL };
const ULONG flt_ffp_max_neg[1] = { 0xDEFFFFFFUL };
const ULONG flt_ffp_min_neg[1] = { 0x9F800000UL };

/* float constants */
#define FLT_MAX (*(const float *)(const void *)flt_max)
#define FLT_MIN (*(const float *)(const void *)flt_min)
#define FLT_MAX_NEG (*(const float *)(const void *)flt_max_neg)
#define FLT_MIN_NEG (*(const float *)(const void *)flt_min_neg)

#define FLT_FFP_MAX (*(const float *)(const void *)flt_ffp_max)
#define FLT_FFP_MIN (*(const float *)(const void *)flt_ffp_min)
#define FLT_FFP_MAX_NEG (*(const float *)(const void *)flt_ffp_max_neg)
#define FLT_FFP_MIN_NEG (*(const float *)(const void *)flt_ffp_min_neg)
